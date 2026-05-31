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

## 插件能力

服务器状态查询：

```text
QQ 用户
  -> /status
  -> AstrBot 插件
  -> /proc 系统信息
  -> Docker Engine API
  -> 状态报告
```

RAG 知识库问答：

```text
QQ 用户
  -> /learn 或 /learnfile
  -> 文本抽取
  -> 结构化 chunking
  -> 本地 JSON 知识库
  -> /ask
  -> Top-K 检索
  -> AstrBot LLM Provider
  -> 基于资料生成回答
```

Agent 工具调用：

```text
QQ 用户自然语言
  -> /agent
  -> 工具路由
  -> server_status / datetime / calculator / knowledge_search
  -> 工具结果
  -> LLM 总结
  -> QQ 回复
```

`astrbot_plugin_agent_tools` 先以 `/agent` 显式触发，避免普通聊天误调用工具。当前版本只开放低风险工具，不提供任意 shell 执行或任意文件写入。

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
- RAG 知识库问答
- Agent 工具调用
- MCP 后续扩展设计
