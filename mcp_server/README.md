# qq_ai_assistant_mcp

本目录提供一个本地 stdio MCP Server，用于把 QQ AI Assistant 的低风险工具标准化暴露给支持 MCP 的客户端。

## 工具

- `qq_ai_get_server_status`: 查询服务器 CPU、内存、磁盘和 Docker 容器状态
- `qq_ai_search_knowledge`: 搜索 RAG 知识库
- `qq_ai_list_knowledge_chunks`: 分页列出知识库片段
- `qq_ai_show_knowledge_chunk`: 查看指定知识片段全文
- `qq_ai_get_datetime`: 查询当前时间
- `qq_ai_calculate`: 安全计算数学表达式

## 安装

```bash
cd /root/qq-ai-assistant-deployment
pip install -r mcp_server/requirements.txt
```

## 运行

```bash
ASTRBOT_DATA_DIR=/root/qq-ai-assistant-deployment/data/astrbot python mcp_server/server.py
```

stdio MCP Server 通常由 MCP 客户端自动拉起，不需要作为常驻 Web 服务运行。

## 安全边界

当前只提供只读工具和安全计算器，不提供任意 shell 执行、任意文件写入或删除能力。
