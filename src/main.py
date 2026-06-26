"""灵犀Agent - 应用入口"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.config import settings
from src.database.session import init_db, engine
from src.api.routes import router
from src.api.websocket import websocket_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🚀 正在启动灵犀Agent...")
    await init_db()
    print("✅ 数据库初始化完成")
    yield
    await engine.dispose()
    print("✅ 数据库连接已关闭")


app = FastAPI(
    title="灵犀Agent",
    description="智能编程助手，支持记忆、工具调用和实时通信",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)

# WebSocket
app.add_api_websocket_route("/ws/{session_id}", websocket_endpoint)


@app.get("/")
async def root():
    """首页 - 聊天界面"""
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>🦌 灵犀Agent</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: #f7f7f8;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            height: 100vh;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: white;
            border-bottom: 1px solid #ddd;
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 20px; }
        .status {
            font-size: 14px;
            padding: 4px 12px;
            border-radius: 20px;
        }
        .status.offline { color: #ef4444; background: #fee2e2; }
        .status.online { color: #22c55e; background: #dcfce7; }
        .chat {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }
        .message { margin-bottom: 16px; }
        .message.user { text-align: right; }
        .message .bubble {
            display: inline-block;
            padding: 10px 16px;
            border-radius: 12px;
            max-width: 80%;
            word-wrap: break-word;
        }
        .message.user .bubble {
            background: #2563eb;
            color: white;
        }
        .message.assistant .bubble {
            background: white;
            border: 1px solid #ddd;
        }
        .tool {
            background: #fff7ed;
            border-left: 4px solid #f97316;
            padding: 10px 14px;
            margin: 8px 0;
            border-radius: 4px;
            font-size: 14px;
        }
        .tool pre {
            background: #1e293b;
            color: #f1f5f9;
            padding: 8px 12px;
            border-radius: 4px;
            overflow-x: auto;
            margin-top: 4px;
            font-size: 13px;
        }
        .input-area {
            background: white;
            border-top: 1px solid #ddd;
            padding: 16px 24px;
            display: flex;
            gap: 12px;
        }
        .input-area input {
            flex: 1;
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid #ccc;
            font-size: 15px;
        }
        .input-area input:focus { outline: none; border-color: #2563eb; }
        .input-area button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            background: #2563eb;
            color: white;
            font-size: 15px;
            cursor: pointer;
        }
        .input-area button:hover { background: #1d4ed8; }
        .input-area button:disabled { opacity: 0.5; cursor: not-allowed; }
        .loading {
            color: #6b7280;
            font-style: italic;
            padding: 8px 0;
        }
        pre { margin: 0; }
        code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }
        pre code { background: transparent; padding: 0; }
        .message.assistant .bubble .content { line-height: 1.6; }
        .message.assistant .bubble .content p { margin: 8px 0; }
        .message.assistant .bubble .content ul { padding-left: 20px; }
        .message.assistant .bubble .content ol { padding-left: 20px; }
        .message.assistant .bubble .content h1,h2,h3,h4 { margin: 12px 0 8px; }
        .message.assistant .bubble .content table {
            border-collapse: collapse;
            width: 100%;
            margin: 8px 0;
        }
        .message.assistant .bubble .content td, th {
            border: 1px solid #ddd;
            padding: 6px 8px;
        }
        .message.assistant .bubble .content blockquote {
            border-left: 4px solid #2563eb;
            padding-left: 12px;
            margin: 8px 0;
            color: #4b5563;
        }
        .clear-btn {
            background: none;
            border: none;
            color: #6b7280;
            cursor: pointer;
            font-size: 14px;
            padding: 4px 12px;
        }
        .clear-btn:hover { color: #ef4444; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🦌 灵犀Agent</h1>
        <div>
            <button class="clear-btn" onclick="clearHistory()">🗑️ 清空</button>
            <span class="status offline" id="status">● 离线</span>
        </div>
    </div>
    <div class="chat" id="chat"></div>
    <div class="input-area">
        <input id="input" placeholder="输入消息..." />
        <button id="sendBtn" onclick="sendMessage()">发送</button>
    </div>
</div>
<script>
    const chat = document.getElementById("chat");
    const input = document.getElementById("input");
    const statusEl = document.getElementById("status");
    const sendBtn = document.getElementById("sendBtn");

    const sessionId = "session_" + Date.now();
    let ws = null;
    let currentAssistant = null;
    let isProcessing = false;

    function connect() {
        ws = new WebSocket(`ws://${location.host}/ws/${sessionId}`);
        ws.onopen = () => {
            statusEl.className = "status online";
            statusEl.textContent = "● 在线";
            sendBtn.disabled = false;
        };
        ws.onclose = () => {
            statusEl.className = "status offline";
            statusEl.textContent = "● 离线";
            sendBtn.disabled = true;
            setTimeout(connect, 3000);
        };
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleEvent(data);
        };
    }

    function handleEvent(data) {
        switch(data.type) {
            case "chunk":
                if (!currentAssistant) {
                    currentAssistant = createAssistantMessage();
                }
                currentAssistant.raw += data.content;
                currentAssistant.content.innerHTML = marked.parse(currentAssistant.raw);
                scrollBottom();
                break;
            case "tool_call":
                addTool("🔧 " + data.tool, JSON.stringify(data.input, null, 2));
                break;
            case "tool_result":
                addTool("📋 " + data.tool, data.result);
                break;
            case "done":
                currentAssistant = null;
                isProcessing = false;
                sendBtn.disabled = false;
                break;
            case "error":
                addTool("❌ 错误", data.content);
                currentAssistant = null;
                isProcessing = false;
                sendBtn.disabled = false;
                break;
            case "cleared":
                chat.innerHTML = "";
                break;
            case "pong":
                break;
        }
    }

    function createAssistantMessage() {
        const wrapper = document.createElement("div");
        wrapper.className = "message assistant";
        const bubble = document.createElement("div");
        bubble.className = "bubble";
        const content = document.createElement("div");
        content.className = "content";
        bubble.appendChild(content);
        wrapper.appendChild(bubble);
        chat.appendChild(wrapper);
        scrollBottom();
        return { wrapper, content, raw: "" };
    }

    function createUserMessage(text) {
        const div = document.createElement("div");
        div.className = "message user";
        div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
        chat.appendChild(div);
        scrollBottom();
    }

    function addTool(title, text) {
        const div = document.createElement("div");
        div.className = "tool";
        div.innerHTML = `<strong>${escapeHtml(title)}</strong><pre>${escapeHtml(text)}</pre>`;
        chat.appendChild(div);
        scrollBottom();
    }

    function sendMessage() {
        const msg = input.value.trim();
        if (!msg || !ws || isProcessing) return;

        createUserMessage(msg);
        ws.send(JSON.stringify({ type: "chat", message: msg }));
        input.value = "";
        isProcessing = true;
        sendBtn.disabled = true;
    }

    function clearHistory() {
        if (ws) {
            ws.send(JSON.stringify({ type: "clear" }));
        }
        chat.innerHTML = "";
        currentAssistant = null;
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function scrollBottom() {
        chat.scrollTop = chat.scrollHeight;
    }

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendMessage();
    });

    connect();
</script>
</body>
</html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
