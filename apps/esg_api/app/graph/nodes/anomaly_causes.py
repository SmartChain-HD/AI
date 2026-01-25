# app/graph/nodes/anomaly_causes.py
'''
A-1) 이상치 원인 후보 자동 생성 노드 (메인 시나리오 포함)
- 입력: (2025 전력 이상치) + (가능하면 2024 전력)
- 출력: 후보 리스트 + 추가 증빙 체크리스트
- 원칙: '단정' 금지, '가능한 후보'만 제시
'''

from __future__ import annotations
from app.graph.state import EsgGraphState

def esg_anomaly_causes_node(state: EsgGraphState) -> EsgGraphState:
    extracted = state.get("extracted", []) or []
    by_slot = {x.get("slot_name"): x for x in extracted if x.get("slot_name")}

    e2025 = by_slot.get("electricity_usage_2025")
    e2024 = by_slot.get("electricity_usage_2024")

    candidates: list[dict] = []

    if not e2025:
        state["anomaly_candidates"] = []
        return state

    ratio = float((e2025.get("meta") or {}).get("spike_ratio", 0.0))
    spike_avg = float(e2025.get("value", 0.0))
    normal_avg = float((e2025.get("meta") or {}).get("normal_avg", 0.0))

    # 전년 대비(YoY) 참고치: 2024도 있으면 같은 방식으로 ratio 산출해서 비교
    yoy_note = ""
    if e2024:
        ratio_2024 = float((e2024.get("meta") or {}).get("spike_ratio", 0.0))
        if ratio_2024 > 0:
            yoy_note = f"참고: 2024 동일 구간 spike_ratio={ratio_2024:.2f}, 2025={ratio:.2f}"

    # ratio가 의미 있을 때만 후보 생성
    if ratio >= 1.4:
        candidates.append({
            "slot_name": "electricity_usage_2025",
            "title": "생산량 증가/가동률 상승",
            "confidence": 0.55,
            "rationale": f"급증 구간 평균({spike_avg:.0f})이 평시({normal_avg:.0f}) 대비 {ratio:.2f}배로 상승. {yoy_note}".strip(),
            "suggested_evidence": [
                "생산량/가동률 일별 데이터(XLSX/CSV)",
                "설비 가동 로그(PLC/설비 로그)",
                "근무/교대 편성표(연장 가동 여부)",
            ],
        })
        candidates.append({
            "slot_name": "electricity_usage_2025",
            "title": "설비 증설/신규 라인 가동",
            "confidence": 0.45,
            "rationale": f"특정 기간(10/12~10/19)에 집중된 상승 패턴은 신규 설비 가동/라인 변경과도 일치할 수 있음. {yoy_note}".strip(),
            "suggested_evidence": [
                "설비 도입/설치 내역(계약/검수 문서)",
                "설비 시운전 기록",
                "에너지 사용 설비별 분해 데이터(가능 시)",
            ],
        })
        candidates.append({
            "slot_name": "electricity_usage_2025",
            "title": "계측기/검침 오류 또는 단위·기간 착오",
            "confidence": 0.50,
            "rationale": f"급증 비율이 크고(={ratio:.2f}) 데이터 입력/계량 과정 오류 가능성도 배제 불가. {yoy_note}".strip(),
            "suggested_evidence": [
                "계측기 교정 성적서(해당 기간)",
                "전기요금 고지서 원본(PDF)",
                "검침값 원시 로그(계량기/EMS 로그)",
            ],
        })

    state["anomaly_candidates"] = candidates
    return state