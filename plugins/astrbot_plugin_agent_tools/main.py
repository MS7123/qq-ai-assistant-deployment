from __future__ import annotations

import ast
import asyncio
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
from pathlib import Path
from zoneinfo import ZoneInfo

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


PLUGIN_NAME = "astrbot_plugin_agent_tools"
RAG_PLUGIN_NAME = "astrbot_plugin_simple_rag"
KNOWLEDGE_FILE = "knowledge.json"
DOCKER_SOCKET = "/var/run/docker.sock"
WATCHED_CONTAINERS = ("astrbot", "napcat", "astrbot_shipyard")
TOP_K = 6


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    text: str
    source: str
    created_at: int


class AgentToolsPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        data_root = Path(get_astrbot_data_path())
        self.knowledge_file = data_root / "plugin_data" / RAG_PLUGIN_NAME / KNOWLEDGE_FILE

    @filter.command("agent")
    async def agent(self, event: AstrMessageEvent):
        """自然语言工具调用。用法：/agent 帮我查服务器状态"""
        user_text = extract_command_body(event.message_str, "agent")
        if not user_text:
            yield event.plain_result(
                "用法：/agent 你的任务\n"
                "示例：/agent 现在服务器状态怎么样\n"
                "示例：/agent 查一下知识库里 AI 实习生相关内容\n"
                "示例：/agent 计算 128*36"
            )
            return

        try:
            tool_call = await self.plan_tool_call(event, user_text)
            tool_result = await asyncio.to_thread(self.execute_tool, tool_call)
            answer = await self.summarize_tool_result(event, user_text, tool_call, tool_result)
            yield event.plain_result(answer)
        except Exception as exc:
            logger.exception(f"Agent tool call failed: {exc}")
            yield event.plain_result(f"Agent 执行失败：{exc}")

    @filter.command("tools")
    async def tools(self, event: AstrMessageEvent):
        """列出当前 Agent 可用工具。"""
        yield event.plain_result(format_tool_list())

    async def plan_tool_call(self, event: AstrMessageEvent, user_text: str) -> ToolCall:
        heuristic = heuristic_plan(user_text)
        if heuristic is not None:
            return heuristic

        provider_id = await self.context.get_current_chat_provider_id(
            umo=event.unified_msg_origin
        )
        prompt = build_planner_prompt(user_text)
        llm_resp = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
        )
        completion_text = getattr(llm_resp, "completion_text", None) or str(llm_resp)
        return parse_tool_call(completion_text)

    def execute_tool(self, tool_call: ToolCall) -> str:
        if tool_call.name == "server_status":
            return build_status_report()
        if tool_call.name == "datetime":
            return get_datetime_text()
        if tool_call.name == "calculator":
            expression = str(tool_call.arguments.get("expression", ""))
            return calculate_expression(expression)
        if tool_call.name == "knowledge_search":
            query = str(tool_call.arguments.get("query", ""))
            return search_knowledge(self.knowledge_file, query)
        if tool_call.name == "knowledge_list":
            limit = parse_int(tool_call.arguments.get("limit"), default=20, maximum=100)
            return list_knowledge(self.knowledge_file, limit)
        if tool_call.name == "help":
            return format_tool_list()
        return f"未知工具：{tool_call.name}"

    async def summarize_tool_result(
        self,
        event: AstrMessageEvent,
        user_text: str,
        tool_call: ToolCall,
        tool_result: str,
    ) -> str:
        if tool_call.name in {"server_status", "datetime", "calculator", "knowledge_list", "help"}:
            return tool_result

        provider_id = await self.context.get_current_chat_provider_id(
            umo=event.unified_msg_origin
        )
        prompt = (
            "你是一个 QQ AI Agent。请基于工具返回结果回答用户问题。\n"
            "要求：中文、简洁、不要编造工具结果之外的信息。\n\n"
            f"用户问题：{user_text}\n"
            f"调用工具：{tool_call.name}\n"
            f"工具结果：\n{tool_result}\n\n"
            "请给出最终回答。"
        )
        llm_resp = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
        )
        completion_text = getattr(llm_resp, "completion_text", None)
        return completion_text or tool_result

    async def terminate(self):
        logger.info("AgentToolsPlugin terminated.")


def extract_command_body(message: str, command: str) -> str:
    text = (message or "").strip()
    for prefix in (f"/{command}", command):
        if text == prefix:
            return ""
        if text.startswith(prefix + " "):
            return text[len(prefix):].strip()
    return text


