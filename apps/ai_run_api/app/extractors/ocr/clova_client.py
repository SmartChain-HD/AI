"""Naver Clova OCR client."""

from __future__ import annotations

import base64
import logging
import time
import uuid
from urllib.parse import urlparse

import httpx

from app.core.config import CLOVA_INVOKE_URL, CLOVA_OCR_SECRET

logger = logging.getLogger(__name__)


_HTTP_ERROR_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    408: "TIMEOUT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    429: "RATE_LIMIT",
    500: "SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def _normalize_format(file_format: str) -> str:
    fmt = (file_format or "").strip().lower()
    if fmt == "jpg":
        return "jpeg"
    if fmt in {"jpeg", "png", "pdf", "tiff", "gif", "bmp"}:
        return fmt
    return "png"


def _validate_config() -> None:
    if not CLOVA_INVOKE_URL:
        raise RuntimeError("CLOVA_INVOKE_URL is empty")
    if not CLOVA_OCR_SECRET:
        raise RuntimeError("CLOVA_OCR_SECRET is empty")


def _mask_secret(value: str, head: int = 4, tail: int = 2) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= head + tail:
        return "*" * len(text)
    return f"{text[:head]}***{text[-tail:]}"


def _mask_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    try:
        parsed = urlparse(text)
        host = parsed.netloc or ""
        path = parsed.path or ""
        return f"{parsed.scheme}://{host}{path}"
    except Exception:
        return text[:24] + ("..." if len(text) > 24 else "")


def _extract_error_detail(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    # Common Clova-style keys
    for key in ("message", "errorMessage", "error_message"):
        if payload.get(key):
            return str(payload.get(key))
    err = payload.get("error")
    if isinstance(err, dict):
        code = err.get("code")
        msg = err.get("message")
        if code or msg:
            return f"{code}:{msg}".strip(":")
    return ""


async def run_ocr(image_data: bytes, file_format: str = "png") -> str:
    """Send image bytes to Clova OCR and return concatenated text."""
    _validate_config()
    fmt = _normalize_format(file_format)
    req_id = str(uuid.uuid4())

    payload = {
        "version": "V2",
        "requestId": req_id,
        "timestamp": int(time.time() * 1000),
        "images": [
            {
                "format": fmt,
                "name": "image",
                "data": base64.b64encode(image_data).decode(),
            }
        ],
    }

    headers = {
        "X-OCR-SECRET": CLOVA_OCR_SECRET,
        "Content-Type": "application/json",
    }

    logger.info(
        "clova_ocr_request id=%s fmt=%s bytes=%s url=%s secret=%s",
        req_id,
        fmt,
        len(image_data),
        _mask_url(CLOVA_INVOKE_URL),
        _mask_secret(CLOVA_OCR_SECRET),
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(CLOVA_INVOKE_URL, headers=headers, json=payload)
        if resp.status_code >= 400:
            code = _HTTP_ERROR_MAP.get(resp.status_code, "HTTP_ERROR")
            detail = ""
            try:
                detail = _extract_error_detail(resp.json())
            except Exception:
                detail = (resp.text or "").strip()[:160]
            logger.warning(
                "clova_ocr_response id=%s status=%s code=%s detail=%s",
                req_id,
                resp.status_code,
                code,
                detail,
            )
            raise RuntimeError(f"CLOVA_OCR_{code}:{detail or resp.status_code}")

    result = resp.json()
    logger.info("clova_ocr_response id=%s status=%s", req_id, resp.status_code)
    texts: list[str] = []
    for img in result.get("images", []):
        for field in img.get("fields", []):
            infer_text = (field.get("inferText") or "").strip()
            if infer_text:
                texts.append(infer_text)
        # Some responses return line-level text only.
        for line in img.get("lineTexts", []):
            line_text = (line or "").strip()
            if line_text:
                texts.append(line_text)

    joined = " ".join(texts).strip()
    if not joined:
        raise RuntimeError("OCR returned empty text")
    return joined
