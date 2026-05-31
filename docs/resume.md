# 简历项目描述

## 项目名称

基于 AstrBot 与 NapCat 的 QQ AI 智能助手系统

## 项目描述

基于 Docker Compose 在阿里云服务器部署 AstrBot、NapCat 与 Shipyard，接入 DeepSeek API 实现 QQ AI 机器人，支持 QQ 消息接入、AI 对话回复和云端稳定运行。项目沉淀可复现部署配置、环境变量模板与部署文档，后续计划扩展 RAG 知识库问答、Agent 工具调用、多模型 API 适配和 MCP 工具接入能力。

## 可写入简历的要点

- 使用 Docker Compose 编排 AstrBot、NapCat、Shipyard 多容器服务，完成云服务器部署与端口映射配置。
- 基于 NapCat 接入 QQ 消息，通过 OneBot v11 / WebSocket 与 AstrBot 建立通信，实现 QQ AI 机器人对话能力。
- 接入 DeepSeek API 实现大模型问答，并通过环境变量隔离账号、token 和服务配置。
- 规划 RAG 知识库、Agent 工具调用和 MCP 工具服务扩展方向，提升项目与 AI Agent 实习岗位的匹配度。
