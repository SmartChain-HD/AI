# app/models/response.py
from pydantic import BaseModel, Field
from typing import List, Optional

class Highlight(BaseModel):
    """문서 내 하이라이트할 위험 문구의 위치 정보"""
    text: str = Field(..., description="위험 문구 원문")
    reason: str = Field(..., description="위험하다고 판단한 이유")
    bbox: List[int] = Field(..., description="[x, y, w, h] 좌표")
    page: int = Field(1, description="페이지 번호")

class ComplianceResult(BaseModel):
    """최종 검토 결과 응답 모델"""
    filename: str
    risk_score: int = Field(..., ge=0, le=100, description="리스크 점수 (0-100)")
    summary: str = Field(..., description="전체 검토 요약")
    highlights: List[Highlight] = []
    feedback_text: str = Field(..., description="협력사 발송용 보완 요청 문구")