# AI/apps/out_risk_api/app/ui/streamlit_app.py

# 20260202 이종헌 수정: ESG 탭(협력사 외부 이슈 모니터링) Streamlit
# - 다수 협력사 일괄 감지 + 정렬 + 사유 3줄 요약
# - pyarrow/pandas 미사용(표는 markdown 렌더링)
# - "기사 찾았는지" 강력 확인: detect 메타 + (가능하면) search preview

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

try:
    import httpx
    _HTTPX_OK = True
except Exception:
    httpx = None
    _HTTPX_OK = False


# =========================
# 20260202 이종헌 신규: UI/렌더링 유틸
# =========================

def esg_setup_page() -> None:
    st.set_page_config(
        page_title="ESG 외부 이슈 모니터링(참고용)",
        layout="wide",
    )


def esg_escape_md(v: object) -> str:
    s = "" if v is None else str(v)
    return s.replace("|", "\\|").replace("\n", " ")


def esg_to_md_table(rows: List[Dict[str, Any]], max_rows: int = 50) -> str:
    if not rows:
        return "표시할 데이터가 없습니다."

    safe_rows = rows[: max(1, int(max_rows or 50))]
    cols = list(safe_rows[0].keys())

    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = []
    for r in safe_rows:
        body.append("| " + " | ".join(esg_escape_md(r.get(c, "")) for c in cols) + " |")

    return "\n".join([header, sep] + body)


def esg_render_table(rows: List[Dict[str, Any]], max_rows: int = 50) -> None:
    md = esg_to_md_table(rows, max_rows=max_rows)
    st.markdown(md)


def esg_notice_httpx() -> None:
    if not _HTTPX_OK:
        st.error("httpx가 설치되어 있지 않습니다. `pip install httpx` 후 다시 실행하세요.")
        st.stop()


# =========================
# 20260202 이종헌 수정: 입력 파서/페이로드 생성
# =========================

def esg_parse_vendors_json(raw: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
    if not (raw or "").strip():
        return [], "vendors JSON이 비어있습니다."

    try:
        obj = json.loads(raw)
    except Exception as e:
        return [], f"vendors JSON 파싱 실패: {e}"

    if not isinstance(obj, list):
        return [], "vendors JSON은 리스트([]) 형태여야 합니다."

    out: List[Dict[str, str]] = []
    for v in obj:
        if not isinstance(v, dict):
            continue
        name = (v.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "biz_no": (v.get("biz_no") or "").strip(),
                "vendor_id": (v.get("vendor_id") or "").strip(),
            }
        )

    if not out:
        return [], "vendors JSON에서 유효한 협력사(name 필수)를 찾지 못했습니다."

    return out, None


def esg_build_payload_for_vendor(
    vendor: Dict[str, str],
    time_window_days: int,
    categories: List[str],
    search_enabled: bool,
    search_query: str,
    max_results: int,
    sources: List[str],
    lang: str,
    rag_enabled: bool,
    top_k: int,
    chunk_size: int,
    strict_grounding: bool,
    return_evidence_text: bool,
) -> Dict[str, Any]:
    return {
        "company": {
            "name": vendor.get("name", ""),
            "biz_no": vendor.get("biz_no") or None,
            "vendor_id": vendor.get("vendor_id") or None,
        },
        "time_window_days": int(time_window_days),
        "categories": categories,
        "search": {
            "enabled": bool(search_enabled),
            "query": (search_query or "").strip(),
            "max_results": int(max_results),
            "sources": sources,
            "lang": (lang or "ko"),
        },
        "documents": [],
        "rag": {
            "enabled": bool(rag_enabled),
            "top_k": int(top_k),
            "chunk_size": int(chunk_size),
        },
        "options": {
            "strict_grounding": bool(strict_grounding),
            "return_evidence_text": bool(return_evidence_text),
        },
    }


# =========================
# 20260202 이종헌 신규: API 호출 (detect / search preview)
# =========================

