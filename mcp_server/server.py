#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import math
import operator
import os
import re
import shutil
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field


SERVER_NAME = "qq_ai_assistant_mcp"
RAG_PLUGIN_NAME = "astrbot_plugin_simple_rag"
KNOWLEDGE_FILE = "knowledge.json"
DOCKER_SOCKET = "/var/run/docker.sock"
WATCHED_CONTAINERS = ("astrbot", "napcat", "astrbot_shipyard")
DEFAULT_TOP_K = 8

mcp = FastMCP(SERVER_NAME)


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class SearchKnowledgeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(..., description="Search query, for example 'AI 实习生 Python MCP'.", min_length=1)
    top_k: int = Field(default=DEFAULT_TOP_K, description="Maximum chunks to return.", ge=1, le=30)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format.")


class ListKnowledgeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    limit: int = Field(default=20, description="Maximum chunks to return.", ge=1, le=100)
    offset: int = Field(default=0, description="Number of chunks to skip.", ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format.")


class ShowChunkInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    chunk_id: str = Field(..., description="Knowledge chunk id, for example 'k3'.", min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format.")


class CalculatorInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    expression: str = Field(..., description="Math expression using numbers and + - * / % ** ().", min_length=1, max_length=200)


@dataclass(frozen=True)
class CpuSnapshot:
    idle: int
    total: int


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    text: str
    source: str
    created_at: int


@mcp.tool(
    name="qq_ai_get_server_status",
    annotations={
        "title": "Get QQ AI Server Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qq_ai_get_server_status() -> str:
    """Return CPU, memory, disk, and Docker container status for the QQ AI assistant server.

    Returns:
        str: Markdown text with CPU usage, memory usage, disk usage, and watched container states.
    """
    return build_status_report()


@mcp.tool(
    name="qq_ai_search_knowledge",
    annotations={
        "title": "Search QQ AI Knowledge Base",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qq_ai_search_knowledge(params: SearchKnowledgeInput) -> str:
    """Search the local RAG knowledge base with BM25-like keyword retrieval.

    Args:
        params (SearchKnowledgeInput): Validated input with query, top_k, and response_format.

    Returns:
        str: Matching chunks in markdown or JSON. Does not modify the knowledge base.
    """
    chunks = load_knowledge(get_knowledge_file())
    matches = retrieve(params.query, chunks, params.top_k)
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "query": params.query,
                "total_chunks": len(chunks),
                "count": len(matches),
                "matches": [
                    {
                        "rank": index,
                        "chunk_id": chunk.chunk_id,
                        "score": score,
                        "source": chunk.source,
                        "created_at": chunk.created_at,
                        "text": chunk.text,
                    }
                    for index, (chunk, score) in enumerate(matches, start=1)
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    if not chunks:
        return "知识库为空。"
    if not matches:
        return f"没有检索到与 `{params.query}` 相关的知识片段。"
    return format_matches(matches)


@mcp.tool(
    name="qq_ai_list_knowledge_chunks",
    annotations={
        "title": "List QQ AI Knowledge Chunks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qq_ai_list_knowledge_chunks(params: ListKnowledgeInput) -> str:
    """List knowledge chunks with pagination.

    Args:
        params (ListKnowledgeInput): Validated input with limit, offset, and response_format.

    Returns:
        str: Knowledge chunk summaries in markdown or JSON. Does not modify data.
    """
    chunks = load_knowledge(get_knowledge_file())
    items = chunks[params.offset : params.offset + params.limit]
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "total": len(chunks),
                "count": len(items),
                "offset": params.offset,
                "limit": params.limit,
                "has_more": params.offset + len(items) < len(chunks),
                "chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "source": chunk.source,
                        "created_at": chunk.created_at,
                        "preview": preview_text(chunk.text, 180),
                    }
                    for chunk in items
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    if not chunks:
        return "知识库为空。"
    lines = [
        f"# 知识库片段",
        f"共 {len(chunks)} 条，当前显示 {len(items)} 条，offset={params.offset}。",
        "",
    ]
    for chunk in items:
        lines.append(f"- **{chunk.chunk_id}** | {chunk.source} | {preview_text(chunk.text, 160)}")
    if params.offset + len(items) < len(chunks):
        lines.append("")
        lines.append(f"还有 {len(chunks) - params.offset - len(items)} 条未显示。")
    return "\n".join(lines)


@mcp.tool(
    name="qq_ai_show_knowledge_chunk",
    annotations={
        "title": "Show QQ AI Knowledge Chunk",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qq_ai_show_knowledge_chunk(params: ShowChunkInput) -> str:
    """Show full content for one knowledge chunk by id.

    Args:
        params (ShowChunkInput): Validated input with chunk_id and response_format.

    Returns:
        str: Full chunk content in markdown or JSON.
    """
    chunks = load_knowledge(get_knowledge_file())
    chunk = find_chunk(chunks, params.chunk_id)
    if chunk is None:
        return f"没有找到片段：{params.chunk_id}"
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "created_at": chunk.created_at,
                "text": chunk.text,
            },
            ensure_ascii=False,
            indent=2,
        )
    return f"# {chunk.chunk_id}\n\n- source: {chunk.source}\n- created_at: {chunk.created_at}\n\n{chunk.text}"


@mcp.tool(
    name="qq_ai_get_datetime",
    annotations={
        "title": "Get Current DateTime",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qq_ai_get_datetime() -> str:
    """Return current Asia/Shanghai time.

    Returns:
        str: Current timestamp in Asia/Shanghai timezone.
    """
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    return f"当前时间：{now:%Y-%m-%d %H:%M:%S} Asia/Shanghai"


@mcp.tool(
    name="qq_ai_calculate",
    annotations={
        "title": "Calculate Math Expression",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qq_ai_calculate(params: CalculatorInput) -> str:
    """Safely calculate a math expression with numbers and basic operators.

    Args:
        params (CalculatorInput): Validated input with expression.

    Returns:
        str: Calculation result.
    """
    try:
        result = safe_eval(params.expression)
    except Exception as exc:
        return f"计算失败：{exc}"
    return f"{params.expression} = {result:g}"


def get_knowledge_file() -> Path:
    data_dir = os.getenv("ASTRBOT_DATA_DIR", "./data/astrbot")
    return Path(data_dir) / "plugin_data" / RAG_PLUGIN_NAME / KNOWLEDGE_FILE


def build_status_report() -> str:
    cpu_percent = read_cpu_percent()
    memory_percent = read_memory_percent()
    disk_percent = read_disk_percent("/")
    containers = read_container_statuses(WATCHED_CONTAINERS)
    lines = [
        "# 服务器状态",
        f"- CPU 使用率：{format_percent(cpu_percent)}",
        f"- 内存使用率：{format_percent(memory_percent)}",
        f"- 磁盘使用率：{format_percent(disk_percent)}",
        "",
        "## Docker 容器",
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
    return {name: read_container_status(name) for name in container_names}


def read_container_status(container_name: str) -> str:
    try:
        status_code, body = docker_get(f"/containers/{container_name}/json")
    except OSError as exc:
        return f"query failed: {exc}"
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
    request = f"GET {path} HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n\r\n"
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
    return status_code, body_bytes.decode("utf-8", errors="replace")


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


def load_knowledge(path: Path) -> list[KnowledgeChunk]:
    if not path.exists():
        return []
    try:
        raw_items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    chunks: list[KnowledgeChunk] = []
    for item in raw_items:
        try:
            chunks.append(
                KnowledgeChunk(
                    chunk_id=str(item["chunk_id"]),
                    text=str(item["text"]),
                    source=str(item.get("source", "unknown")),
                    created_at=int(item.get("created_at", 0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return chunks


def find_chunk(chunks: list[KnowledgeChunk], chunk_id: str) -> KnowledgeChunk | None:
    normalized = chunk_id.strip().lower()
    for chunk in chunks:
        if chunk.chunk_id.lower() == normalized:
            return chunk
    return None


def retrieve(question: str, chunks: list[KnowledgeChunk], top_k: int) -> list[tuple[KnowledgeChunk, float]]:
    query_terms = tokenize(question)
    if not query_terms:
        return []
    document_terms = [tokenize(chunk.text) for chunk in chunks]
    doc_count = len(chunks)
    document_frequency: dict[str, int] = {}
    for terms in document_terms:
        for term in set(terms):
            document_frequency[term] = document_frequency.get(term, 0) + 1
    scored: list[tuple[KnowledgeChunk, float]] = []
    for chunk, terms in zip(chunks, document_terms):
        score = bm25_like_score(query_terms, terms, document_frequency, doc_count)
        if score > 0:
            scored.append((chunk, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    terms = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", lowered)
    chinese_bigrams = [
        lowered[index : index + 2]
        for index in range(len(lowered) - 1)
        if is_chinese(lowered[index]) and is_chinese(lowered[index + 1])
    ]
    return terms + chinese_bigrams


def is_chinese(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def bm25_like_score(
    query_terms: list[str],
    document_terms: list[str],
    document_frequency: dict[str, int],
    doc_count: int,
) -> float:
    if not document_terms:
        return 0.0
    term_counts: dict[str, int] = {}
    for term in document_terms:
        term_counts[term] = term_counts.get(term, 0) + 1
    score = 0.0
    doc_len_norm = 1 + math.log(1 + len(document_terms))
    for term in query_terms:
        tf = term_counts.get(term, 0)
        if tf == 0:
            continue
        df = document_frequency.get(term, 0)
        idf = math.log((doc_count + 1) / (df + 0.5)) + 1
        score += (tf / doc_len_norm) * idf
    return score


def format_matches(matches: list[tuple[KnowledgeChunk, float]]) -> str:
    lines: list[str] = ["# 知识库检索结果", ""]
    for index, (chunk, score) in enumerate(matches, start=1):
        lines.append(f"## {index}. {chunk.chunk_id} score={score:.3f}")
        lines.append(f"- source: {chunk.source}")
        lines.append("")
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines)


def preview_text(text: str, max_len: int) -> str:
    preview = text.replace("\n", " ").strip()
    if len(preview) > max_len:
        return preview[: max_len - 3] + "..."
    return preview


def safe_eval(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    return float(eval_ast_node(tree.body))


def eval_ast_node(node) -> float:
    binary_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    unary_ops = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
        left = eval_ast_node(node.left)
        right = eval_ast_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 10:
            raise ValueError("指数过大")
        return binary_ops[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in unary_ops:
        return unary_ops[type(node.op)](eval_ast_node(node.operand))
    raise ValueError("只支持数字和 + - * / % ** ()")


if __name__ == "__main__":
    mcp.run()
