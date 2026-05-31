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

## 注意事项

- `.env` 和 `data/` 目录包含敏感信息，不应提交到 Git。
- NapCat 首次登录后的状态文件会保存在 `data/napcat`。
- AstrBot 配置和插件数据会保存在 `data/astrbot`。
