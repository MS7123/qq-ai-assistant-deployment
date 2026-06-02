# 部署文档

## 前置条件

- 一台 Linux 云服务器
- 已安装 Docker 和 Docker Compose
- 安全组放行 `6185`、`6199`、`3001`、`6099` 等必要端口

## 部署步骤

1. 克隆仓库。

```bash
git clone <repo-url>
cd qq-ai-assistant-deployment
```

2. 创建环境变量文件。

```bash
cp .env.example .env
```

3. 修改 `.env` 中的 QQ 账号和 Shipyard token。

4. 启动服务。

```bash
docker compose up -d
```

5. 查看日志。

```bash
docker compose logs -f astrbot
docker compose logs -f napcat
```

## 服务器更新

如果服务器访问 GitHub 不稳定，使用 ZIP 更新：

```bash
cd /root

rm -f qq-ai-assistant-deployment-main.zip
rm -rf qq-ai-assistant-deployment-main

wget -O qq-ai-assistant-deployment-main.zip https://codeload.github.com/MS7123/qq-ai-assistant-deployment/zip/refs/heads/main

unzip -q qq-ai-assistant-deployment-main.zip

cp -a qq-ai-assistant-deployment-main/plugins ./qq-ai-assistant-deployment/
cp -a qq-ai-assistant-deployment-main/docker-compose.yml ./qq-ai-assistant-deployment/docker-compose.yml
cp -a qq-ai-assistant-deployment-main/README.md ./qq-ai-assistant-deployment/README.md
cp -a qq-ai-assistant-deployment-main/docs ./qq-ai-assistant-deployment/

rm -f qq-ai-assistant-deployment-main.zip
rm -rf qq-ai-assistant-deployment-main

cd /root/qq-ai-assistant-deployment
docker compose up -d
docker compose restart astrbot
```

## 常用命令

```bash
docker compose ps
docker compose restart
docker compose down
docker compose pull
docker compose up -d
```

## NapCat 保活

NapCat 可能出现容器仍在运行但 QQ 账号变为离线的情况。仓库提供了一个轻量 watchdog，用于检测最近日志中的离线或网络异常并重启 NapCat：

```bash
chmod +x /root/qq-ai-assistant-deployment/scripts/watch-napcat.sh
crontab -e
```

加入：

```cron
*/10 * * * * /root/qq-ai-assistant-deployment/scripts/watch-napcat.sh
```

查看 watchdog 日志：

```bash
tail -f /root/qq-ai-assistant-deployment/data/napcat-watchdog.log
```

这只能缩短离线后的恢复时间，不能保证 QQ 在云服务器上永久不掉线。

## 插件测试

服务器状态：

```text
/status
```

知识库写入和问答：

```text
/learn AstrBot 是一个支持插件扩展的 AI 机器人框架。
/ask AstrBot 是什么？
```

文件入库：

```text
/learnfile /AstrBot/data/temp/example.pdf
/learnfile /AstrBot/data/temp/example.docx
/learnfile /AstrBot/data/temp/example.xlsx
/learnfile
```

知识库管理：

```text
/kbstats
/kblist
/kbsearch AstrBot 是什么？
/kbshow k1
/filedebug
/kbdelete k1
/kbdelete_source example.pdf
/kbclear confirm
```

Agent 工具调用：

```text
/tools
/agent 现在服务器状态怎么样
/agent 计算 128*36
/agent 现在几点
/agent 查一下知识库里 AI 实习生相关内容
```

MCP Server 本地运行：

```bash
cd /root/qq-ai-assistant-deployment
pip install -r mcp_server/requirements.txt
ASTRBOT_DATA_DIR=/root/qq-ai-assistant-deployment/data/astrbot python mcp_server/server.py
```

stdio MCP Server 通常由 MCP 客户端自动拉起，不需要作为常驻 Web 服务运行。

## 注意事项

- `.env` 和 `data/` 目录包含敏感信息，不应提交到 Git。
- NapCat 首次登录后的状态文件会保存在 `data/napcat`。
- AstrBot 配置和插件数据会保存在 `data/astrbot`。
- `docker-compose.yml` 为了查询容器状态，将 `/var/run/docker.sock` 只读挂载到 AstrBot 容器。该能力适合学习和个人服务器使用，生产环境需要更严格的权限隔离。
