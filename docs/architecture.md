# 架构说明

## 当前架构

```text
QQ 用户
  -> NapCat
  -> OneBot v11 / WebSocket
  -> AstrBot
  -> DeepSeek API
  -> AstrBot
  -> NapCat
  -> QQ 用户
```

Shipyard 为 AstrBot 提供沙盒执行能力，适合后续扩展工具调用和代码执行类能力。

## 后续目标架构

```text
QQ 用户
  -> NapCat
  -> AstrBot
  -> LLM Provider
  -> Agent Router
       -> RAG 知识库
       -> MCP Tools
       -> 本地工具
  -> 回复生成
```

## 简历可强调能力

- Docker Compose 云端部署与服务编排
- OneBot v11 协议接入
- 大模型 API 调用
- AstrBot 插件化扩展
- RAG、Agent、MCP 后续扩展设计
