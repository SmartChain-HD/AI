# AI/apps/out_risk_api/app/search/rss.py

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import List

import httpx

from app.schemas.risk import DocItem, ExternalRiskDetectRequest
from app.search.rss_sources import RSS_FEEDS

from urllib.parse import urlparse  # 신규: RSS 아이템 출처 도메인 추출용

# 신규: RSS 파싱은 표준 라이브러리로만(KISS)
import xml.etree.ElementTree as ET

# 신규: 검색 가시화용 로깅
import logging
logger = logging.getLogger("out_risk.search")

# 신규: URL 인코딩(검색 RSS 생성용)
from urllib.parse import quote_plus  # 신규: google news rss query 인코딩

# 신규: alias 확장
from app.search.aliases import esg_expand_company_terms  # 신규: 회사명 별칭


def esg_hash_id(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]


# 신규: RSS pubDate(RFC822) 파싱 지원
from email.utils import parsedate_to_datetime  # 신규: 날짜 파싱 표준 유틸

def esg_safe_ymd(pub_text: str) -> str:
    s = (pub_text or "").strip()
    if not s:
        return ""

    # 신규: RSS 표준(pubDate) 우선 처리
    try:
        dt = parsedate_to_datetime(s)
        return dt.date().isoformat()
    except Exception:
        pass  # 수정: 실패하면 ISO 시도

    # 수정: ISO 형태 fallback
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return ""



def esg_search_rss(req: ExternalRiskDetectRequest) -> List[DocItem]:
    # 신규: 회사명/검색어 기반 RSS 검색 feed 생성
    def esg_build_rss_search_feeds(req: ExternalRiskDetectRequest) -> list[str]:
        # 신규: 기준 쿼리(비우면 회사명)
        base_q = (req.search.query or "").strip() or (req.company.name or "").strip()  # 신규: 검색어 우선
        if not base_q:  # 신규: 방어
            return []  # 신규: 없음

        # 신규: alias 확장
        terms = esg_expand_company_terms(base_q) or [base_q]  # 신규: 후보 용어

        # 신규: Google News RSS Search(무료 후보 수집)
        out: list[str] = []  # 신규: 결과 feed 목록
        for t in terms:  # 신규: 용어별 feed 생성
            q = quote_plus(t)  # 신규: URL 인코딩
            out.append(f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko")  # 신규: 한국 설정
        return out  # 신규: 반환

    # 수정: 고정 RSS_FEEDS + 검색 RSS 합치기
    feeds = list(RSS_FEEDS)  # 수정: 기존 피드
    feeds.extend(esg_build_rss_search_feeds(req))  # 신규: 회사명 검색 RSS 추가
    if not feeds:  # 수정: 검사 대상 변경
        return []  # 수정: 그대로

    items: List[DocItem] = []
    seen_url = set()

    max_total = int(req.search.max_results or 20)  # 신규: RSS 전체 결과 상한(전체 feed 합산)

    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        for feed_url in feeds:
            # 신규: 이미 충분히 모였으면 더 이상 RSS를 읽지 않음(빠른 응답)
            if len(items) >= max_total:  # 신규: 상한 도달 시 즉시 종료
                break
            try:
                r = client.get(feed_url)
                r.raise_for_status()
                xml = r.text
            except Exception as e:
                logger.warning("RSS fetch failed: %s (%s)", feed_url, str(e))
                continue

            try:
                root = ET.fromstring(xml)
                channel = root.find("channel")
                entries = channel.findall("item") if channel is not None else root.findall(".//item")
            except Exception as e:
                logger.warning("RSS parse failed: %s (%s)", feed_url, str(e))
                continue

            for it in entries:
                if len(items) >= max_total:  # 신규: 상한 도달 시 feed 내부도 즉시 종료
                    break

                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                pub = (it.findtext("pubDate") or "").strip()

                if not link or link in seen_url:
                    continue
                seen_url.add(link)

                doc_id = esg_hash_id(link)
                published_at = esg_safe_ymd(pub)
                
                src = urlparse(link).netloc.replace("www.", "") or "unknown"  # 신규: 출처를 기사 도메인으로 저장

                # 신규: 후보 수집이 목적이므로 snippet만 채워도 충분
                items.append(
                    DocItem(
                        doc_id=doc_id,
                        title=title or "untitled",
                        source=src,  # 수정: feed_url 대신 기사 도메인
                        published_at=published_at,
                        url=link,
                        text="",
                        snippet=title or "rss_item",
                    )
                )

    return items