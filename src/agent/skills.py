"""技能系统"""

import yaml
from pathlib import Path

from src.config import settings

# 技能注册表
SKILL_REGISTRY: dict[str, dict] = {}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 SKILL.md 的 YAML 前置元数据"""
    if not text.startswith("---"):
        return {}, text
    
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    
    return meta, parts[2].strip()


def scan_skills():
    """扫描 skills/ 目录，加载技能到注册表"""
    if not settings.SKILLS_DIR.exists():
        return
    
    for skill_dir in sorted(settings.SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        
        manifest = skill_dir / "SKILL.md"
        if manifest.exists():
            raw = manifest.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(raw)
            
            name = meta.get("name", skill_dir.name)
            desc = meta.get("description", raw.split("\n")[0].lstrip("#").strip())
            
            SKILL_REGISTRY[name] = {
                "name": name,
                "description": desc,
                "content": raw,
                "path": str(skill_dir)
            }


def list_skills() -> str:
    """列出所有可用技能"""
    if not SKILL_REGISTRY:
        return "(未找到任何技能)"
    
    lines = ["可用技能:"]
    for skill in SKILL_REGISTRY.values():
        lines.append(f"  - **{skill['name']}**: {skill['description']}")
    return "\n".join(lines)


def load_skill(name: str) -> str:
    """加载指定技能的完整内容"""
    skill = SKILL_REGISTRY.get(name)
    if not skill:
        return f"未找到技能: {name}"
    return skill["content"]


# 初始化：扫描技能
scan_skills()
