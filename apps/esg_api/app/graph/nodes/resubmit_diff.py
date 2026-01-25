# app/graph/nodes/resubmit_diff.py
'''
A-3) 재제출 개선 비교 노드 (메인 시나리오 포함)
- 같은 draft_id의 이전 결과 JSON이 있으면 비교(diff)
- 데모 기준: outputs/{draft_id}_latest.json 저장, 다음 실행 시 비교
'''

from __future__ import annotations
import json
from pathlib import Path
from app.graph.state import EsgGraphState
from app.utils.files import esg_get_upload_dir

def _count_levels(issues: list[dict]) -> tuple[int, int]:
    fail = sum(1 for i in issues if i.get("level") == "FAIL")
    warn = sum(1 for i in issues if i.get("level") == "WARN")
    return fail, warn

def esg_resubmit_diff_node(state: EsgGraphState) -> EsgGraphState:
    draft_id = state.get("draft_id", "unknown")
    out_dir = esg_get_upload_dir()
    latest_path = out_dir / f"{draft_id}_latest.json"

    current_issues = state.get("issues", []) or []
    current_status = state.get("status", "OK")

    current_fail, current_warn = _count_levels(current_issues)
    current_codes = {i.get("code") for i in current_issues if i.get("code")}

    diff = {
        "has_previous": False,
        "previous_status": None,
        "current_status": current_status,
        "delta_fail": 0,
        "delta_warn": 0,
        "fixed_issues": [],
        "new_issues": [],
        "note": "",
    }

    if latest_path.exists():
        try:
            prev = json.loads(latest_path.read_text(encoding="utf-8"))
            prev_status = prev.get("status")
            prev_issues = prev.get("issues", []) or []
            prev_fail, prev_warn = _count_levels(prev_issues)
            prev_codes = {i.get("code") for i in prev_issues if i.get("code")}

            diff["has_previous"] = True
            diff["previous_status"] = prev_status
            diff["delta_fail"] = current_fail - prev_fail
            diff["delta_warn"] = current_warn - prev_warn
            diff["fixed_issues"] = sorted(list(prev_codes - current_codes))
            diff["new_issues"] = sorted(list(current_codes - prev_codes))
            diff["note"] = "이전 실행 결과와 비교한 개선/변경 내역입니다."
        except Exception:
            diff["note"] = "이전 결과 파일이 있으나 파싱 실패하여 비교를 생략했습니다."

    # 현재 결과 저장(다음 제출 비교용)
    try:
        latest_path.write_text(
            json.dumps(
                {
                    "draft_id": draft_id,
                    "status": current_status,
                    "issues": current_issues,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        diff["note"] = (diff["note"] + " (현재 결과 저장 실패)").strip()

    state["resubmit_diff"] = diff
    return state