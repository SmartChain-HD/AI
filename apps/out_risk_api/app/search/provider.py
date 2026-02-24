from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.schemas.risk import DocItem, SearchPreviewRequest
from app.search.aliases import esg_expand_company_terms
from app.search.rss import esg_search_rss

logger = logging.getLogger("out_risk")

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def _build_gdelt_query(terms: List[str]) -> str:
    quoted = [f"\"{t}\"" for t in terms if t]
    if not quoted:
        return ""
    if len(quoted) == 1:
        return quoted[0]
    return "(" + " OR ".join(quoted) + ")"


def _build_gdelt_url(query: str, *, max_records: int, time_window_days: int) -> str:
    start_dt = datetime.now(timezone.utc) - timedelta(days=max(1, time_window_days))
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "DateDesc",
        "startdatetime": start_dt.strftime("%Y%m%d%H%M%S"),
    }
    return str(httpx.URL(GDELT_DOC_API, params=params))


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


def _parse_doc_datetime(value: Optional[str]) -> Optional[datetime]:
    s = (value or "").strip()
    if not s:
        return None
    try:
        if "T" in s and s.endswith("Z") and len(s) == 16:
            return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
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


def _esg_filter_docs_relaxed(
    docs: List[DocItem],
    terms: List[str],
    *,
    time_window_days: int,
) -> List[DocItem]:
    if not docs:
        return []
    terms_l = [t.lower() for t in terms if t]
    keys_l = [k.lower() for k in _esg_keywords()]

    kept: List[DocItem] = []
    for d in docs:
        if not _within_time_window(d.published_at, time_window_days):
            continue
        hay = " ".join([d.title or "", d.snippet or "", d.source or "", d.url or ""]).lower()
        has_company = any(t in hay for t in terms_l) if terms_l else True
        has_keyword = any(k in hay for k in keys_l)
        if has_keyword and (has_company or not terms_l):
            kept.append(d)
    return kept


async def esg_search_gdelt(req: SearchPreviewRequest) -> List[DocItem]:
    timeout = httpx.Timeout(3.5, connect=2.0)
    time_window_days = req.search.time_window_days
    max_records = req.search.max_results

    try:
        logger.info("GDELT search start vendor=%s", req.vendor)
        gdelt_url: Optional[str] = getattr(req, "gdelt_url", None)
        terms = esg_expand_company_terms(req.vendor) or [req.vendor]
        if not gdelt_url:
            query = _build_gdelt_query(terms[:3])
            gdelt_url = _build_gdelt_url(
                query,
                max_records=max_records,
                time_window_days=time_window_days,
            )

        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(gdelt_url)

        ctype = (r.headers.get("content-type") or "").lower()
        if "json" not in ctype:
            logger.warning("GDELT non-json response: status=%s ctype=%s", r.status_code, ctype)
            return []

        try:
            data = r.json()
        except json.JSONDecodeError:
            logger.warning("GDELT json decode failed: status=%s head=%s", r.status_code, r.text[:120])
            return []

        docs = _esg_parse_gdelt_to_docs(data)
        filtered = _esg_filter_docs_relaxed(
            docs,
            terms,
            time_window_days=time_window_days,
        )
        logger.info("GDELT docs raw=%s filtered=%s", len(docs), len(filtered))
        return filtered[:max_records]
    except httpx.TimeoutException:
        logger.warning("GDELT timeout")
        return []
    except Exception as e:
        logger.exception("GDELT error: %s", e)
        return []


def _esg_parse_gdelt_to_docs(data: Dict[str, Any]) -> List[DocItem]:
    items = data.get("articles") or data.get("data") or data.get("results") or []
    docs: List[DocItem] = []

    for i, it in enumerate(items):
        title = (it.get("title") or it.get("name") or "").strip()
        url = (it.get("url") or it.get("sourceUrl") or it.get("link") or "").strip()
        source = (it.get("sourceCountry") or it.get("source") or it.get("domain") or "GDELT").strip()
        published_at = (it.get("seendate") or it.get("publishedAt") or it.get("date") or None)
        snippet = (it.get("summary") or it.get("snippet") or None)

        if not title or not url:
            continue

        docs.append(
            DocItem(
                doc_id=f"gdelt_{i}",
                title=title,
                url=url,
                source=source,
                published_at=str(published_at) if published_at else None,
                snippet=snippet,
            )
        )

    seen: set[tuple[str, str]] = set()
    uniq: List[DocItem] = []
    for d in docs:
        key = ((d.title or "").strip().lower(), (d.url or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(d)
    return uniq


async def esg_search_documents(req: SearchPreviewRequest) -> List[DocItem]:
    async def _gdelt_safe() -> List[DocItem]:
        try:
            return await asyncio.wait_for(esg_search_gdelt(req), timeout=4.0)
        except asyncio.TimeoutError:
            logger.warning("GDELT stage timeout vendor=%s", req.vendor)
            return []
        except Exception as e:
            logger.warning("GDELT stage failed vendor=%s err=%s", req.vendor, e)
            return []

    async def _rss_safe() -> List[DocItem]:
        try:
            return await asyncio.wait_for(asyncio.to_thread(esg_search_rss, req), timeout=4.0)
        except asyncio.TimeoutError:
            logger.warning("RSS stage timeout vendor=%s", req.vendor)
            return []
        except Exception as e:
            logger.warning("RSS stage failed vendor=%s err=%s", req.vendor, e)
            return []

    gdelt_docs, rss_docs = await asyncio.gather(_gdelt_safe(), _rss_safe())
    max_results = req.search.max_results

    merged: List[DocItem] = []
    seen: set[tuple[str, str]] = set()
    for d in gdelt_docs + rss_docs:
        key = ((d.title or "").strip().lower(), (d.url or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(d)
        if len(merged) >= max_results:
            break
    return merged
