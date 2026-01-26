# app/services/rag_lookup.py
'''
B-1 규정/가이드 근거 조회(RAG) - 사이드 패널 전용 / 판정 영향 0
데모용: 로컬 파일(텍스트)에서 키워드 매칭으로 snippet 반환
※ 나중에 벡터DB/임베딩으로 교체하면 됨 (tool로 분리 유지)
'''

from __future__ import annotations
from pathlib import Path
from app.schemas import EsgRagLookupRequest, EsgRagLookupResponse, EsgRagSnippet
from app.utils.files import esg_get_repo_root

def _load_corpus() -> list[tuple[str, str]]:
    """
    data/rag/ 아래의 .txt/.md를 로드 (데모)
    파일이 없으면 하드코딩된 간단 문구로 fallback
    """
    repo = esg_get_repo_root()
    rag_dir = repo / "AI" / "apps" / "esg_api" / "data" / "rag"
    docs: list[tuple[str, str]] = []

    if rag_dir.exists():
        for p in rag_dir.glob("**/*"):
            if p.suffix.lower() in [".txt", ".md"]:
                try:
                    docs.append((p.name, p.read_text(encoding="utf-8")))
                except Exception:
                    pass

    if not docs:
        docs = [
            ("DEMO_GRI.md", "GRI: 에너지 사용량은 기간/단위/근거 문서가 명확해야 하며, 이상치는 원인과 보완 증빙 제시가 권장됩니다."),
            ("DEMO_IFRS_S2.md", "IFRS S2: 기후 관련 지표는 산정 근거와 데이터 품질(검증가능성)이 중요하며, 추정/불확실성은 명시해야 합니다."),
        ]
    return docs

def esg_rag_lookup(req: EsgRagLookupRequest) -> EsgRagLookupResponse:
    docs = _load_corpus()
    q = (req.query or f"{req.slot_name} {req.issue_code}").lower()

    snippets: list[EsgRagSnippet] = []
    for name, text in docs:
        t = text.lower()
        # 매우 단순한 키워드 매칭(데모용)
        if any(k in t for k in q.split()):
            excerpt = text[:220].replace("\n", " ")
            snippets.append(EsgRagSnippet(source=name, excerpt=excerpt))

    if not snippets:
        snippets = [EsgRagSnippet(source="DEMO", excerpt="관련 근거를 찾지 못했습니다. (데모: 문서 코퍼스 확장 필요)")]

    return EsgRagLookupResponse(
        slot_name=req.slot_name,
        issue_code=req.issue_code,
        snippets=snippets[:3],
        note="사이드 패널 참고용 근거 조회입니다. 메인 판정에는 사용되지 않습니다.",
    )