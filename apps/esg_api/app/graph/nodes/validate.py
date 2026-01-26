# app/graph/nodes/validate.py
'''
4) 룰 검증 노드 (판정은 룰 기반 고정, LLM 관여 X)
- 2025 전기: spike_ratio로 FAIL/WARN/OK
- 2024 전기: 비교용으로만 사용(없어도 FAIL은 아님)
- ISO/행동강령: Day3는 존재 확인 + (향후) 유효성 확장
'''

from __future__ import annotations
from app.graph.state import EsgGraphState


def esg_validate_node(state: EsgGraphState) -> EsgGraphState:
    # 이유: triage issues를 덮어쓰면 안 됨 -> 누적
    issues: list[dict] = state.get("issues", []) or []
    extracted = state.get("extracted", []) or []

    # extracted를 slot별로 빠르게 찾기
    by_slot = {x.get("slot_name"): x for x in extracted if x.get("slot_name")}

    SPIKE_FAIL_RATIO = 1.8
    SPIKE_WARN_RATIO = 1.4
    MIN_BASELINE = 1e-6

    # -------------------------
    # E) 전력(2025) 이상치 판정
    # -------------------------
    e2025 = by_slot.get("electricity_usage_2025")
    if e2025:
        fid = e2025.get("file_id", "")
        ev = e2025.get("evidence_ref")
        spike_avg = float(e2025.get("value", 0.0))
        normal_avg = float((e2025.get("meta") or {}).get("normal_avg", 0.0))

        if normal_avg < MIN_BASELINE:
            issues.append({
                "level": "FAIL",
                "code": "MISSING_BASELINE",
                "message": "전력 급증 판정을 위한 기준 평균(normal_avg)이 없거나 0에 가깝습니다. Q4(10/01~12/31) 평시 구간 데이터가 포함되었는지 확인해 주세요.",
                "file_id": fid,
                "evidence_ref": ev,
                "slot_name": "electricity_usage_2025",
                "meta": {"spike_avg": spike_avg, "normal_avg": normal_avg},
            })
        else:
            ratio = spike_avg / normal_avg
            if ratio >= SPIKE_FAIL_RATIO:
                issues.append({
                    "level": "FAIL",
                    "code": "ANOMALY_SPIKE_RATIO",
                    "message": f"급증 구간 평균이 평시 대비 {ratio:.2f}배로 기준({SPIKE_FAIL_RATIO}배) 초과입니다.",
                    "file_id": fid,
                    "evidence_ref": ev,
                    "slot_name": "electricity_usage_2025",
                    "meta": {"spike_avg": spike_avg, "normal_avg": normal_avg, "spike_ratio": ratio},
                })
            elif ratio >= SPIKE_WARN_RATIO:
                issues.append({
                    "level": "WARN",
                    "code": "SPIKE_RATIO_WARN",
                    "message": f"급증 구간 평균이 평시 대비 {ratio:.2f}배로 경고 기준({SPIKE_WARN_RATIO}배) 이상입니다.",
                    "file_id": fid,
                    "evidence_ref": ev,
                    "slot_name": "electricity_usage_2025",
                    "meta": {"spike_avg": spike_avg, "normal_avg": normal_avg, "spike_ratio": ratio},
                })
            else:
                issues.append({
                    "level": "OK",
                    "code": "SPIKE_RATIO_OK",
                    "message": f"급증 구간 평균이 평시 대비 {ratio:.2f}배로 정상 범위입니다.",
                    "file_id": fid,
                    "evidence_ref": ev,
                    "slot_name": "electricity_usage_2025",
                    "meta": {"spike_avg": spike_avg, "normal_avg": normal_avg, "spike_ratio": ratio},
                })
    else:
        # 핵심 파일이 없으면 FAIL
        issues.append({
            "level": "FAIL",
            "code": "MISSING_ELECTRICITY_2025",
            "message": "2025 전기 사용량 파일이 누락되었습니다.",
            "file_id": "",
            "evidence_ref": None,
            "slot_name": "electricity_usage_2025",
            "meta": {},
        })

    # -------------------------
    # E) 전력(2024) 존재 체크(비교용)
    # -------------------------
    e2024 = by_slot.get("electricity_usage_2024")
    if not e2024:
        issues.append({
            "level": "WARN",
            "code": "MISSING_ELECTRICITY_2024",
            "message": "2024 전기 사용량 파일이 누락되었습니다. (전년 대비 비교(A-1) 정확도가 낮아질 수 있습니다)",
            "file_id": "",
            "evidence_ref": None,
            "slot_name": "electricity_usage_2024",
            "meta": {},
        })

    # -------------------------
    # S) ISO 45001 (Day3: 존재만 확인)
    # -------------------------
    iso = by_slot.get("iso_45001")
    if not iso:
        issues.append({
            "level": "WARN",
            "code": "MISSING_ISO_45001",
            "message": "ISO 45001 인증서(PDF)가 누락되었습니다. (S 항목 신뢰도 저하)",
            "file_id": "",
            "evidence_ref": None,
            "slot_name": "iso_45001",
            "meta": {},
        })
    else:
        issues.append({
            "level": "OK",
            "code": "ISO_EXISTS_OK",
            "message": "ISO 45001 문서가 제출되었습니다(존재 확인).",
            "file_id": iso.get("file_id", ""),
            "evidence_ref": iso.get("evidence_ref"),
            "slot_name": "iso_45001",
            "meta": {"note": "Day3: content parsing later"},
        })

    # -------------------------
    # G) 행동강령 (Day3: 존재만 확인 + '승인 정보 미확인' WARN)
    # -------------------------
    coc = by_slot.get("code_of_conduct")
    if not coc:
        issues.append({
            "level": "FAIL",
            "code": "MISSING_CODE_OF_CONDUCT",
            "message": "행동강령/윤리 서약 문서(이미지)가 누락되었습니다.",
            "file_id": "",
            "evidence_ref": None,
            "slot_name": "code_of_conduct",
            "meta": {},
        })
    else:
        issues.append({
            "level": "WARN",
            "code": "CANNOT_VERIFY_APPROVAL_INFO",
            "message": "행동강령 문서의 승인일/결의 주체 등 핵심 승인정보를 Day3에서 확인할 수 없습니다(OCR/파싱 전). 최신 승인본 정보가 포함된 파일 제출을 권장합니다.",
            "file_id": coc.get("file_id", ""),
            "evidence_ref": coc.get("evidence_ref"),
            "slot_name": "code_of_conduct",
            "meta": {"note": "Day3: OCR later"},
        })

    # overall status
    levels = [i["level"] for i in issues]
    state["status"] = "FAIL" if "FAIL" in levels else ("WARN" if "WARN" in levels else "OK")
    state["issues"] = issues
    return state