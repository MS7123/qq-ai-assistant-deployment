# astrbot_plugin_simple_rag

一个最小可用的本地知识库 RAG 插件，用于学习文档写入、检索增强生成和 AstrBot 大模型调用。

## 指令

写入知识：

```text
/learn 成都天开智能科技有限公司 AI 实习生岗位要求包括 Python、Agent、RAG、MCP、Docker 和 WebSocket。
```

基于知识库提问：

```text
/ask 这个岗位需要学习哪些技术？
```

查看统计：

```text
/kbstats
```

列出知识片段：

```text
/kblist
/kblist 50
```

调试检索：

```text
/kbsearch 你的问题
/kbshow k3
```

清空知识库：

```text
/kbclear confirm
```

读取文件入库：

```text
/learnfile /AstrBot/data/temp/example.pdf
/learnfile /AstrBot/data/temp/example.docx
```

支持格式：

```text
.txt .md .markdown .pdf .docx .xlsx .xlsm .csv .tsv
```

## 实现说明

- 知识持久化位置：`data/plugin_data/astrbot_plugin_simple_rag/knowledge.json`
- 文件读取范围：默认只允许读取 `/AstrBot/data` 下的文件
- Excel 读取方式：按工作表逐行抽取非空单元格，并用 `|` 拼接成文本
- 检索方式：本地关键词与中文 bigram 的 BM25-like scoring
- 生成方式：调用 AstrBot 当前会话配置的大模型 provider

## 后续升级

- 接入 embedding model
- 使用 FAISS 或 Chroma 存储向量
- 返回更严格的引用来源
