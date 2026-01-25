# app/services/supplychain_predict.py
'''
지능형 공급망 분석 및 예측 서비스 (데모용 / 판정 영향 0)
- 입력: 현재 status + issues
- 출력: 리스크 레벨/드라이버/모니터링 권고
※ 데모는 룰/휴리스틱, 향후 Search/RAG/외부데이터로 확장
'''

from __future__ import annotations
from app.schemas import EsgSupplyChainPredictRequest, EsgSupplyChainPredictResponse

def esg_supplychain_predict(req: EsgSupplyChainPredictRequest) -> EsgSupplyChainPredictResponse:
    issues = req.issues or []
    status = req.current_status

    # 휴리스틱 점수
    score = 0.2
    drivers = []
    monitoring = []

    if status == "FAIL":
        score += 0.45
        drivers.append("제출 데이터 검증 FAIL 발생")
    elif status == "WARN":
        score += 0.25
        drivers.append("제출 데이터 검증 WARN 존재")

    codes = {i.code for i in issues if i.code}
    if "ANOMALY_SPIKE_RATIO" in codes:
        score += 0.20
        drivers.append("전력 사용량 급증 이상치 탐지")
        monitoring += ["전력비/에너지 단가 변동", "생산량/가동률 변화", "설비 증설/유지보수 이벤트"]

    if "MISSING_CODE_OF_CONDUCT" in codes or "CANNOT_VERIFY_APPROVAL_INFO" in codes:
        score += 0.10
        drivers.append("윤리/컴플라이언스 문서 승인정보 불확실")
        monitoring += ["윤리/준법 교육 이수 기록", "내부통제/감사 결과", "협력사 행동강령 최신화 주기"]

    # 정규화
    score = min(max(score, 0.0), 1.0)
    risk = "LOW" if score < 0.4 else ("MEDIUM" if score < 0.7 else "HIGH")

    # 중복 제거
    monitoring = list(dict.fromkeys(monitoring))[:6]

    return EsgSupplyChainPredictResponse(
        supplier_name=req.supplier_name,
        risk_level=risk,
        risk_score=score,
        drivers=drivers[:5],
        recommended_monitoring=monitoring,
        note="운영 참고용 예측 카드입니다(판정 영향 0). 외부 데이터 연동 시 정교화 가능합니다.",
    )