# app/graph/nodes/summary.py
'''
7) 요약 카드 노드
- 결재자/원청용 3~5줄 요약
- A-2/A-1/A-3 결과를 요약에 반영(데모 임팩트)
'''

from __future__ import annotations
from app.graph.state import EsgGraphState

def esg_summary_node(state: EsgGraphState) -> EsgGraphState:
    status = state.get("status", "OK")
    issues = state.get("issues", []) or []
    qs = state.get("questions", []) or []
    candidates = state.get("anomaly_candidates", []) or []
    diff = state.get("resubmit_diff")

    fail_cnt = sum(1 for i in issues if i.get("level") == "FAIL")
    warn_cnt = sum(1 for i in issues if i.get("level") == "WARN")

    top_candidate = candidates[0]["title"] if candidates else "N/A"

    diff_line = "재제출 비교: 이전 이력 없음"
    if diff and diff.get("has_previous"):
        diff_line = f"재제출 비교: FAIL Δ{diff.get('delta_fail',0)}, WARN Δ{diff.get('delta_warn',0)}"

    cards = [
        {
            "audience": "APPROVER",
            "lines": [
                f"검증 상태: {status} (FAIL {fail_cnt} / WARN {warn_cnt})",
                "메인 이슈: 2025 전력 급증(10/12~10/19) 및 문서 승인정보 미확인(행동강령).",
                f"A-2 보완요청서 자동 생성: {len(qs)}개 문장",
                f"A-1 이상치 원인 후보(예): {top_candidate}",
                diff_line,
            ],
        },
        {
            "audience": "PRIME",
            "lines": [
                f"제출 검증 결과: {status}",
                "근거(evidence_ref) 기반으로 이슈를 추적할 수 있습니다.",
                "보완요청이 자동 생성되어 협력사에 즉시 요청 가능합니다(A-2).",
                "재제출 시 개선 비교가 자동으로 제공됩니다(A-3).",
            ],
        },
    ]
    state["summary_cards"] = cards
    return state