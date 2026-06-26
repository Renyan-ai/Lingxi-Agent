"""配置管理"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """应用配置"""
    
    # ===== 路径配置 =====
    WORKDIR = Path(__file__).parent.parent
    SKILLS_DIR = WORKDIR / "skills"
    TRANSCRIPT_DIR = WORKDIR / ".transcripts"
    TOOL_RESULTS_DIR = WORKDIR / ".task_outputs" / "tool-results"
    MEMORY_DIR = WORKDIR / ".memory"
    
    # ===== 数据库配置 =====
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:lzx1526711085@localhost:5432/agent_db"
    )
    
    # ===== API 配置 =====
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    MODEL_ID = os.getenv("MODEL_ID", "deepseek-v4-flash")
    
    # ===== 上下文限制 =====
    CONTEXT_LIMIT = int(os.getenv("CONTEXT_LIMIT", "50000"))
    KEEP_RECENT = int(os.getenv("KEEP_RECENT", "3"))
    PERSIST_THRESHOLD = int(os.getenv("PERSIST_THRESHOLD", "30000"))
    
    # ===== 服务配置 =====
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()

# 创建必要的目录
for d in [settings.SKILLS_DIR, settings.TRANSCRIPT_DIR, 
          settings.TOOL_RESULTS_DIR, settings.MEMORY_DIR]:
    d.mkdir(parents=True, exist_ok=True)
