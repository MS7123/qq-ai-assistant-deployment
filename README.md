# QQ AI Assistant

基于 Docker 部署 AstrBot、NapCat 和 Shipyard，并接入大模型 API 实现 QQ AI 机器人。

## 项目目标

当前版本沉淀可复现部署配置。后续计划在此基础上扩展多模型调用、RAG 知识库问答、Agent 工具调用和 MCP 工具接入能力。

## 技术栈

- AstrBot: AI 机器人框架
- NapCat: QQ 接入与 OneBot v11 通信
- Shipyard: AstrBot 沙盒能力
- Docker Compose: 服务编排与云端部署
- DeepSeek API: 大模型对话能力

## 快速开始

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
NAPCAT_ACCOUNT=你的QQ号
SHIPYARD_ACCESS_TOKEN=自定义强随机token
```

启动服务：

```bash
docker compose up -d
```

查看容器状态：

```bash
docker compose ps
```

## 访问端口

- AstrBot WebUI: `http://服务器IP:6185`
- NapCat WebUI: `http://服务器IP:3001`
- NapCat OneBot: `6099`
- AstrBot OneBot WebSocket: `6199`

## 安全说明

不要将 `.env`、`data/`、日志、数据库、QQ 登录状态、API Key 或 token 提交到 Git。

## 后续开发方向

- 封装统一 LLM Provider，支持 DeepSeek、OpenAI-compatible API、Qwen 等模型。
- 增加 RAG 知识库问答能力，包括文档解析、chunking、embedding、向量检索和引用返回。
- 设计 Agent 工具调用模块，支持文件检索、文档总结、服务器状态查询等工具。
- 接入 MCP，将本地工具能力标准化暴露给 AI 助手。
- 补充部署文档、架构文档和项目复盘文档，用于简历展示。