def build_planner_prompt(user_text: str) -> str:
    return (
        "你是工具路由器。请只输出 JSON，不要输出解释。\n"
        "可用工具：\n"
        "1. server_status: 查询服务器 CPU、内存、磁盘、Docker 容器状态。arguments={}\n"
        "2. datetime: 查询当前时间。arguments={}\n"
        "3. calculator: 安全计算数学表达式。arguments={\"expression\":\"1+2\"}\n"
        "4. knowledge_search: 搜索本地知识库。arguments={\"query\":\"关键词或问题\"}\n"
        "5. knowledge_list: 列出知识库片段。arguments={\"limit\":20}\n"
        "6. help: 查看工具列表。arguments={}\n\n"
        "输出格式：\n"
        "{\"tool\":\"knowledge_search\",\"arguments\":{\"query\":\"AI 实习生\"}}\n\n"
        f"用户请求：{user_text}"
    )


def parse_tool_call(text: str) -> ToolCall:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return ToolCall("help", {})

    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return ToolCall("help", {})

    tool_name = str(payload.get("tool", "help"))
    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        arguments = {}
    if tool_name not in get_tool_names():
        tool_name = "help"
    return ToolCall(tool_name, arguments)


def heuristic_plan(user_text: str) -> ToolCall | None:
    text = user_text.strip().lower()
    compact = re.sub(r"\s+", "", text)

    if any(keyword in compact for keyword in ("服务器状态", "运行状态", "cpu", "内存", "磁盘", "容器状态")):
        return ToolCall("server_status", {})

    if any(keyword in compact for keyword in ("现在几点", "当前时间", "今天日期", "现在时间")):
        return ToolCall("datetime", {})

    if any(keyword in compact for keyword in ("工具列表", "能做什么", "帮助", "help")):
        return ToolCall("help", {})

    if any(keyword in compact for keyword in ("知识库列表", "列出知识库", "所有知识片段")):
        limit_match = re.search(r"\d+", text)
        limit = int(limit_match.group(0)) if limit_match else 20
        return ToolCall("knowledge_list", {"limit": limit})

    if any(keyword in compact for keyword in ("知识库", "检索", "搜索", "查一下", "查询")):
        return ToolCall("knowledge_search", {"query": user_text})

    expression = extract_math_expression(user_text)
    if expression:
        return ToolCall("calculator", {"expression": expression})

    return None


def get_tool_names() -> set[str]:
    return {
        "server_status",
        "datetime",
        "calculator",
        "knowledge_search",
        "knowledge_list",
        "help",
    }


def format_tool_list() -> str:
    return (
        "当前 Agent 工具：\n"
        "- server_status：查询服务器 CPU、内存、磁盘和容器状态\n"
        "- datetime：查询当前时间\n"
        "- calculator：计算数学表达式\n"
        "- knowledge_search：搜索本地知识库\n"
        "- knowledge_list：列出知识库片段\n\n"
        "示例：\n"
        "/agent 现在服务器状态怎么样\n"
        "/agent 计算 128*36\n"
        "/agent 查一下知识库里 AI 实习生相关内容"
    )


def get_datetime_text() -> str:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    return f"当前时间：{now:%Y-%m-%d %H:%M:%S} Asia/Shanghai"


def extract_math_expression(text: str) -> str:
    match = re.search(r"(?:计算|算一下|calc)?\s*([0-9\s\.\+\-\*\/\%\(\)]+)", text)
    if not match:
        return ""
    expression = match.group(1).strip()
    if not re.search(r"\d", expression) or not re.search(r"[\+\-\*\/\%]", expression):
        return ""
    return expression


def calculate_expression(expression: str) -> str:
    if not expression:
        return "没有提供可计算的表达式。"
    result = safe_eval(expression)
    return f"{expression} = {result:g}"


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


@dataclass(frozen=True)
class CpuSnapshot:
    idle: int
    total: int


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
        decoded.extend(body[position:position + chunk_size])
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


def list_knowledge(path: Path, limit: int) -> str:
    chunks = load_knowledge(path)
    if not chunks:
        return "知识库为空。"
    shown = chunks[:limit]
    lines = [f"知识库片段：共 {len(chunks)} 条，显示前 {len(shown)} 条。"]
    for item in shown:
        preview = item.text.replace("\n", " ").strip()
        if len(preview) > 120:
            preview = preview[:117] + "..."
        lines.append(f"- {item.chunk_id} | {item.source} | {preview}")
    return "\n".join(lines)


def search_knowledge(path: Path, query: str) -> str:
    chunks = load_knowledge(path)
    if not chunks:
        return "知识库为空。"
    matches = retrieve(query, chunks, TOP_K)
    if not matches:
        return "没有检索到相关知识片段。"
    return format_context(matches)


def retrieve(
    question: str,
    chunks: list[KnowledgeChunk],
    top_k: int,
) -> list[tuple[KnowledgeChunk, float]]:
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
        lowered[index:index + 2]
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


def format_context(matches: list[tuple[KnowledgeChunk, float]]) -> str:
    lines: list[str] = []
    for index, (chunk, score) in enumerate(matches, start=1):
        lines.append(
            f"[{index}] id={chunk.chunk_id}, score={score:.3f}, source={chunk.source}\n"
            f"{chunk.text}"
        )
    return "\n\n".join(lines)


def parse_int(value, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))