def esg_call_api_json(url: str, payload: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
    esg_notice_httpx()
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


def esg_call_detect(api_base: str, payload: Dict[str, Any], timeout_s: float = 25.0) -> Dict[str, Any]:
    url = api_base.rstrip("/") + "/risk/external/detect"
    return esg_call_api_json(url, payload, timeout_s=timeout_s)


def esg_call_search_preview_maybe(api_base: str, payload: Dict[str, Any], timeout_s: float = 15.0) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    서버에 /risk/external/search/preview 가 없을 수 있으니:
    - 있으면 preview 결과를 반환
    - 없으면 None + 안내 메시지
    """
    url = api_base.rstrip("/") + "/risk/external/search/preview"
    try:
        data = esg_call_api_json(url, payload, timeout_s=timeout_s)
        return data, None
    except Exception as e:
        msg = str(e)
        # 엔드포인트 미구현/404이면 조용히 안내하고 스킵
        if "404" in msg or "Not Found" in msg:
            return None, "search preview 엔드포인트가 서버에 없습니다. (detect 메타로만 확인합니다)"
        return None, f"search preview 호출 실패: {e}"


# =========================
# 20260202 이종헌 수정: 결과 정리/정렬/품질체크
# =========================

def esg_level_rank(level: str) -> int:
    if level == "HIGH":
        return 2
    if level == "MEDIUM":
        return 1
    return 0


def esg_sort_key(row: Dict[str, Any]) -> Tuple[int, float]:
    return (esg_level_rank(str(row.get("external_risk_level", "LOW"))), float(row.get("total_score", 0) or 0))


def esg_reason_3lines(resp: Dict[str, Any]) -> str:
    sigs = resp.get("signals") or []
    if not sigs:
        return "외부 이슈 신호 없음"

    lines: List[str] = []
    for s in sigs[:3]:
        cat = s.get("category", "")
        summ = (s.get("summary_ko") or "").strip() or (s.get("why") or "").strip()
        if len(summ) > 90:
            summ = summ[:90] + "…"
        lines.append(f"- {cat}: {summ}")
    return "\n".join(lines)


def esg_detect_quality_summary(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    "검색이 실제 됐는지"를 메타로 강하게 판단
    """
    meta = resp.get("retrieval_meta") or {}
    docs_count = int(meta.get("docs_count") or 0)
    top_sources = meta.get("top_sources") or []

    search_used = bool(meta.get("search_used"))
    rag_used = bool(meta.get("rag_used"))

    ok = (docs_count > 0) and search_used
    return {
        "ok": ok,
        "search_used": search_used,
        "rag_used": rag_used,
        "docs_count": docs_count,
        "top_sources": ", ".join(top_sources[:5]) if isinstance(top_sources, list) else str(top_sources),
    }


# =========================
# 20260202 이종헌 수정: 상세 렌더
# =========================

def esg_render_vendor_detail(resp: Dict[str, Any]) -> None:
    st.subheader("협력사 상세(참고용)")

    st.markdown("**disclaimer**")
    st.write(resp.get("disclaimer", ""))

    st.markdown("**retrieval_meta**")
    st.json(resp.get("retrieval_meta") or {})

    sigs = resp.get("signals") or []
    if not sigs:
        st.info("표시할 signals가 없습니다.")
        return

    st.markdown("### Top signals")
    for i, s in enumerate(sigs[:10]):
        title = s.get("title") or "(no title)"
        score = s.get("score")
        cat = s.get("category")

        with st.expander(f"[{i+1}] {cat} | score={score} | {title}"):
            st.write("summary_ko:", s.get("summary_ko"))
            st.write("why:", s.get("why"))
            st.write("published_at:", s.get("published_at"))
            st.write("tags:", s.get("tags"))
            st.write("is_estimated:", s.get("is_estimated"))

            evs = s.get("evidence") or []
            if evs:
                st.markdown("**evidence**")
                for ev in evs:
                    st.write(
                        {
                            "doc_id": ev.get("doc_id"),
                            "source": ev.get("source"),
                            "url": ev.get("url"),
                            "offset": ev.get("offset"),
                        }
                    )
                    st.code(ev.get("quote") or "", language="text")


def esg_render_preview_docs(preview: Dict[str, Any], vendor_name: str) -> None:
    """
    preview 응답 스키마가 팀마다 다를 수 있어서:
    - docs / documents / items 중 존재하는 것을 찾아서 출력
    - 없다면 json 전체를 보여줌
    """
    st.markdown(f"### 검색 미리보기(문서 확인) - {vendor_name}")

    docs = None
    for k in ["docs", "documents", "items", "results"]:
        if isinstance(preview.get(k), list):
            docs = preview.get(k)
            break

    if not docs:
        st.info("preview 응답에서 문서 리스트를 찾지 못했습니다. (서버 응답 JSON을 그대로 표시합니다)")
        st.json(preview)
        return

    rows: List[Dict[str, Any]] = []
    for d in docs[:20]:
        if not isinstance(d, dict):
            continue
        rows.append(
            {
                "title": d.get("title", ""),
                "source": d.get("source", ""),
                "published_at": d.get("published_at", ""),
                "url": d.get("url", ""),
            }
        )

    esg_render_table(rows, max_rows=20)


# =========================
# 20260202 이종헌 수정: 메인 UI
# =========================

def esg_render() -> None:
    st.title("ESG 외부 이슈 모니터링(참고용)")
    st.caption("내가 관리하는 협력사들의 외부 이슈 신호를 참고용으로 요약/정렬해 보여줍니다. (메인 판정 변경 없음)")

    with st.sidebar:
        st.header("실행 설정")

        api_base = st.text_input("API Base URL", value="http://localhost:8000")
        time_window_days = st.number_input("time_window_days", min_value=1, max_value=3650, value=90, step=1)

        st.divider()
        st.header("카테고리(ESG 외부 위험 신호)")
        category_all = [
            "SAFETY_ACCIDENT",
            "LEGAL_SANCTION",
            "LABOR_DISPUTE",
            "ENV_COMPLAINT",
            "FINANCE_LITIGATION",
        ]
        categories = st.multiselect("categories", options=category_all, default=category_all)

        st.divider()
        st.header("SEARCH")
        search_enabled = st.toggle("search.enabled", value=True)
        search_query = st.text_input("search.query (비우면 회사명 사용)", value="")
        max_results = st.number_input("search.max_results", min_value=1, max_value=100, value=20, step=1)
        sources_all = ["news", "gov", "court", "public_db"]
        sources = st.multiselect("search.sources", options=sources_all, default=["news"])
        lang = st.selectbox("search.lang", options=["ko", "en"], index=0)

        st.divider()
        st.header("RAG (Chroma)")
        rag_enabled = st.toggle("rag.enabled", value=True)
        top_k = st.number_input("rag.top_k", min_value=1, max_value=50, value=6, step=1)
        chunk_size = st.number_input("rag.chunk_size", min_value=200, max_value=4000, value=800, step=50)

        st.divider()
        st.header("OPTIONS")
        strict_grounding = st.toggle("options.strict_grounding", value=True)
        return_evidence_text = st.toggle("options.return_evidence_text", value=True)

        st.divider()
        st.header("협력사 목록(vendors)")
        example_vendors = [
            {"name": "SK하이닉스", "biz_no": "", "vendor_id": ""},
            {"name": "삼성SDI", "biz_no": "", "vendor_id": ""},
            {"name": "SK이노베이션", "biz_no": "", "vendor_id": ""},
        ]
        vendors_raw = st.text_area(
            "vendors JSON (리스트)",
            value=json.dumps(example_vendors, ensure_ascii=False, indent=2),
            height=220,
        )

        vendors, v_err = esg_parse_vendors_json(vendors_raw)
        if v_err:
            st.error(v_err)

        st.divider()
        st.header("실행 버튼")
        run_preview_first = st.toggle("먼저 search preview로 문서 확인", value=True)
        run_all = st.button("일괄 감지 실행", type="primary", disabled=bool(v_err))

    left, right = st.columns([1.25, 1.0])

    if "esg_results" not in st.session_state:
        st.session_state["esg_results"] = []
    if "esg_previews" not in st.session_state:
        st.session_state["esg_previews"] = {}

    if run_all:
        esg_notice_httpx()

        results: List[Dict[str, Any]] = []
        previews: Dict[str, Any] = {}
        errors: List[str] = []

        with st.spinner("협력사 외부 이슈 감지 실행 중..."):
            for v in vendors:
                name = v.get("name", "").strip()
                if not name:
                    continue

                payload = esg_build_payload_for_vendor(
                    vendor=v,
                    time_window_days=int(time_window_days),
                    categories=categories or category_all,
                    search_enabled=bool(search_enabled),
                    search_query=search_query.strip(),
                    max_results=int(max_results),
                    sources=sources or ["news"],
                    lang=lang,
                    rag_enabled=bool(rag_enabled),
                    top_k=int(top_k),
                    chunk_size=int(chunk_size),
                    strict_grounding=bool(strict_grounding),
                    return_evidence_text=bool(return_evidence_text),
                )

                # (선택) 검색 문서가 실제로 잡히는지 먼저 확인
                if run_preview_first and search_enabled:
                    pv, pv_err = esg_call_search_preview_maybe(api_base, payload, timeout_s=12.0)
                    if pv is not None:
                        previews[name] = pv
                    elif pv_err:
                        previews[name] = {"_error": pv_err}

                # detect 실행
                try:
                    resp = esg_call_detect(api_base, payload, timeout_s=25.0)
                    qsum = esg_detect_quality_summary(resp)

                    row = {
                        "vendor_name": name,
                        "external_risk_level": resp.get("external_risk_level"),
                        "total_score": float(resp.get("total_score", 0) or 0),
                        "reason_3lines": esg_reason_3lines(resp),
                        "docs_ok": "OK" if qsum["ok"] else "WARN",
                        "docs_count": qsum["docs_count"],
                        "top_sources": qsum["top_sources"],
                        "_raw": resp,
                    }
                    results.append(row)
                except Exception as e:
                    errors.append(f"{name}: {e}")

        results_sorted = sorted(results, key=esg_sort_key, reverse=True)
        st.session_state["esg_results"] = results_sorted
        st.session_state["esg_previews"] = previews

        if errors:
            with left:
                st.warning("일부 협력사 실행 실패")
                for msg in errors:
                    st.write(msg)

    results_view: List[Dict[str, Any]] = st.session_state.get("esg_results", [])
    previews_view: Dict[str, Any] = st.session_state.get("esg_previews", {})

    with left:
        st.subheader("협력사 외부 이슈 리스트(참고용)")
        st.caption("정렬: 위험도(HIGH>MEDIUM>LOW) → total_score 내림차순 / 사유는 최대 3줄 요약")

        if not results_view:
            st.info("좌측에서 '일괄 감지 실행'을 누르면 결과가 표시됩니다.")
        else:
            table_rows = []
            for r in results_view:
                table_rows.append(
                    {
                        "협력사": r.get("vendor_name"),
                        "외부위험도": r.get("external_risk_level"),
                        "점수": r.get("total_score"),
                        "문서확인": f"{r.get('docs_ok')} (docs={r.get('docs_count')})",
                        "상위출처": r.get("top_sources"),
                        "사유(3줄)": r.get("reason_3lines"),
                    }
                )
            esg_render_table(table_rows, max_rows=50)

            vendor_names = [r.get("vendor_name") for r in results_view]
            selected = st.selectbox("우측 상세로 볼 협력사 선택", options=vendor_names, index=0)

    with right:
        if results_view:
            picked = None
            for r in results_view:
                if r.get("vendor_name") == selected:
                    picked = r
                    break

            if not picked:
                st.info("선택된 협력사의 상세 데이터를 찾지 못했습니다.")
                return

            raw = picked.get("_raw") or {}

            top = st.columns(3)
            top[0].metric("협력사", picked.get("vendor_name"))
            top[1].metric("external_risk_level", raw.get("external_risk_level", ""))
            top[2].metric("total_score", raw.get("total_score", 0))

            st.markdown("### 사유(3줄)")
            st.text(picked.get("reason_3lines") or "")

            # (가능하면) search preview 문서 목록을 같이 보여줌
            pv = previews_view.get(selected)
            if isinstance(pv, dict):
                st.divider()
                if pv.get("_error"):
                    st.warning(str(pv.get("_error")))
                else:
                    esg_render_preview_docs(pv, vendor_name=selected)

            st.divider()
            esg_render_vendor_detail(raw)


def esg_main() -> None:
    esg_setup_page()
    esg_render()


if __name__ == "__main__":
    esg_main()
