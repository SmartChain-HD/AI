# app/graph/state.py
'''
LangGraph State 정의 (단일/정합 버전)
'''

from __future__ import annotations
from typing import TypedDict, Any, Literal, Optional

class EsgGraphState(TypedDict, total=False):
    # input
    draft_id: str
    files: list[dict[str, Any]]
    slot_hint: dict[str, Any] | None

    # intermediate
    triage: dict[str, Any]
    slot_map: list[dict[str, Any]]
    extracted: list[dict[str, Any]]
    issues: list[dict[str, Any]]        # schema와 1:1 (level/code/message/file_id/evidence_ref/slot_name/meta)
    questions: list[str]                # A-2 (문장)
    summary_cards: list[dict[str, Any]]

    # A-1 / A-3 결과
    anomaly_candidates: list[dict[str, Any]]
    resubmit_diff: Optional[dict[str, Any]]

    # output
    status: Literal["OK", "WARN", "FAIL"]