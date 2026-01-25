# app/graph/nodes/issue_reason.py
'''
6) 보완요청 문장 노드(더미)
issues code 기반 보완 질의 템플릿 문장 생성
'''

from __future__ import annotations

import os
from typing import List, Optional
from pydantic import BaseModel, Field

from app.graph.state import EsgGraphState
from app.llm.openai_client import esg_try_llm_parse_structured


# ---------- 1) Structured Outputs Schema ----------

class EsgClarificationQuestion(BaseModel):
    slot_name: str = Field(..., description="어떤 슬롯에 대한 보완요청인지")
    question: str = Field(..., description="협력사에게 요청할 보완 질문(한 문장)")
    priority: str = Field(..., description="HIGH|MEDIUM|LOW")
    evidence_ref: str = Field(..., description="근거 위치 참조(evidence_ref)")
    expected_file: str = Field(..., description="요청할 파일/증빙 예시(짧게)")


class EsgIssueReasonResponse(BaseModel):
    issue_reasoning: str = Field(..., description="이슈 해석 요약(3~6줄)")
    clarification_questions: List[EsgClarificationQuestion]


# ---------- 2) Node ----------

def esg_issue_reason_node(state: EsgGraphState) -> EsgGraphState:
    """
    6) issue_reason_node (LLM)
    - 입력: issues[] + evidence_ref
    - 출력: issue_reasoning + clarification_questions[]
    """
    issues = state.get("issues", []) or []
    extracted = state.get("extracted", []) or []

    # evidence_ref를 slot별로 쉽게 찾게 정리
    ev_by_slot = {}
    for x in extracted:
        sn = x.get("slot_name")
        if sn and x.get("evidence_ref"):
            ev_by_slot[sn] = x.get("evidence_ref")

    # LLM에 넘길 요약 payload (너무 길게 주지 말기)
    compact_issues = []
    for it in issues:
        compact_issues.append({
            "slot_name": it.get("slot_name"),
            "severity": it.get("severity"),
            "code": it.get("code"),
            "message": it.get("message"),
            "evidence_ref": it.get("evidence_ref") or ev_by_slot.get(it.get("slot_name")),
        })

    system = (
        "You are an enterprise compliance assistant.\n"
        "You DO NOT judge PASS/FAIL.\n"
        "You only explain issues and draft clarification questions.\n"
        "Return ONLY JSON that matches the schema.\n"
        "Keep questions actionable, requesting specific evidence files or missing fields.\n"
    )

    user = (
        f"issues = {compact_issues}\n\n"
        "Write:\n"
        "1) issue_reasoning: 3~6 lines, explain root causes and what is missing.\n"
        "2) clarification_questions: 2~5 items.\n"
        "Constraints:\n"
        "- priority must be one of HIGH|MEDIUM|LOW\n"
        "- evidence_ref must be present (use given).\n"
        "- expected_file should be concrete (e.g. 'electricity bill PDF', 'meter log XLSX', 'signed code-of-conduct image').\n"
    )

    model = os.getenv("OPENAI_MODEL_ISSUE", "gpt-5-mini")
    parsed: Optional[EsgIssueReasonResponse] = esg_try_llm_parse_structured(
        model=model,
        system=system,
        user=user,
        schema_model=EsgIssueReasonResponse,
        temperature=0.2,
        max_output_tokens=900,
    )

    if parsed:
        state["issue_reasoning"] = parsed.issue_reasoning
        state["clarification_questions"] = [q.model_dump() for q in parsed.clarification_questions]
    else:
        # fallback: 룰 기반 템플릿(데모 안정성)
        qs = []
        for it in compact_issues[:3]:
            sn = it.get("slot_name") or "unknown"
            ev = it.get("evidence_ref") or "EV-UNKNOWN"
            qs.append({
                "slot_name": sn,
                "question": f"[보완요청] {sn}: {it.get('message','이슈')} 관련 근거 자료(원본/상세내역)를 추가 제출해 주세요.",
                "priority": "HIGH" if it.get("severity") == "FAIL" else "MEDIUM",
                "evidence_ref": ev,
                "expected_file": "원본 청구서(PDF) 또는 원시로그(XLSX/CSV)",
            })
        state["issue_reasoning"] = "LLM unavailable. Generated fallback clarification questions based on issues."
        state["clarification_questions"] = qs

    return state