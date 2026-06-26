"""工具执行模块"""

import subprocess
import glob as glob_module
from pathlib import Path

from src.config import settings


def safe_path(path: str) -> Path:
    """安全路径检查，防止逃逸工作目录"""
    full_path = (settings.WORKDIR / path).resolve()
    if not full_path.is_relative_to(settings.WORKDIR):
        raise ValueError(f"路径超出工作目录: {path}")
    return full_path


def run_bash(command: str) -> str:
    """执行 Shell 命令"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=settings.WORKDIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120
        )
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(无输出)"
    except subprocess.TimeoutExpired:
        return "错误: 命令超时 (120s)"
    except Exception as e:
        return f"错误: {e}"


def run_read(path: str, limit: int = None) -> str:
    """读取文件内容"""
    try:
        file_path = safe_path(path)
        if not file_path.exists():
            return f"错误: 文件不存在: {path}"
        
        lines = file_path.read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... (还有 {len(lines) - limit} 行)"]
        return "\n".join(lines)
    except Exception as e:
        return f"错误: {e}"


def run_write(path: str, content: str) -> str:
    """写入文件"""
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"已写入 {len(content)} 字节到 {path}"
    except Exception as e:
        return f"错误: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    """编辑文件（替换文本）"""
    try:
        file_path = safe_path(path)
        if not file_path.exists():
            return f"错误: 文件不存在: {path}"
        
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text:
            return f"错误: 在 {path} 中未找到指定文本"
        
        file_path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"已编辑: {path}"
    except Exception as e:
        return f"错误: {e}"


def run_glob(pattern: str) -> str:
    """文件搜索"""
    try:
        results = []
        # 使用相对路径
        for match in glob_module.glob(pattern, root_dir=settings.WORKDIR, recursive=True):
            full_path = (settings.WORKDIR / match).resolve()
            if full_path.is_relative_to(settings.WORKDIR):
                results.append(match)
        
        return "\n".join(results) if results else "(无匹配文件)"
    except Exception as e:
        return f"错误: {e}"


# ===== 工具定义（用于 API） =====
TOOLS_DEFINITION = [
    {
        "name": "bash",
        "description": "执行 Shell 命令",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"]
        }
    },
    {
        "name": "read_file",
        "description": "读取文件内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "写入内容到文件",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "替换文件中的文本",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"}
            },
            "required": ["path", "old_text", "new_text"]
        }
    },
    {
        "name": "glob",
        "description": "使用 glob 模式搜索文件",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"]
        }
    }
]

# ===== 工具处理器映射 =====
TOOL_HANDLERS = {
    "bash": run_bash,
    "read_file": run_read,
    "write_file": run_write,
    "edit_file": run_edit,
    "glob": run_glob,
}
