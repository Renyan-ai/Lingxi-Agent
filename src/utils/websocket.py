"""WebSocket 处理"""

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import AsyncSessionLocal
from src.database.models import Session
from src.agent.core import CodingAgent


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.session_agents: dict[str, CodingAgent] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """接受连接"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"✅ 会话 {session_id} 已连接。总数: {len(self.active_connections)}")
    
    def disconnect(self, session_id: str):
        """断开连接"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.session_agents:
            del self.session_agents[session_id]
        print(f"❌ 会话 {session_id} 已断开。总数: {len(self.active_connections)}")
    
    async def send_message(self, session_id: str, message: dict):
        """发送消息到指定会话"""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message)
                return True
            except Exception as e:
                print(f"发送消息到 {session_id} 失败: {e}")
                self.disconnect(session_id)
                return False
        return False
    
    async def handle_chat(self, session_id: str, message: str, db: AsyncSession):
        """处理聊天消息"""
        if session_id not in self.session_agents:
            self.session_agents[session_id] = CodingAgent(session_id, db)
        
        agent = self.session_agents[session_id]
        
        try:
            async for event in agent.stream_chat_with_tools(message):
                await self.send_message(session_id, event)
        except Exception as e:
            await self.send_message(session_id, {
                "type": "error",
                "content": str(e)
            })


# 全局连接管理器
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 端点"""
    await manager.connect(websocket, session_id)
    
    async with AsyncSessionLocal() as db:
        # 确保会话存在
        existing = await db.execute(select(Session).where(Session.id == session_id))
        if not existing.scalar_one_or_none():
            db.add(Session(id=session_id))
            await db.commit()
        
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "chat")
                
                if msg_type == "chat":
                    await manager.handle_chat(session_id, data.get("message", ""), db)
                elif msg_type == "clear":
                    if session_id in manager.session_agents:
                        manager.session_agents[session_id].clear_history()
                    await manager.send_message(session_id, {"type": "cleared"})
                elif msg_type == "ping":
                    await manager.send_message(session_id, {"type": "pong"})
        
        except WebSocketDisconnect:
            manager.disconnect(session_id)
