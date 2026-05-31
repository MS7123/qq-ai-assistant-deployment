# QQ AI Assistant

基于 Docker Compose 部署 AstrBot、NapCat 和 Shipyard，并接入 DeepSeek API 实现 QQ AI 机器人。

## 项目目标

当前项目从可复现部署开始，逐步扩展为具备 RAG 知识库、文件入库、服务器状态查询和 Agent 工具调用能力的 QQ AI 助手。

## 技术栈

- AstrBot: AI 机器人框架
- NapCat: QQ 接入与 OneBot v11 通信
- Shipyard: AstrBot 沙盒能力
- Docker Compose: 服务编排与云端部署
- DeepSeek API: 大模型对话能力
- RAG: 本地知识库问答
- Agent Tools: 自然语言工具调用

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

## 插件能力

- `astrbot_plugin_server_status`: 通过 `/status` 查询服务器与 Docker 容器状态。
- `astrbot_plugin_simple_rag`: 通过 `/learn`、`/learnfile`、`/ask` 实现知识库写入、文件解析和问答。
- `astrbot_plugin_agent_tools`: 通过 `/agent` 使用自然语言调用服务器状态、知识库检索、时间和计算工具。
- `mcp_server`: 将服务器状态、知识库查询、时间和计算器封装为 stdio MCP tools。

## 安全说明

不要将 `.env`、`data/`、日志、数据库、QQ 登录状态、API Key 或 token 提交到 Git。

## 后续方向

- 将 RAG 检索从关键词升级为 embedding + vector database。
- 将 MCP Server 接入更多支持 MCP 的客户端，并继续完善工具权限控制。
- 增加更完善的工具权限控制、审计日志和工具调用记录。
