# app/graph/nodes/slotting.py
'''
2) 슬롯 매핑 노드
- 데모 파일 4개에 1:1 매핑이 "항상" 되도록 규칙 기반 우선
- 애매하면 LLM 보조(실패해도 데모가 깨지지 않게 fallback)
'''

from __future__ import annotations

import os
from typing import Optional, List
from pydantic import BaseModel, Field

from app.graph.state import EsgGraphState
from app.llm.openai_client import esg_try_llm_parse_structured
from app.llm.schemas import EsgLLMSlottingOutput


_ALLOWED_ITEMS = [
    "electricity_usage_2024",
    "electricity_usage_2025",
    "iso_45001",
    "code_of_conduct",
]

def _rule_based_slot(file_name: str, kind: str | None) -> Optional[str]:
    n = (file_name or "").lower()

    if kind == "XLSX":
        if "2024" in n:
            return "electricity_usage_2024"
        if "2025" in n:
            return "electricity_usage_2025"
        # 연도 누락 시 None으로 두고 LLM/후처리

    if kind == "PDF":
        # 데모는 PDF=ISO로 고정
        return "iso_45001"

    if kind == "IMAGE":
        # 데모는 IMAGE=행동강령 고정
        return "code_of_conduct"

    return None


def esg_slotting_node(state: EsgGraphState) -> EsgGraphState:
    files = state.get("files", []) or []
    slot_map: list[dict] = []
    unresolved = []

    # 1) 규칙 기반
    for f in files:
        fid = f.get("file_id")
        if not fid:
            continue
        slot = _rule_based_slot(f.get("file_name", ""), f.get("kind"))
        if slot:
            slot_map.append({
                "file_id": fid,
                "slot_name": slot,
                "reason": "rule-based mapping (demo fixed set)",
                "confidence": 0.98,
            })
        else:
            unresolved.append({
                "file_id": fid,
                "file_name": f.get("file_name"),
                "ext": f.get("ext"),
                "kind": f.get("kind"),
            })

    # 2) unresolved만 LLM 보조
    if unresolved:
        system = (
            "You are a strict JSON generator.\n"
            "Map each file to exactly one slot_name from allowed_items.\n"
            "Return ONLY valid JSON that matches the schema.\n"
            "Use ONLY file_name/ext/kind.\n"
        )
        user = (
            f"allowed_items = {_ALLOWED_ITEMS}\n"
            f"files = {unresolved}\n\n"
            "Output schema:\n"
            "{ slot_map: [ { file_id, slot_name, reason, confidence } ] }\n"
        )

        model = os.getenv("OPENAI_MODEL_SLOT", "gpt-5-mini")
        parsed = esg_try_llm_parse_structured(
            model=model,
            system=system,
            user=user,
            schema_model=EsgLLMSlottingOutput,
            temperature=0.1,
            max_output_tokens=500,
        )

        if parsed:
            for it in parsed.slot_map:
                slot_map.append({
                    "file_id": it.file_id,
                    "slot_name": it.slot_name,
                    "reason": it.reason,
                    "confidence": float(it.confidence),
                })
        else:
            # fallback: 연도 없는 전기 XLSX는 2025로 두되, confidence 낮게
            for uf in unresolved:
                slot_map.append({
                    "file_id": uf["file_id"],
                    "slot_name": "electricity_usage_2025",
                    "reason": "fallback (LLM unavailable) - assume latest year",
                    "confidence": 0.2,
                })

    # 3) 누락 방지(모든 file_id가 1개 슬롯을 갖게)
    mapped = {m["file_id"] for m in slot_map}
    for f in files:
        fid = f.get("file_id")
        if fid and fid not in mapped:
            slot_map.append({
                "file_id": fid,
                "slot_name": "electricity_usage_2025",
                "reason": "forced fill to avoid missing mapping",
                "confidence": 0.1,
            })

    state["slot_map"] = slot_map
    return state