"""辅助工具函数"""

import json
import ast
from typing import List, Dict, Tuple, Optional


def extract_text_from_content(content) -> str:
    """从 Anthropic 响应中提取文本"""
    if not content:
        return ""
    
    if isinstance(content, str):
        return content
    
    if not isinstance(content, list):
        return str(content)
    
    texts = []
    for block in content:
        # 处理 Anthropic 对象
        if hasattr(block, "type") and block.type == "text":
            texts.append(getattr(block, "text", ""))
        # 处理字典
        elif isinstance(block, dict) and block.get("type") == "text":
            texts.append(block.get("text", ""))
    
    return "\n".join(texts)


def normalize_todos(todos) -> Tuple[Optional[List], Optional[str]]:
    """规范化 Todos 数据"""
    if isinstance(todos, str):
        try:
            todos = json.loads(todos)
        except json.JSONDecodeError:
            try:
                todos = ast.literal_eval(todos)
            except (SyntaxError, ValueError):
                return None, "错误: todos 必须是列表或 JSON 数组字符串"
    
    if not isinstance(todos, list):
        return None, "错误: todos 必须是列表"
    
    for i, t in enumerate(todos):
        if not isinstance(t, dict):
            return None, f"错误: todos[{i}] 必须是对象"
        if "content" not in t or "status" not in t:
            return None, f"错误: todos[{i}] 缺少 'content' 或 'status'"
        if t["status"] not in ("pending", "in_progress", "completed"):
            return None, f"错误: todos[{i}] 状态无效: '{t['status']}'"
    
    return todos, None


def format_todo_status(status: str) -> str:
    """格式化任务状态图标"""
    icons = {
        "pending": "○",
        "in_progress": "▶",
        "completed": "✓"
    }
    return icons.get(status, "○")
