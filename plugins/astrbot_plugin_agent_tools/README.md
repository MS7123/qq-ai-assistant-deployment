# astrbot_plugin_agent_tools

一个最小可用的 Agent 工具调用插件。用户通过 `/agent` 输入自然语言，插件会选择合适工具执行，再返回结果。

## 指令

```text
/agent 现在服务器状态怎么样
/agent 计算 128*36
/agent 现在几点
/agent 查一下知识库里 AI 实习生相关内容
/agent 列出知识库前 20 条
/tools
```

## 当前工具

- `server_status`：查询 CPU、内存、磁盘和 Docker 容器状态
- `datetime`：查询当前时间
- `calculator`：安全计算数学表达式
- `knowledge_search`：搜索 `astrbot_plugin_simple_rag` 的本地知识库
- `knowledge_list`：列出知识库片段

## 安全边界

当前版本不提供任意 shell、任意文件读写、系统删除等高风险工具。
