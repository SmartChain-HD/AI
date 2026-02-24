"""OCR router for image files."""

from __future__ import annotations

import re
from datetime import date

from app.extractors.ocr.clova_client import run_ocr

# Supports: 2026-02-18 / 2026.2.18 / 2026 2 18
DATE_RE = re.compile(r"(\d{4})\s*[.\-/\s]\s*(\d{1,2})\s*[.\-/\s]\s*(\d{1,2})")


def _extract_dates(text: str) -> list[str]:
    dates: list[str] = []
    for year, month, day in DATE_RE.findall(text or ""):
        try:
            normalized = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            if normalized not in dates:
                dates.append(normalized)
        except Exception:
            continue
    return dates


async def extract_image(
    data: bytes,
    file_format: str,
    period_start: date,
    period_end: date,
) -> dict:
    """Extract OCR text and date clues from image bytes."""
    reasons: list[str] = []
    extras: dict[str, str] = {}

    try:
        text = await run_ocr(data, file_format)
        extras["ocr_status"] = "SUCCESS"
    except Exception as exc:
        extras["ocr_status"] = "FAILED"
        extras["ocr_error"] = f"{type(exc).__name__}: {exc}"
        return {
            "text": "",
            "dates": [],
            "date_in_range": True,
            "reasons": ["OCR_FAILED"],
            "extras": extras,
        }

    if len((text or "").strip()) == 0:
        extras["ocr_status"] = "UNREADABLE"
        return {
            "text": "",
            "dates": [],
            "date_in_range": True,
            "reasons": ["G_OCR_UNREADABLE"],
            "extras": extras,
        }

    dates = _extract_dates(text)
    date_in_range = True
    for d in dates:
        try:
            dt = date.fromisoformat(d)
            if not (period_start <= dt <= period_end):
                date_in_range = False
                reasons.append("DATE_MISMATCH")
                break
        except ValueError:
            continue

    if not dates:
        reasons.append("NO_DATE_FOUND")

    return {
        "text": text,
        "dates": dates,
        "date_in_range": date_in_range,
        "reasons": reasons,
        "extras": extras,
    }
