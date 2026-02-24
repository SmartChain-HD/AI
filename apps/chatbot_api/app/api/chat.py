from __future__ import annotations

import logging
import re
from functools import lru_cache

import fitz  # PyMuPDF
import requests
from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag import RAGService

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    logger.info("Initializing RAG service")
    service = RAGService()
    logger.info("RAG service initialized")
    return service


def init_rag_service() -> None:
    # Startup warm-up hook (non-fatal if it fails).
    get_rag_service()


def _download_and_extract(url: str) -> str:
    """Download a PDF from URL and extract text."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text())
            return "\n".join(pages)
    except Exception as e:
        logger.warning("PDF extraction failed: %s", e)
        return ""


def _normalize_question_terms(question: str) -> list[str]:
    tokens = [token.strip() for token in re.split(r"\s+", question) if token.strip()]
    cleaned: list[str] = []
    for token in tokens:
        t = re.sub(r"[^\w가-힣]", "", token.lower())
        if len(t) < 2:
            continue
        t = re.sub(r"(은|는|이|가|을|를|에|에서|으로|와|과|도|요|까|죠|나요|했어|했나요)$", "", t)
        if len(t) >= 2:
            cleaned.append(t)
    return cleaned


def _clean_context_lines(context: str) -> list[str]:
    lines: list[str] = []
    for raw in context.splitlines():
        text = re.sub(r"\s+", " ", raw).strip()
        if not text:
            continue
        text = re.sub(r"[^\w가-힣\s\-\.,:/()%\[\]_·]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 3:
            continue
        lines.append(text)
    return lines


def _find_best_matches(lines: list[str], terms: list[str], limit: int = 4) -> list[str]:
    scored: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines):
        lowered = line.lower()
        score = sum(2 for term in terms if term and term in lowered)
        if score == 0 and terms:
            continue
        score += 1 if any(char.isdigit() for char in line) else 0
        scored.append((score, -idx, line))

    scored.sort(reverse=True)
    selected: list[str] = []
    seen = set()
    for _, _, line in scored:
        if line in seen:
            continue
        seen.add(line)
        selected.append(line)
        if len(selected) >= limit:
            break
    return selected


def _fallback_chat_response(question: str, context: str, doc_name: str | None = None) -> ChatResponse:
    lines = _clean_context_lines(context)
    terms = _normalize_question_terms(question)
    matched = _find_best_matches(lines, terms, limit=6)
    doc_title = doc_name or "선택 문서"

    if matched and terms:
        key_phrase = " ".join(terms[:3]) or question.strip()
        key_points = "\n".join(f"- {line}" for line in matched[:3])
        evidence = "\n".join(f"- {line}" for line in matched)
        answer = (
            f"{doc_title} 기준으로 질문('{key_phrase}')에 대한 내용을 정리했습니다.\n"
            "핵심 요약:\n"
            f"{key_points}\n\n"
            "근거 문장:\n"
            f"{evidence}\n\n"
            "추가 확인이 필요하면 조항명/수치(예: 지급기한, 위약금, 계약기간)를 지정해 다시 질문해 주세요."
        )
        confidence = "medium"
    elif matched:
        preview = "\n".join(f"- {line}" for line in matched[:5])
        answer = (
            f"{doc_title}에서 질문과 연관된 원문을 찾았습니다.\n"
            "관련 원문:\n"
            f"{preview}\n\n"
            "질문 범위를 조금 더 좁혀주시면(대상 조항/기간/금액) 답변을 더 정확히 정리할 수 있습니다."
        )
        confidence = "low"
    else:
        answer = (
            f"{doc_title}에서 질문과 직접 연결되는 텍스트를 찾지 못했습니다. "
            "질문에 문서명, 조항명, 날짜, 수치 키워드를 포함해 다시 요청해 주세요."
        )
        confidence = "low"

    return ChatResponse(
        answer=answer,
        sources=[],
        confidence=confidence,
        notes="문서 원문 기반 응답입니다.",
    )


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    message = req.message
    extracted_context = ""
    if req.file_url:
        extracted_context = _download_and_extract(req.file_url)
        if extracted_context:
            # 파일이 선택된 질문은 원문 기반 응답을 우선 적용해
            # 외부 LLM 연결 장애(리전 제한 등)에도 안정적으로 답변한다.
            return _fallback_chat_response(req.message, extracted_context, req.doc_name)

    try:
        rag = get_rag_service()
    except Exception as e:
        logger.exception("RAG service initialization failed: %s", e)
        return _fallback_chat_response(req.message, extracted_context, req.doc_name)

    try:
        return rag.answer(
            message,
            domain=req.domain.value,
            top_k=req.top_k,
            doc_name=req.doc_name,
            history=req.history,
        )
    except Exception as e:
        logger.exception("Chat processing failed: %s", e)
        return _fallback_chat_response(req.message, extracted_context, req.doc_name)
