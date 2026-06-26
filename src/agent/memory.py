"""记忆系统"""

import re
import json
from typing import Optional, List

from anthropic import AsyncAnthropic
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Memory
from src.config import settings


async def write_memory(
    db: AsyncSession,
    name: str,
    memory_type: str,
    description: str,
    content: str,
    user_id: str = None
) -> Memory:
    """写入记忆到数据库"""
    memory = Memory(
        name=name,
        memory_type=memory_type,
        description=description,
        content=content,
        user_id=user_id
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def list_memories(
    db: AsyncSession,
    user_id: str = None
) -> List[dict]:
    """列出所有记忆"""
    query = select(Memory)
    if user_id:
        query = query.where(Memory.user_id == user_id)
    
    result = await db.execute(query)
    memories = result.scalars().all()
    
    return [{
        "id": m.id,
        "name": m.name,
        "description": m.description,
        "type": m.memory_type,
        "content": m.content,
    } for m in memories]


async def delete_memory(db: AsyncSession, memory_id: int) -> bool:
    """删除记忆"""
    result = await db.execute(
        delete(Memory).where(Memory.id == memory_id)
    )
    await db.commit()
    return result.rowcount > 0


def extract_text_from_content(content) -> str:
    """从 Anthropic 响应中提取文本"""
    if not isinstance(content, list):
        return str(content)
    
    texts = []
    for block in content:
        if hasattr(block, "type") and block.type == "text":
            texts.append(getattr(block, "text", ""))
        elif isinstance(block, dict) and block.get("type") == "text":
            texts.append(block.get("text", ""))
    
    return "\n".join(texts)


async def select_relevant_memories(
    db: AsyncSession,
    messages: List[dict],
    client: AsyncAnthropic,
    model: str,
    max_items: int = 5
) -> List[dict]:
    """使用 LLM 选择相关记忆"""
    memories = await list_memories(db)
    if not memories:
        return []
    
    # 收集最近的用户消息
    recent_texts = []
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(getattr(b, "text", "")) for b in content
                    if hasattr(b, "type") and b.type == "text"
                )
            if isinstance(content, str) and content.strip():
                recent_texts.append(content)
                if len(recent_texts) >= 3:
                    break
    
    recent = " ".join(reversed(recent_texts))[:2000]
    if not recent.strip():
        return []
    
    # 构建目录
    catalog_lines = []
    for i, mem in enumerate(memories):
        catalog_lines.append(f"{i}: {mem['name']} — {mem['description']}")
    catalog = "\n".join(catalog_lines)
    
    prompt = (
        "根据最近的对话和下面的记忆目录，选择明确相关的记忆索引。\n"
        "只返回 JSON 整数数组，例如 [0, 3]。如果没有相关的，返回 []。\n\n"
        f"最近对话:\n{recent}\n\n"
        f"记忆目录:\n{catalog}"
    )
    
    try:
        response = await client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        text = extract_text_from_content(response.content)
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        
        if match:
            indices = json.loads(match.group())
            selected = []
            for idx in indices:
                if isinstance(idx, int) and 0 <= idx < len(memories):
                    selected.append(memories[idx])
                    if len(selected) >= max_items:
                        break
            return selected
    except Exception:
        pass
    
    # 回退：关键词匹配
    keywords = [w.lower() for w in recent.split() if len(w) > 3]
    selected = []
    for mem in memories:
        text = (mem["name"] + " " + mem["description"]).lower()
        if any(kw in text for kw in keywords):
            selected.append(mem)
            if len(selected) >= max_items:
                break
    
    return selected


async def load_relevant_memories(
    db: AsyncSession,
    messages: List[dict],
    client: AsyncAnthropic,
    model: str
) -> str:
    """加载相关记忆内容"""
    selected = await select_relevant_memories(db, messages, client, model)
    if not selected:
        return ""
    
    parts = ["<相关记忆>"]
    for mem in selected:
        parts.append(f"### {mem['name']}\n{mem['content']}")
    parts.append("</相关记忆>")
    return "\n\n".join(parts)


async def extract_memories(
    db: AsyncSession,
    messages: List[dict],
    client: AsyncAnthropic,
    model: str
):
    """从对话中提取新记忆"""
    # 收集最近对话
    dialogue_parts = []
    for msg in messages[-10:]:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(getattr(b, "text", "")) for b in content
                if hasattr(b, "type") and b.type == "text"
            )
        if isinstance(content, str) and content.strip():
            dialogue_parts.append(f"{role}: {content}")
    
    dialogue = "\n".join(dialogue_parts)
    if not dialogue.strip():
        return
    
    # 检查已存在的记忆
    existing = await list_memories(db)
    existing_desc = "\n".join(
        f"- {m['name']}: {m['description']}" for m in existing
    ) if existing else "(无)"
    
    prompt = (
        "从对话中提取用户偏好、约束或项目事实。\n"
        "返回 JSON 数组，每个元素包含: {name, type, description, body}\n"
        "- name: 短横线命名标识符 (如 'user-preference-tabs')\n"
        "- type: 'user'(用户偏好), 'feedback'(反馈), 'project'(项目事实), 'reference'(参考资料)\n"
        "- description: 一句话摘要\n"
        "- body: 完整内容 (markdown 格式)\n"
        "如果没有新内容或已存在于现有记忆中，返回 []。\n\n"
        f"现有记忆:\n{existing_desc}\n\n"
        f"对话:\n{dialogue[:4000]}"
    )
    
    try:
        response = await client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )
        text = extract_text_from_content(response.content)
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if not match:
            return
        
        items = json.loads(match.group())
        if not items:
            return
        
        import time
        count = 0
        for mem in items:
            name = mem.get("name", f"memory_{int(time.time())}")
            mem_type = mem.get("type", "user")
            desc = mem.get("description", "")
            body = mem.get("body", "")
            
            if desc and body:
                await write_memory(db, name, mem_type, desc, body)
                count += 1
        
        if count:
            print(f"\n[记忆] 提取了 {count} 条新记忆")
    except Exception as e:
        print(f"记忆提取错误: {e}")
