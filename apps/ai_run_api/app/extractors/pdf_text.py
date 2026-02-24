"""PDF ?띿뒪??異붿텧 + 議곌굔遺 OCR (湲고쉷??짠2.3, 짠4.2).

OCR 議곌굔: ?섏씠吏蹂??띿뒪??30???댄븯 鍮꾩쑉??20% ?댁긽?대㈃ OCR ?섑뻾.
"""

from __future__ import annotations

import re
from datetime import date

import fitz  # PyMuPDF

from app.extractors.ocr.clova_client import run_ocr

DATE_RE = re.compile(r"(\d{4})\s*[.\-/\s]\s*(\d{1,2})\s*[.\-/\s]\s*(\d{1,2})")

OCR_CHAR_THRESHOLD = 30
OCR_PAGE_RATIO_THRESHOLD = 0.20


def _extract_dates(text: str) -> list[str]:
    return [f"{m[0]}-{int(m[1]):02d}-{int(m[2]):02d}" for m in DATE_RE.findall(text)]


def _needs_ocr(page_texts: list[str]) -> bool:
    """?섏씠吏蹂??띿뒪??30???댄븯 鍮꾩쑉??20% ?댁긽?대㈃ True."""
    if not page_texts:
        return False
    short_pages = sum(1 for t in page_texts if len(t.strip()) <= OCR_CHAR_THRESHOLD)
    return (short_pages / len(page_texts)) >= OCR_PAGE_RATIO_THRESHOLD


def _has_signature_image(page: fitz.Page) -> bool:
    for img in page.get_images(full=True):
        rects = page.get_image_rects(img[0])
        if rects:
            for r in rects:
                if r.y0 > page.rect.height * 0.5 and r.width < 200 and r.height < 100:
                    return True
    return False


async def extract_pdf(
    data: bytes,
    period_start: date,
    period_end: date,
    force_ocr: bool = False,
) -> dict:
    """PDF?먯꽌 ?띿뒪???좎쭨/?쒕챸 異붿텧. ?꾩슂 ??OCR ?섑뻾.

    Returns dict with keys:
        text, dates, date_in_range, signature_detected, ocr_applied, reasons
    """
    doc = fitz.open(stream=data, filetype="pdf")

    page_texts: list[str] = []
    sig_detected = False
    for page in doc:
        page_texts.append(page.get_text())
        if not sig_detected and _has_signature_image(page):
            sig_detected = True
    doc.close()

    full_text = "\n".join(page_texts)
    reasons: list[str] = []
    ocr_applied = False

    # 議곌굔遺 OCR
    if force_ocr or _needs_ocr(page_texts):
        try:
            ocr_text = await run_ocr(data, "pdf")
            full_text = ocr_text if len(ocr_text) > len(full_text) else full_text
            ocr_applied = True
        except Exception:
            # OCR ?몄텧???ㅽ뙣?대룄 湲곕낯 ?띿뒪?멸? 異⑸텇?섎㈃ ?먮룆 ?ㅽ뙣濡?蹂댁? ?딅뒗??
            if len(full_text.strip()) < 80:
                reasons.append("OCR_FAILED")

    if len(full_text.strip()) < OCR_CHAR_THRESHOLD and "OCR_FAILED" not in reasons:
        reasons.append("G_OCR_UNREADABLE")

    dates = _extract_dates(full_text)

    # ?좎쭨 踰붿쐞 寃利?
    date_in_range = True
    for d in dates:
        try:
            dt = date.fromisoformat(d)
            if not (period_start <= dt <= period_end):
                date_in_range = False
                reasons.append("DATE_MISMATCH")
                break
        except ValueError:
            pass

    if not dates:
        reasons.append("NO_DATE_FOUND")
    if not sig_detected:
        reasons.append("SIGNATURE_MISSING")

    return {
        "text": full_text,
        "dates": dates,
        "date_in_range": date_in_range,
        "signature_detected": sig_detected,
        "ocr_applied": ocr_applied,
        "reasons": reasons,
    }
