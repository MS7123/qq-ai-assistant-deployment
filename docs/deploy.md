# 部署文档

## 前置条件

- 一台 Linux 云服务器
- 已安装 Docker 和 Docker Compose
- 安全组放行 `6185`、`6199`、`3001`、`6099` 等必要端口

## 部署步骤

1. 克隆仓库。

```bash
git clone <repo-url>
cd qq-ai-assistant
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

## 常用命令

```bash
docker compose ps
docker compose restart
docker compose down
docker compose pull
docker compose up -d
```

## 插件更新

当前仓库包含服务器状态查询插件：

```text
plugins/astrbot_plugin_server_status
plugins/astrbot_plugin_simple_rag
```

更新插件后，在服务器执行：

```bash
git pull
docker compose restart astrbot
```

然后在 QQ 中发送：

```text
/status
```

验证机器人是否能返回 CPU、内存、磁盘和容器状态。

也可以发送：

```text
/learn AstrBot 是一个支持插件扩展的 AI 机器人框架。
/ask AstrBot 是什么？
/kblist
/kbsearch AstrBot 是什么？
/kbshow k1
```

验证简易知识库问答插件。

如果要导入文件，可以先把文件放到 AstrBot 数据目录下，再发送：

```text
/learnfile /AstrBot/data/temp/example.pdf
/learnfile /AstrBot/data/temp/example.docx
/learnfile /AstrBot/data/temp/example.xlsx
```

## 注意事项

- `.env` 和 `data/` 目录包含敏感信息，不应提交到 Git。
- NapCat 首次登录后的状态文件会保存在 `data/napcat`。
- AstrBot 配置和插件数据会保存在 `data/astrbot`。
- `docker-compose.yml` 为了查询容器状态，将 `/var/run/docker.sock` 只读挂载到 AstrBot 容器。该能力适合学习和个人服务器使用，生产环境需要更严格的权限隔离。
