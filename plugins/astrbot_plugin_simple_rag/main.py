from __future__ import annotations

import asyncio
import json
import math
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


PLUGIN_NAME = "astrbot_plugin_simple_rag"
KNOWLEDGE_FILE = "knowledge.json"
MAX_CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
TOP_K = 4
MAX_FILE_BYTES = 20 * 1024 * 1024
SUPPORTED_FILE_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    text: str
    source: str
    created_at: int


class SimpleRagPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / PLUGIN_NAME
        self.knowledge_file = self.data_dir / KNOWLEDGE_FILE
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @filter.command("learn")
    async def learn(self, event: AstrMessageEvent):
        """写入一段知识到本地知识库。用法：/learn 知识内容"""
        content = extract_command_body(event.message_str, "learn")
        if not content:
            yield event.plain_result("用法：/learn 知识内容")
            return

        chunks = chunk_text(content)
        existing = load_knowledge(self.knowledge_file)
        now = int(time.time())
        source = build_source(event)

        start_index = len(existing) + 1
        for offset, chunk in enumerate(chunks):
            existing.append(
                KnowledgeChunk(
                    chunk_id=f"k{start_index + offset}",
                    text=chunk,
                    source=source,
                    created_at=now,
                )
            )

        save_knowledge(self.knowledge_file, existing)
        yield event.plain_result(f"已写入 {len(chunks)} 条知识片段，当前共 {len(existing)} 条。")

    @filter.command("learnfile")
    async def learnfile(self, event: AstrMessageEvent):
        """读取 txt、md、pdf、docx 文件并写入知识库。用法：/learnfile 文件路径"""
        file_refs = collect_file_refs(event)
        body = extract_command_body(event.message_str, "learnfile")
        if body:
            file_refs.insert(0, body)

        if not file_refs:
            yield event.plain_result(
                "用法：/learnfile /AstrBot/data/temp/example.pdf\n"
                "也可以发送文件后，在同一条消息中带上 /learnfile。"
            )
            return

        existing = load_knowledge(self.knowledge_file)
        now = int(time.time())
        source = build_source(event)
        start_index = len(existing) + 1
        added_chunks = 0
        imported_files: list[str] = []
        errors: list[str] = []

        for file_ref in file_refs:
            try:
                file_path = await asyncio.to_thread(
                    prepare_file_ref,
                    file_ref,
                    self.data_dir / "uploads",
                )
                text = await asyncio.to_thread(extract_text_from_file, file_path)
                chunks = chunk_text(text)
                if not chunks:
                    errors.append(f"{file_path.name}: 未提取到文本")
                    continue

                for offset, chunk in enumerate(chunks):
                    existing.append(
                        KnowledgeChunk(
                            chunk_id=f"k{start_index + added_chunks + offset}",
                            text=chunk,
                            source=f"{source}#{file_path.name}",
                            created_at=now,
                        )
                    )

                added_chunks += len(chunks)
                imported_files.append(file_path.name)
            except Exception as exc:
                logger.exception(f"Failed to import file into knowledge base: {file_ref}")
                errors.append(f"{file_ref}: {exc}")

        if added_chunks:
            save_knowledge(self.knowledge_file, existing)

        lines = [
            f"文件入库完成：新增 {added_chunks} 条片段，当前共 {len(existing)} 条。"
        ]
        if imported_files:
            lines.append("已导入：" + "、".join(imported_files))
        if errors:
            lines.append("问题：")
            lines.extend(f"- {error}" for error in errors[:5])

        yield event.plain_result("\n".join(lines))

    @filter.command("ask")
    async def ask(self, event: AstrMessageEvent):
        """基于本地知识库检索并调用大模型回答。用法：/ask 问题"""
        question = extract_command_body(event.message_str, "ask")
        if not question:
            yield event.plain_result("用法：/ask 问题")
            return

        knowledge = load_knowledge(self.knowledge_file)
        if not knowledge:
            yield event.plain_result("知识库还是空的。请先使用 /learn 写入资料。")
            return

        matches = retrieve(question, knowledge, TOP_K)
        if not matches:
            yield event.plain_result("没有检索到相关资料。可以先用 /learn 补充知识。")
            return

        try:
            answer = await self.generate_answer(event, question, matches)
        except Exception as exc:
            logger.exception(f"RAG answer generation failed: {exc}")
            fallback_context = format_context(matches)
            answer = (
                "大模型调用失败，先返回检索到的相关资料：\n\n"
                f"{fallback_context}\n\n"
                f"错误：{exc}"
            )

        yield event.plain_result(answer)

    @filter.command("kbstats")
    async def kbstats(self, event: AstrMessageEvent):
        """查看当前知识库统计信息。"""
        knowledge = load_knowledge(self.knowledge_file)
        total_chars = sum(len(item.text) for item in knowledge)
        yield event.plain_result(f"知识库统计：{len(knowledge)} 条片段，约 {total_chars} 个字符。")

    @filter.command("kbclear")
    async def kbclear(self, event: AstrMessageEvent):
        """清空当前简易知识库。用法：/kbclear confirm"""
        body = extract_command_body(event.message_str, "kbclear")
        if body != "confirm":
            yield event.plain_result("此操作会清空知识库。确认请发送：/kbclear confirm")
            return

        save_knowledge(self.knowledge_file, [])
        yield event.plain_result("知识库已清空。")

    async def generate_answer(
        self,
        event: AstrMessageEvent,
        question: str,
        matches: list[tuple[KnowledgeChunk, float]],
    ) -> str:
        provider_id = await self.context.get_current_chat_provider_id(
            umo=event.unified_msg_origin
        )
        context_text = format_context(matches)
        prompt = (
            "请基于下面的知识库片段回答用户问题。"
            "如果片段中没有答案，请明确说明知识库资料不足，不要编造。\n\n"
            f"知识库片段：\n{context_text}\n\n"
            f"用户问题：{question}\n\n"
            "请用中文回答，并在末尾列出引用的片段编号。"
        )

        llm_resp = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
        )
        completion_text = getattr(llm_resp, "completion_text", None)
        return completion_text or str(llm_resp) or "大模型没有返回文本。"

    async def terminate(self):
        logger.info("SimpleRagPlugin terminated.")


