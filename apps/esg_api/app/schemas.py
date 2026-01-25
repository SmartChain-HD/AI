# app/schemas.py
'''
요청/응답 스키마(=백엔드/UI와의 계약)
- 핵심: 노드 출력과 완전히 일치시켜 런타임 검증 에러 방지
'''

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional


# -------------------------
# Main Run Response
# -------------------------

class EsgFileInfo(BaseModel):
    file_id: str
    file_name: str
    file_path: str
    ext: str
    kind: Literal["XLSX", "PDF", "IMAGE", "UNKNOWN"]


class EsgSlotMapItem(BaseModel):
    file_id: str
    slot_name: str
    reason: str
    confidence: float


class EsgExtractedItem(BaseModel):
    file_id: str
    slot_name: str
    period_start: str
    period_end: str
    value: float
    unit: str
    evidence_ref: str
    meta: dict[str, Any] = Field(default_factory=dict)  # normal_avg/spike_ratio/yoy 등은 여기로


class EsgValidationIssue(BaseModel):
    level: Literal["OK", "WARN", "FAIL"]
    code: str
    message: str
    file_id: str
    evidence_ref: Optional[str] = None
    slot_name: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class EsgSummaryCard(BaseModel):
    audience: Literal["APPROVER", "PRIME"]
    lines: list[str]


class EsgAnomalyCandidate(BaseModel):
    slot_name: str
    title: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    suggested_evidence: list[str]  # 추가로 확인할 증빙 리스트


class EsgResubmitDiff(BaseModel):
    has_previous: bool
    previous_status: Optional[Literal["OK", "WARN", "FAIL"]] = None
    current_status: Literal["OK", "WARN", "FAIL"]
    delta_fail: int = 0
    delta_warn: int = 0
    fixed_issues: list[str] = Field(default_factory=list)    # code 목록
    new_issues: list[str] = Field(default_factory=list)      # code 목록
    note: str = ""


class EsgRunResponse(BaseModel):
    draft_id: str
    status: Literal["OK", "WARN", "FAIL"]
    triage: dict[str, Any]
    files: list[EsgFileInfo]
    slot_map: list[EsgSlotMapItem]
    extracted: list[EsgExtractedItem]
    issues: list[EsgValidationIssue]

    # A-2 보완요청서(문장) - 데모 안정: list[str]
    questions: list[str]

    # A-1 이상치 원인 후보
    anomaly_candidates: list[EsgAnomalyCandidate] = Field(default_factory=list)

    # A-3 재제출 개선 비교
    resubmit_diff: Optional[EsgResubmitDiff] = None

    summary_cards: list[EsgSummaryCard]


# -------------------------
# B-1 RAG Lookup (Side Panel)
# -------------------------

class EsgRagLookupRequest(BaseModel):
    slot_name: str
    issue_code: str
    query: str | None = None


class EsgRagSnippet(BaseModel):
    source: str
    excerpt: str


class EsgRagLookupResponse(BaseModel):
    slot_name: str
    issue_code: str
    snippets: list[EsgRagSnippet]
    note: str


# -------------------------
# Supply Chain Predict (Side Service)
# -------------------------

class EsgSupplyChainPredictRequest(BaseModel):
    supplier_name: str
    draft_id: str | None = None
    current_status: Literal["OK", "WARN", "FAIL"]
    issues: list[EsgValidationIssue] = Field(default_factory=list)


class EsgSupplyChainPredictResponse(BaseModel):
    supplier_name: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    risk_score: float = Field(ge=0.0, le=1.0)
    drivers: list[str] = Field(default_factory=list)
    recommended_monitoring: list[str] = Field(default_factory=list)
    note: str = ""