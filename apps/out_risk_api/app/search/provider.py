# AI/apps/out_rick_api/app/search/provider.py

# 20260131 이종헌 수정: ESG 외부 위험 감지용 검색 Provider
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse

import httpx

from app.schemas.risk import DocItem, ExternalRiskDetectRequest

# 20260201 이종헌 신규: RSS 후보 수집 provider import
from app.search.rss import esg_search_rss

# 20260201 이종헌 신규: 검색 가시화용 로깅
import logging
logger = logging.getLogger("out_risk.search")

# 20260202 이종헌 신규
from app.search.aliases import esg_expand_company_terms


# 역할: URL에서 도메인(출처명)만 뽑음
def esg_domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host.replace("www.", "") if host else "unknown"
    except Exception:
        return "unknown"


# 역할: 문자열을 안정적으로 doc_id로 변환(중복 제거용)
def esg_hash_id(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]


# 역할: GDELT 날짜(YYYYMMDDhhmmss) → YYYY-MM-DD 변환
def esg_gdelt_date_to_ymd(seendate: str) -> str:
    try:
        if not seendate:
            return ""
        dt = datetime.strptime(seendate[:14], "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


# 역할: ESG 전용 검색 쿼리를 생성(회사명 + ESG 리스크 키워드)
def esg_build_esg_query(company_name: str, user_query: str) -> str:
    base = (user_query or "").strip()
    if not base:
        base = company_name

    # 20260202 이종헌 신규: alias를 OR로 묶어서 검색 커버리지 확대
    terms = esg_expand_company_terms(base) or [base]
    or_terms = " OR ".join([f'"{t}"' for t in terms])

    esg_terms = '(환경 OR 오염 OR 민원 OR 제재 OR 행정처분 OR 과징금 OR 소송 OR 회생 OR 파산 OR 부도 OR 산재 OR 중대재해 OR 임금체불 OR 파업)'
    return f"({or_terms}) AND {esg_terms}"


# 역할: GDELT Doc API로 기사 목록을 가져와 DocItem으로 변환
def esg_search_gdelt(req: ExternalRiskDetectRequest) -> List[DocItem]:
    company_name = req.company.name
    query = esg_build_esg_query(company_name, req.search.query)

    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=int(req.time_window_days or 90))
    start_str = start_dt.strftime("%Y%m%d%H%M%S")
    end_str = end_dt.strftime("%Y%m%d%H%M%S")

    # GDELT Doc 2.1: 무료/무키 방식(2일 MVP 적합)
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": int(req.search.max_results or 20),
        "startdatetime": start_str,
        "enddatetime": end_str,
    }

    # 20260201 이종헌 수정: 한국어 우선
    if (req.search.lang or "ko").lower().startswith("ko"):
        params["query"] = params["query"] + " sourcelang:kor"
    
    items: List[DocItem] = []
    seen = set()

    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    articles = (data or {}).get("articles", []) or []
    for a in articles:
        article_url = (a.get("url") or "").strip()
        if not article_url or article_url in seen:
            continue
        seen.add(article_url)

        title = (a.get("title") or "").strip() or "untitled"
        seendate = (a.get("seendate") or "").strip()
        published_at = esg_gdelt_date_to_ymd(seendate) or ""

        source = esg_domain_from_url(article_url)
        snippet = (a.get("snippet") or "").strip()

        # 증거 인용은 snippet/text에서만 발췌해야 하므로, 최소한 snippet은 채움
        doc_id = esg_hash_id(article_url)

        items.append(
            DocItem(
                doc_id=doc_id,
                title=title,
                source=source,
                published_at=published_at or start_dt.strftime("%Y-%m-%d"),
                url=article_url,
                text="",  # MVP: 원문 크롤링은 다음 단계
                snippet=snippet or title,
            )
        )

    return items


def esg_search_documents(req: ExternalRiskDetectRequest) -> List[DocItem]:
    if not req.search.enabled:
        return []

    sources = set(req.search.sources or [])

    # 20260201 이종헌 수정: news가 없으면 수집하지 않음(MVP 정책)
    if sources and "news" not in sources:
        return []
    
    docs: List[DocItem] = []

    try:
        gdelt_docs = esg_search_gdelt(req)
        docs.extend(gdelt_docs)
        logger.info("GDELT returned %d docs", len(gdelt_docs))
    except Exception as e:
        logger.warning("GDELT failed: %s", str(e))

    # 20260201 이종헌 신규: GDELT로 max_results를 이미 채웠으면 RSS 호출을 생략(응답 지연/timeout 방지)
    if len(docs) < int(req.search.max_results or 20):  # 신규: 부족할 때만 RSS 시도
        try:
            rss_docs = esg_search_rss(req)
            docs.extend(rss_docs)
            logger.info("RSS returned %d docs", len(rss_docs))
        except Exception as e:
            logger.warning("RSS failed: %s", str(e))

    # 20260202 이종헌 신규: 검색어가 비어있으면 회사명으로 '관련성 필터'를 걸기
    must = (req.search.query or "").strip() or (req.company.name or "").strip()  # 신규: 필터 기준(검색어 우선)
    must_lower = must.lower()  # 신규: 대소문자 무시 비교용

    # 20260202 이종헌 신규: title/snippet/text 중 하나라도 must를 포함하지 않으면 버림(RSS 잡음 제거)
    filtered: List[DocItem] = []  # 신규: 필터된 문서
    for d in docs:
        hay = f"{d.title} {d.snippet} {d.text}".lower()  # 20260202 이종헌 신규: 검색 대상 텍스트
        if must_lower and must_lower not in hay:
            continue  # 신규: 회사명/검색어가 안 나오면 무관 기사로 간주
        filtered.append(d)

    # 20260202 이종헌 수정: 이후 로직은 filtered 기준으로 중복 제거
    uniq: List[DocItem] = []
    seen_url = set()
    for d in filtered:  # 20260202 이종헌 수정: docs -> filtered
        if d.url in seen_url:
            continue
        seen_url.add(d.url)
        uniq.append(d)

    logger.info("Merged docs=%d (unique)", len(uniq))  # 20260202 이종헌 수정: 필터/중복 제거 후 개수

    return uniq[: int(req.search.max_results or 20)]
