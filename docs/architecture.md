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

## 当前插件能力

```text
QQ 用户
  -> /status
  -> AstrBot 插件
  -> /proc 系统信息
  -> Docker Engine API
  -> 状态报告
```

`astrbot_plugin_server_status` 使用 Python 标准库读取 `/proc/stat`、`/proc/meminfo`、磁盘使用率，并通过 Docker Unix socket 查询容器运行状态。

```text
QQ 用户
  -> /learn 写入资料
  -> 本地 JSON 知识库
  -> /ask 提问
  -> 关键词检索 Top-K 片段
  -> AstrBot LLM Provider
  -> 基于资料生成回答
```

`astrbot_plugin_simple_rag` 是第一版 RAG 学习实现，先使用本地关键词检索跑通知识写入、检索和生成链路。知识片段较少时会直接将所有片段送入上下文，降低关键词检索漏召回的概率；后续可替换为 embedding + FAISS/Chroma。

文件入库链路：

```text
PDF / Word / Markdown / TXT
  -> 文本抽取
  -> chunking
  -> 本地 JSON 知识库
  -> /ask 检索问答
```

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