def extract_command_body(message: str, command: str) -> str:
    text = (message or "").strip()
    patterns = (f"/{command}", command)
    for prefix in patterns:
        if text == prefix:
            return ""
        if text.startswith(prefix + " "):
            return text[len(prefix) :].strip()
    return text


def build_source(event: AstrMessageEvent) -> str:
    get_sender_name = getattr(event, "get_sender_name", None)
    sender = get_sender_name() if callable(get_sender_name) else "unknown"
    origin = event.unified_msg_origin or "unknown"
    return f"{sender}@{origin}"


def collect_file_refs(event: AstrMessageEvent) -> list[str]:
    message_obj = getattr(event, "message_obj", None)
    message_chain = getattr(message_obj, "message", []) if message_obj else []
    file_refs: list[str] = []

    for component in message_chain:
        component_type = component.__class__.__name__.lower()
        if "file" not in component_type:
            continue

        for attr_name in ("path", "file", "file_path", "url"):
            value = getattr(component, attr_name, None)
            if isinstance(value, str) and value.strip():
                file_refs.append(value.strip())
                break

    return file_refs


def prepare_file_ref(file_ref: str, upload_dir: Path) -> Path:
    if is_url(file_ref):
        return download_file(file_ref, upload_dir)
    return resolve_local_file(file_ref)


def is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"}


def download_file(url: str, upload_dir: Path) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    parsed = urllib.parse.urlparse(url)
    filename = Path(urllib.parse.unquote(Path(parsed.path).name)).name
    if not filename:
        filename = f"download-{int(time.time())}.txt"

    target = upload_dir / filename
    with urllib.request.urlopen(url, timeout=15) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_FILE_BYTES:
            raise ValueError(f"文件过大，当前限制 {MAX_FILE_BYTES // 1024 // 1024}MB")

        data = response.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f"文件过大，当前限制 {MAX_FILE_BYTES // 1024 // 1024}MB")

    target.write_bytes(data)
    return target


def resolve_local_file(file_ref: str) -> Path:
    data_root = Path(get_astrbot_data_path()).resolve()
    path = Path(file_ref).expanduser()
    if not path.is_absolute():
        path = data_root / path

    resolved = path.resolve()
    if not is_relative_to(resolved, data_root):
        raise ValueError("只允许读取 /AstrBot/data 目录下的文件")
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"文件不存在：{resolved}")
    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"文件过大，当前限制 {MAX_FILE_BYTES // 1024 // 1024}MB")
    return resolved


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_FILE_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_FILE_EXTENSIONS))
        raise ValueError(f"暂不支持 {suffix or '无扩展名'} 文件，支持：{supported}")

    if suffix in {".txt", ".md", ".markdown"}:
        return read_plain_text(path)
    if suffix == ".pdf":
        return read_pdf_text(path)
    if suffix == ".docx":
        return read_docx_text(path)

    raise ValueError(f"未实现的文件类型：{suffix}")


def read_plain_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError as exc:
            raise RuntimeError("缺少 PDF 解析依赖，请安装 pypdf。") from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[page {index}]\n{text}")
    return "\n\n".join(pages)


def read_docx_text(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("缺少 Word 解析依赖，请安装 python-docx。") from exc

    document = Document(str(path))
    parts: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return "\n".join(parts)


def chunk_text(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + MAX_CHUNK_SIZE, len(normalized))
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return [chunk for chunk in chunks if chunk]


def load_knowledge(path: Path) -> list[KnowledgeChunk]:
    if not path.exists():
        return []

    try:
        raw_items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception(f"Failed to load knowledge file: {path}")
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
            logger.warning(f"Skipped invalid knowledge item: {item}")
    return chunks


def save_knowledge(path: Path, chunks: list[KnowledgeChunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "chunk_id": item.chunk_id,
            "text": item.text,
            "source": item.source,
            "created_at": item.created_at,
        }
        for item in chunks
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def format_context(matches: list[tuple[KnowledgeChunk, float]]) -> str:
    lines: list[str] = []
    for index, (chunk, score) in enumerate(matches, start=1):
        lines.append(
            f"[{index}] id={chunk.chunk_id}, score={score:.3f}, source={chunk.source}\n"
            f"{chunk.text}"
        )
    return "\n\n".join(lines)
