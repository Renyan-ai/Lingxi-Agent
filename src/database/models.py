"""数据库模型定义"""

from datetime import datetime
from typing import Optional, Dict, List

from sqlalchemy import String, Text, DateTime, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, declarative_base

Base = declarative_base()


class Session(Base):
    """会话表"""
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    session_metadata: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)


class Message(Base):
    """消息表"""
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32))  # user, assistant
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    tool_results: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Memory(Base):
    """记忆表"""
    __tablename__ = "memories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    memory_type: Mapped[str] = mapped_column(String(32))  # user, feedback, project, reference
    description: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class Todo(Base):
    """待办事项表"""
    __tablename__ = "todos"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32))  # pending, in_progress, completed
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
