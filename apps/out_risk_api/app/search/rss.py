from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional
from urllib.parse import quote_plus, urlparse

import httpx

from app.schemas.risk import DocItem, SearchPreviewRequest
from app.search.aliases import esg_expand_company_terms
from app.search.rss_sources import RSS_FEEDS

logger = logging.getLogger("out_risk.search")


def esg_hash_id(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]


def _safe_iso_date(pub_text: str) -> str:
    s = (pub_text or "").strip()
    if not s:
        return ""
    try:
        dt = parsedate_to_datetime(s)
        return dt.date().isoformat()
    except Exception:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.date().isoformat()
        except Exception:
            return ""


def _parse_doc_datetime(value: Optional[str]) -> Optional[datetime]:
    s = (value or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None


def _within_time_window(published_at: Optional[str], time_window_days: int) -> bool:
    dt = _parse_doc_datetime(published_at)
    if not dt:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - dt
    return age <= timedelta(days=max(1, time_window_days))


def _esg_keywords() -> List[str]:
    return [
        "사고",
        "산재",
        "중대재해",
        "안전",
        "위험",
        "불법",
        "위반",
        "제재",
        "벌금",
        "기소",
        "압수수색",
        "수사",
        "환경",
        "오염",
        "배출",
        "유출",
        "리콜",
        "결함",
        "fraud",
        "corruption",
        "violation",
        "sanction",
        "lawsuit",
        "indict",
        "investigation",
        "recall",
        "defect",
        "accident",
    ]


def _esg_filter_docs_relaxed(docs: List[DocItem], *, time_window_days: int) -> List[DocItem]:
    if not docs:
        return []
    keys_l = [k.lower() for k in _esg_keywords()]
    kept: List[DocItem] = []
    for d in docs:
        if not _within_time_window(d.published_at, time_window_days):
            continue
        hay = " ".join([d.title or "", d.snippet or "", d.source or "", d.url or ""]).lower()
        if any(k in hay for k in keys_l):
            kept.append(d)
    return kept


def esg_search_rss(req: SearchPreviewRequest) -> List[DocItem]:
    def build_rss_feeds(req_: SearchPreviewRequest) -> list[str]:
        base_q = (req_.vendor or "").strip()
        if not base_q:
            return []
        terms = esg_expand_company_terms(base_q) or [base_q]
        terms = terms[:3]
        window = max(30, req_.search.time_window_days)
        search_feeds = [
            f"https://news.google.com/rss/search?q={quote_plus(f'{term} when:{window}d')}&hl=ko&gl=KR&ceid=KR:ko"
            for term in terms
        ]
        merged: list[str] = []
        seen: set[str] = set()
        for feed in search_feeds + list(RSS_FEEDS):
            f = (feed or "").strip()
            if not f or f in seen:
                continue
            seen.add(f)
            merged.append(f)
        return merged

    logger.info("RSS search start vendor=%s", req.vendor)
    feeds = build_rss_feeds(req)
    if not feeds:
        return []

    items: List[DocItem] = []
    seen_url: set[str] = set()
    max_total = min(100, max(20, req.search.max_results * 2))
    max_feeds = min(8, len(feeds))
    timeout = httpx.Timeout(connect=1.2, read=1.5, write=1.0, pool=1.0)

    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "out_risk_api/0.1"}) as client:
        for feed_url in feeds[:max_feeds]:
            if len(items) >= max_total:
                break
            try:
                r = client.get(feed_url)
                r.raise_for_status()
                root = ET.fromstring(r.text)
                channel = root.find("channel")
                entries = channel.findall("item") if channel is not None else root.findall(".//item")

                for it in entries:
                    if len(items) >= max_total:
                        break
                    link = (it.findtext("link") or "").strip()
                    if not link or link in seen_url:
                        continue
                    seen_url.add(link)

                    items.append(
                        DocItem(
                            doc_id=esg_hash_id(link),
                            title=(it.findtext("title") or "").strip() or "untitled",
                            source=urlparse(link).netloc.replace("www.", "") or "unknown",
                            published_at=_safe_iso_date(it.findtext("pubDate")),
                            url=link,
                            snippet=(it.findtext("title") or "").strip(),
                        )
                    )
            except Exception as e:
                logger.warning("RSS fetch/parse failed: %s", str(e))
                continue

    seen: set[tuple[str, str]] = set()
    uniq: List[DocItem] = []
    for d in items:
        key = ((d.title or "").strip().lower(), (d.url or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(d)

    filtered = _esg_filter_docs_relaxed(uniq, time_window_days=req.search.time_window_days)[: req.search.max_results]
    logger.info("RSS docs raw=%s filtered=%s", len(items), len(filtered))
    return filtered
