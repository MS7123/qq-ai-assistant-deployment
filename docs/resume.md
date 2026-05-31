# 简历项目描述

## 项目名称

基于 AstrBot 与 NapCat 的 QQ AI 智能助手系统

## 项目描述

基于 Docker Compose 在阿里云服务器部署 AstrBot、NapCat 与 Shipyard，接入 DeepSeek API 实现 QQ AI 机器人，支持 QQ 消息接入、AI 对话回复和云端稳定运行。项目沉淀可复现部署配置、环境变量模板与部署文档，并扩展服务器状态查询、RAG 知识库问答、多格式文件入库和 Agent 工具调用能力。

## 可写入简历的要点

- 使用 Docker Compose 编排 AstrBot、NapCat、Shipyard 多容器服务，完成云服务器部署与端口映射配置。
- 基于 NapCat 接入 QQ 消息，通过 OneBot v11 / WebSocket 与 AstrBot 建立通信，实现 QQ AI 机器人对话能力。
- 接入 DeepSeek API 实现大模型问答，并通过环境变量隔离账号、token 和服务配置。
- 基于 AstrBot 插件机制开发 `/status` 服务器状态查询工具，支持实时查看 CPU、内存、磁盘和 Docker 容器运行状态。
- 开发简易 RAG 知识库问答插件，支持通过 `/learn` 写入资料，并可读取 TXT、Markdown、PDF、Word、Excel、CSV 文档完成文本抽取、结构化 chunking、片段增删管理、检索调试、Top-K 检索和大模型问答。
- 开发 Agent 工具调用插件，支持通过自然语言调用服务器状态、时间、计算器和知识库检索等工具，并由大模型整合工具结果生成回复。
- 基于 MCP Python SDK 开发 stdio MCP Server，将服务器状态、知识库查询、时间和计算器封装为标准 MCP tools，实现工具能力标准化暴露。
