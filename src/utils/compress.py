"""上下文压缩工具"""

import json
import time
from pathlib import Path
from typing import List, Dict

from anthropic import AsyncAnthropic

from src.config import settings


def estimate_size(messages: List[dict]) -> int:
    """估算消息总大小"""
    return len(str(messages))


def block_type(block):
    """获取 block 类型"""
    return block.get("type") if isinstance(block, dict) else getattr(block, "type", None)


def message_has_tool_use(msg: dict) -> bool:
    """检查消息是否包含工具调用"""
    if msg.get("role") != "assistant":
        return False
    content = msg.get("content")
    if not isinstance(content, list):
        return False
    return any(block_type(block) == "tool_use" for block in content)


def is_tool_result_message(msg: dict) -> bool:
    """检查消息是否是工具结果"""
    if msg.get("role") != "user":
        return False
    content = msg.get("content")
    if not isinstance(content, list):
        return False
    return any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content)


# ===== L1: 精简压缩 =====
def snip_compact(messages: List[dict], max_messages: int = 50) -> List[dict]:
    """压缩消息列表，保留头部和尾部"""
    if len(messages) <= max_messages:
        return messages
    
    keep_head, keep_tail = 3, max_messages - 3
    head_end, tail_start = keep_head, len(messages) - keep_tail
    
    # 确保不截断工具调用
    if head_end > 0 and message_has_tool_use(messages[head_end - 1]):
        while head_end < len(messages) and is_tool_result_message(messages[head_end]):
            head_end += 1
    
    if (tail_start > 0 and tail_start < len(messages)
            and is_tool_result_message(messages[tail_start])
            and message_has_tool_use(messages[tail_start - 1])):
        tail_start -= 1
    
    if head_end >= tail_start:
        return messages
    
    snipped = tail_start - head_end
    return messages[:head_end] + [{
        "role": "user",
        "content": f"[已压缩 {snipped} 条消息]"
    }] + messages[tail_start:]


# ===== L2: 微压缩 =====
def collect_tool_results(messages: List[dict]) -> List[tuple]:
    """收集所有工具结果"""
    blocks = []
    for mi, msg in enumerate(messages):
        if msg.get("role") != "user" or not isinstance(msg.get("content"), list):
            continue
        for bi, block in enumerate(msg["content"]):
            if isinstance(block, dict) and block.get("type") == "tool_result":
                blocks.append((mi, bi, block))
    return blocks


def micro_compact(messages: List[dict]) -> List[dict]:
    """压缩旧工具结果"""
    tool_results = collect_tool_results(messages)
    if len(tool_results) <= settings.KEEP_RECENT:
        return messages
    
    for _, _, block in tool_results[:-settings.KEEP_RECENT]:
        if len(block.get("content", "")) > 120:
            block["content"] = "[旧工具结果已压缩。如需重新运行请再次调用。]"
    
    return messages


# ===== L3: 结果持久化 =====
def persist_large_output(tool_use_id: str, output: str) -> str:
    """将大输出保存到文件"""
    if len(output) <= settings.PERSIST_THRESHOLD:
        return output
    
    settings.TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.TOOL_RESULTS_DIR / f"{tool_use_id}.txt"
    if not path.exists():
        path.write_text(output, encoding="utf-8")
    
    return f"""<持久化输出>
完整输出: {path}
预览:
{output[:2000]}
</持久化输出>"""


def tool_result_budget(messages: List[dict], max_bytes: int = 200_000) -> List[dict]:
    """预算工具结果大小"""
    if not messages:
        return messages
    
    last = messages[-1]
    if last.get("role") != "user" or not isinstance(last.get("content"), list):
        return messages
    
    blocks = [(i, b) for i, b in enumerate(last["content"]) 
              if isinstance(b, dict) and b.get("type") == "tool_result"]
    
    total = sum(len(str(b.get("content", ""))) for _, b in blocks)
    if total <= max_bytes:
        return messages
    
    # 按大小排序，优先压缩大的
    ranked = sorted(blocks, key=lambda p: len(str(p[1].get("content", ""))), reverse=True)
    
    for _, block in ranked:
        if total <= max_bytes:
            break
        
        content = str(block.get("content", ""))
        if len(content) <= settings.PERSIST_THRESHOLD:
            continue
        
        tid = block.get("tool_use_id", "unknown")
        block["content"] = persist_large_output(tid, content)
        total = sum(len(str(b.get("content", ""))) for _, b in blocks)
    
    return messages


# ===== L4: LLM 总结 =====
def write_transcript(messages: List[dict]) -> Path:
    """保存对话记录"""
    settings.TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    return path


async def summarize_history(
    client: AsyncAnthropic,
    messages: List[dict],
    model: str
) -> str:
    """使用 LLM 总结对话历史"""
    conversation = json.dumps(messages, default=str)[:80000]
    prompt = (
        "总结这段编程助手的对话，以便继续工作。\n"
        "保留: 1. 当前目标, 2. 关键发现/决策, 3. 已读/修改的文件, "
        "4. 剩余工作, 5. 用户约束。\n"
        "简洁但具体。\n\n" + conversation
    )
    
    response = await client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000
    )
    
    from src.utils.helpers import extract_text_from_content
    return extract_text_from_content(response.content).strip() or "(空总结)"


async def compact_history(
    client: AsyncAnthropic,
    messages: List[dict],
    model: str
) -> List[dict]:
    """压缩对话历史"""
    transcript_path = write_transcript(messages)
    print(f"[对话已保存: {transcript_path}]")
    
    summary = await summarize_history(client, messages, model)
    return [{"role": "user", "content": f"[已压缩]\n\n{summary}"}]


def reactive_compact(messages: List[dict]) -> List[dict]:
    """反应式压缩（当提示词过长时）"""
    transcript_path = write_transcript(messages)
    print(f"[反应式压缩，对话已保存: {transcript_path}]")
    
    # 简化版：只保留最后5条消息
    tail_start = max(0, len(messages) - 5)
    if (tail_start > 0 and tail_start < len(messages)
            and is_tool_result_message(messages[tail_start])
            and message_has_tool_use(messages[tail_start - 1])):
        tail_start -= 1
    
    return [{
        "role": "user",
        "content": f"[反应式压缩]\n\n对话已保存到: {transcript_path}"
    }] + messages[tail_start:]
