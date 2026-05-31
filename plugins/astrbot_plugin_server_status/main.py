from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import time
from dataclasses import dataclass

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star


DOCKER_SOCKET = "/var/run/docker.sock"
WATCHED_CONTAINERS = ("astrbot", "napcat", "astrbot_shipyard")


@dataclass(frozen=True)
class CpuSnapshot:
    idle: int
    total: int


class ServerStatusPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("status")
    async def status(self, event: AstrMessageEvent):
        """查询服务器 CPU、内存、磁盘和 Docker 容器状态。"""
        try:
            report = await asyncio.to_thread(build_status_report)
            yield event.plain_result(report)
        except Exception as exc:
            logger.exception(f"Failed to build server status report: {exc}")
            yield event.plain_result(f"服务器状态查询失败：{exc}")

    async def terminate(self):
        logger.info("ServerStatusPlugin terminated.")


def build_status_report() -> str:
    cpu_percent = read_cpu_percent()
    memory_percent = read_memory_percent()
    disk_percent = read_disk_percent("/AstrBot/data")
    containers = read_container_statuses(WATCHED_CONTAINERS)

    lines = [
        "服务器状态",
        f"CPU 使用率：{format_percent(cpu_percent)}",
        f"内存使用率：{format_percent(memory_percent)}",
        f"磁盘使用率：{format_percent(disk_percent)}",
        "",
        "Docker 容器：",
    ]

    for name in WATCHED_CONTAINERS:
        lines.append(f"- {name}: {containers.get(name, 'unknown')}")

    return "\n".join(lines)


def read_cpu_percent(interval: float = 0.2) -> float | None:
    first = read_cpu_snapshot()
    time.sleep(interval)
    second = read_cpu_snapshot()
    if first is None or second is None:
        return None

    idle_delta = second.idle - first.idle
    total_delta = second.total - first.total
    if total_delta <= 0:
        return None

    return (1 - idle_delta / total_delta) * 100


def read_cpu_snapshot() -> CpuSnapshot | None:
    try:
        with open("/proc/stat", "r", encoding="utf-8") as stat_file:
            first_line = stat_file.readline().strip()
    except OSError:
        return None

    parts = first_line.split()
    if not parts or parts[0] != "cpu":
        return None

    values = [int(value) for value in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return CpuSnapshot(idle=idle, total=sum(values))


def read_memory_percent() -> float | None:
    values: dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as meminfo:
            for line in meminfo:
                key, raw_value = line.split(":", 1)
                values[key] = int(raw_value.strip().split()[0])
    except (OSError, ValueError):
        return None

    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None

    return (1 - available / total) * 100


def read_disk_percent(path: str) -> float | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None

    if usage.total <= 0:
        return None

    return usage.used / usage.total * 100


def read_container_statuses(container_names: tuple[str, ...]) -> dict[str, str]:
    if not os.path.exists(DOCKER_SOCKET):
        return {name: "docker socket unavailable" for name in container_names}

    statuses: dict[str, str] = {}
    for name in container_names:
        statuses[name] = read_container_status(name)
    return statuses


def read_container_status(container_name: str) -> str:
    try:
        response = docker_get(f"/containers/{container_name}/json")
    except OSError as exc:
        return f"query failed: {exc}"

    status_code, body = response
    if status_code == 404:
        return "not found"
    if status_code < 200 or status_code >= 300:
        return f"docker api error: HTTP {status_code}"

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return "invalid docker response"

    state = payload.get("State", {})
    status = state.get("Status", "unknown")
    health = state.get("Health", {}).get("Status")
    return f"{status} ({health})" if health else status


def docker_get(path: str) -> tuple[int, str]:
    request = (
        f"GET {path} HTTP/1.1\r\n"
        "Host: docker\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(DOCKER_SOCKET)
        client.sendall(request.encode("utf-8"))
        chunks: list[bytes] = []
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)

    raw_response = b"".join(chunks)
    head_bytes, _, body_bytes = raw_response.partition(b"\r\n\r\n")
    head = head_bytes.decode("utf-8", errors="replace")
    status_line = head.splitlines()[0]
    status_code = int(status_line.split()[1])
    headers = parse_headers(head)
    if headers.get("transfer-encoding", "").lower() == "chunked":
        body_bytes = decode_chunked_body(body_bytes)
    body = body_bytes.decode("utf-8", errors="replace")
    return status_code, body


def parse_headers(head: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in head.splitlines()[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def decode_chunked_body(body: bytes) -> bytes:
    decoded = bytearray()
    position = 0

    while position < len(body):
        line_end = body.find(b"\r\n", position)
        if line_end == -1:
            break

        size_line = body[position:line_end].split(b";", 1)[0].strip()
        try:
            chunk_size = int(size_line, 16)
        except ValueError:
            break

        position = line_end + 2
        if chunk_size == 0:
            break

        decoded.extend(body[position : position + chunk_size])
        position += chunk_size + 2

    return bytes(decoded)


def format_percent(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:.1f}%"
