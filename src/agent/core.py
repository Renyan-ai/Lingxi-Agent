"""Agent 核心逻辑"""

from typing import Dict, List, AsyncGenerator, Optional
from pathlib import Path

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database.models import Message, Todo
from src.agent.tools import TOOLS_DEFINITION, TOOL_HANDLERS
from src.agent.skills import list_skills, load_skill
from src.agent.memory import load_relevant_memories, extract_memories
from src.utils.compress import (
    estimate_size,
    snip_compact,
    micro_compact,
    tool_result_budget,
    compact_history,
    reactive_compact
)
from src.utils.helpers import extract_text_from_content, normalize_todos


class CodingAgent:
    """编程助手 Agent"""
    
    def __init__(self, session_id: str, db: AsyncSession, workdir: Path = None):
        self.session_id = session_id
        self.db = db
        self.workdir = workdir or settings.WORKDIR
        
        # 初始化 Anthropic 客户端（兼容 DeepSeek）
        self.client = AsyncAnthropic(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/anthropic"
        )
        self.model = settings.MODEL_ID
        
        # 对话历史
        self.messages: List[dict] = []
    
    def get_tools(self) -> List[Dict]:
        """获取工具定义（包含动态工具）"""
        tools = TOOLS_DEFINITION.copy()
        
        # 添加 Todo 工具
        tools.append({
            "name": "todo_write",
            "description": "创建和管理任务列表",
            "input_schema": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
                            },
                            "required": ["content", "status"]
                        }
                    }
                },
                "required": ["todos"]
            }
        })
        
        # 添加子代理工具
        tools.append({
            "name": "task",
            "description": "启动子代理处理复杂子任务",
            "input_schema": {
                "type": "object",
                "properties": {"description": {"type": "string"}},
                "required": ["description"]
            }
        })
        
        # 添加技能加载工具
        tools.append({
            "name": "load_skill",
            "description": "按名称加载技能的完整内容",
            "input_schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"]
            }
        })
        
        return tools
    
    def build_system_prompt(self) -> str:
        """构建系统提示"""
        skills_catalog = list_skills()
        return f"""你是一个编程助手，工作目录: {self.workdir}

可用技能:
{skills_catalog}
使用 load_skill 获取完整内容。

你有以下工具: bash, read_file, write_file, edit_file, glob, todo_write, task, load_skill
根据需要调用工具。保持简洁高效。"""
    
    async def execute_tool_async(self, tool_name: str, tool_input: Dict) -> str:
        """异步执行工具"""
        # Todo 工具
        if tool_name == "todo_write":
            return await self._handle_todo(tool_input.get("todos", []))
        
        # 子代理工具
        if tool_name == "task":
            return await self._spawn_subagent(tool_input.get("description", ""))
        
        # 技能加载
        if tool_name == "load_skill":
            return load_skill(tool_input.get("name", ""))
        
        # 其他工具（同步执行）
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return f"未知工具: {tool_name}"
        
        try:
            return handler(**tool_input)
        except Exception as e:
            return f"工具执行错误: {e}"
    
    async def _handle_todo(self, todos: list) -> str:
        """处理 Todo 写入"""
        todos, error = normalize_todos(todos)
        if error:
            return error
        
        # 删除旧的 todos
        from sqlalchemy import delete
        await self.db.execute(
            delete(Todo).where(Todo.session_id == self.session_id)
        )
        
        # 添加新的 todos
        for i, todo in enumerate(todos):
            self.db.add(Todo(
                session_id=self.session_id,
                content=todo["content"],
                status=todo["status"],
                order=i
            ))
        
        await self.db.commit()
        
        lines = ["\n## 当前任务"]
        for t in todos:
            icon = {"pending": "○", "in_progress": "▶", "completed": "✓"}[t["status"]]
            lines.append(f"  [{icon}] {t['content']}")
        
        print("\n".join(lines))
        return f"已更新 {len(todos)} 个任务"
    
    async def _spawn_subagent(self, task: str) -> str:
        """启动子代理"""
        print(f"\n[子代理启动]")
        
        sub_tools = [
            {"name": "bash", "description": "执行 Shell 命令",
             "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            {"name": "read_file", "description": "读取文件",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "write_file", "description": "写入文件",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            {"name": "edit_file", "description": "编辑文件",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
            {"name": "glob", "description": "搜索文件",
             "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
        ]
        
        sub_messages = [{"role": "user", "content": task}]
        sub_system = f"你是一个编程助手，工作目录: {self.workdir}。完成任务后返回简洁总结。不要委托给其他代理。"
        
        for _ in range(30):
            response = await self.client.messages.create(
                model=self.model,
                system=sub_system,
                messages=sub_messages,
                tools=sub_tools,
                max_tokens=8000
            )
            sub_messages.append({"role": "assistant", "content": response.content})
            
            if response.stop_reason != "tool_use":
                break
            
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    handler = TOOL_HANDLERS.get(block.name)
                    output = handler(**block.input) if handler else f"未知工具: {block.name}"
                    print(f"  [子代理] {block.name}: {str(output)[:100]}")
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output
                    })
            sub_messages.append({"role": "user", "content": results})
        
        result = extract_text_from_content(sub_messages[-1]["content"])
        if not result:
            for msg in reversed(sub_messages):
                if msg["role"] == "assistant":
                    result = extract_text_from_content(msg["content"])
                    if result:
                        break
            if not result:
                result = "子代理运行了 30 轮后未返回答案"
        
        print(f"[子代理完成]")
        return result
    
    async def stream_chat_with_tools(self, user_message: str) -> AsyncGenerator[dict, None]:
        """流式聊天，支持工具调用"""
        # 添加用户消息
        self.messages.append({"role": "user", "content": user_message})
        
        # 保存到数据库
        user_msg = Message(
            session_id=self.session_id,
            role="user",
            content=user_message
        )
        self.db.add(user_msg)
        await self.db.commit()
        
        system_prompt = self.build_system_prompt()
        
        # 加载相关记忆
        memories_content = await load_relevant_memories(
            self.db, self.messages, self.client, self.model
        )
        if memories_content:
            self.messages[-1] = {
                "role": "user",
                "content": memories_content + "\n\n" + user_message
            }
        
        max_iterations = 200
        iteration = 0
        full_response_text = ""
        all_tool_calls = []
        all_tool_results = []
        
        while iteration < max_iterations:
            iteration += 1
            
            # 应用压缩管道
            self.messages[:] = tool_result_budget(self.messages)
            self.messages[:] = snip_compact(self.messages)
            self.messages[:] = micro_compact(self.messages)
            
            if estimate_size(self.messages) > settings.CONTEXT_LIMIT:
                print("[自动压缩]")
                self.messages = await compact_history(
                    self.client, self.messages, self.model
                )
            
            full_text = ""
            tool_block_map = {}
            
            try:
                async with self.client.messages.stream(
                    model=self.model,
                    system=system_prompt,
                    messages=self.messages,
                    tools=self.get_tools(),
                    max_tokens=4096
                ) as stream:
                    
                    async for chunk in stream:
                        if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":
                            text = chunk.delta.text
                            full_text += text
                            full_response_text += text
                            yield {"type": "chunk", "content": text}
                        
                        elif chunk.type == "content_block_start" and chunk.content_block.type == "tool_use":
                            idx = chunk.index
                            tool_block_map[idx] = {
                                "id": chunk.content_block.id,
                                "name": chunk.content_block.name,
                                "input": ""
                            }
                        
                        elif chunk.type == "content_block_delta" and chunk.delta.type == "input_json_delta":
                            target_idx = chunk.index
                            partial_json = chunk.delta.partial_json
                            if partial_json and target_idx in tool_block_map:
                                tool_block_map[target_idx]["input"] += partial_json
                    
                    final_message = await stream.get_final_message()
            
            except Exception as e:
                if "prompt_too_long" in str(e).lower() or "too many tokens" in str(e).lower():
                    print("[反应式压缩]")
                    self.messages = reactive_compact(self.messages)
                    continue
                yield {"type": "error", "content": str(e)}
                return
            
            # 没有工具调用，结束
            if final_message.stop_reason != "tool_use":
                self.messages.append({
                    "role": "assistant",
                    "content": full_text
                })
                
                # 保存到数据库
                assistant_msg = Message(
                    session_id=self.session_id,
                    role="assistant",
                    content=full_response_text,
                    tool_calls=all_tool_calls if all_tool_calls else None,
                    tool_results=all_tool_results if all_tool_results else None
                )
                self.db.add(assistant_msg)
                await self.db.commit()
                
                # 提取记忆
                await extract_memories(self.db, self.messages, self.client, self.model)
                
                yield {"type": "done"}
                break
            
            # 有工具调用
            else:
                # 保存助手响应
                self.messages.append({
                    "role": "assistant",
                    "content": final_message.content
                })
                
                tool_results = []
                for block in final_message.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_id = block.id
                        
                        all_tool_calls.append({
                            "name": tool_name,
                            "input": tool_input,
                            "id": tool_id
                        })
                        
                        yield {
                            "type": "tool_call",
                            "tool": tool_name,
                            "input": tool_input,
                            "tool_id": tool_id
                        }
                        
                        try:
                            result = await self.execute_tool_async(tool_name, tool_input)
                        except Exception as e:
                            result = f"工具执行失败: {str(e)}"
                        
                        all_tool_results.append({
                            "tool": tool_name,
                            "result": result[:500],
                            "tool_id": tool_id
                        })
                        
                        yield {
                            "type": "tool_result",
                            "tool": tool_name,
                            "result": str(result)[:500],
                            "tool_id": tool_id
                        }
                        
