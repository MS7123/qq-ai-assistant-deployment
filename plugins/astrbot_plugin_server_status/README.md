# astrbot_plugin_server_status

通过 `/status` 指令查询服务器 CPU、内存、磁盘和 Docker 容器运行状态。

## 使用方式

在 QQ 私聊或群聊中发送：

```text
/status
```

示例输出：

```text
服务器状态
CPU 使用率：12.5%
内存使用率：43.2%
磁盘使用率：58.1%

Docker 容器：
- astrbot: running
- napcat: running
- astrbot_shipyard: running (healthy)
```

## 部署说明

仓库的 `docker-compose.yml` 已将本插件挂载到 AstrBot 插件目录：

```yaml
./plugins/astrbot_plugin_server_status:/AstrBot/data/plugins/astrbot_plugin_server_status:ro
```

同时挂载 Docker socket 用于查询容器状态：

```yaml
/var/run/docker.sock:/var/run/docker.sock:ro
```

修改插件代码后，在服务器执行：

```bash
git pull
docker compose restart astrbot
```

然后在 AstrBot WebUI 插件管理中确认插件已加载。
