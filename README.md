# 🦌 灵犀Agent (Lingxi Agent)

> 一个功能强大、可扩展的 AI 编程助手，支持 PostgreSQL 持久化存储、智能记忆系统、实时 WebSocket 通信和丰富的工具生态。

[![Python Version](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Anthropic](https://img.shields.io/badge/Anthropic-API-purple.svg)](https://www.anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

---

## 📖 目录

- [✨ 核心特性](#-核心特性)
- [🎯 使用场景](#-使用场景)
- [🚀 快速开始](#-快速开始)
- [🏗️ 系统架构](#️-系统架构)
- [🛠️ 工具介绍](#️-工具介绍)
- [🧩 记忆系统](#-记忆系统)
- [📡 API 接口](#-api-接口)
- [📁 技能系统](#-技能系统)
- [🔧 配置说明](#-配置说明)
- [🤝 贡献指南](#-贡献指南)
- [📄 开源协议](#-开源协议)

---

## ✨ 核心特性

### 🧠 智能 Agent 核心
- 基于 Claude / DeepSeek 等大语言模型
- 支持 Function Calling 工具调用
- 多轮对话上下文管理
- 自动提取和存储记忆

### 💾 持久化存储
- PostgreSQL 存储会话、消息、记忆和任务
- 支持会话恢复和历史查询
- 数据持久化，重启不丢失

### 🔧 丰富的工具生态
- **系统操作**: 执行 Shell 命令
- **文件操作**: 读写编辑文件
- **搜索工具**: 文件模糊匹配
- **任务管理**: 创建和追踪待办事项
- **子代理**: 委派复杂子任务
- **技能系统**: 动态加载自定义技能

### 🧩 智能记忆系统
- **自动提取**: 从对话中识别重要信息
- **类型分类**: 用户偏好、反馈、项目事实、参考资料
- **上下文检索**: 根据当前对话自动召回相关记忆
- **持久存储**: 所有记忆保存在数据库中

### 🔄 上下文压缩
- 智能压缩长对话历史
- 保留关键信息，节省 Token
- 支持对话摘要和存档

### 🌐 实时通信
- WebSocket 支持流式响应
- 实时显示工具调用过程
- 即时的 AI 思考反馈

### 🎨 开箱即用
- 内置美观的 Web 聊天界面
- Docker 一键部署
- 完整的 RESTful API

---

## 🎯 使用场景

| 场景 | 说明 |
|------|------|
| **AI 结对编程** | 代码编写、审查、优化建议 |
| **项目自动化** | 批量文件操作、命令执行 |
| **文档生成** | 自动生成和维护项目文档 |
| **代码分析** | 代码质量检查、依赖分析 |
| **任务管理** | 自动创建和追踪项目任务 |
| **知识管理** | 提取和存储项目知识库 |

---
### 结构
```text
┌─────────────────────────────────────────────────────────────┐
│                      WebSocket/HTTP API                     │
├─────────────────────────────────────────────────────────────┤
│                        CodingAgent                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Tools      │  │   Memory     │  │   Skills     │    │
│  │  - bash      │  │  - Extract   │  │  - Load      │    │
│  │  - file ops  │  │  - Retrieve  │  │  - Catalog   │    │
│  │  - todo      │  │  - Store     │  │              │    │
│  │  - subagent  │  │              │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                    PostgreSQL Database                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Sessions │  │ Messages │  │ Memories │  │  Todos   │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 方式一: Docker 部署

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/lingxi-agent.git
cd lingxi-agent

# 2. 复制环境变量配置
cp .env.example .env

# 3. 编辑 .env，填入你的 API Key
vim .env

# 4. 启动服务
docker-compose up -d

# 5. 打开浏览器访问
open http://localhost:8000


### 方式二: 手动部署

```bash

# 1. 克隆项目
git clone https://github.com/yourusername/lingxi-agent.git
cd lingxi-agent

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
vim .env  # 填入你的配置

# 5. 初始化数据库
python -c "
import asyncio
from src.database.session import init_db
asyncio.run(init_db())
"

# 6. 启动服务
python src/main.py

# 7. 访问
open http://localhost:8000
