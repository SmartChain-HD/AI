#AI/apps/out_risk_api/app/schemas/risk.py

# 20260131 이종헌 신규: 외부 위험 감지 API 스키마(요구사항 동결 버전)
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Category = Literal[
    "SAFETY_ACCIDENT",
    "LEGAL_SANCTION",
    "LABOR_DISPUTE",
    "ENV_COMPLAINT",
    "FINANCE_LITIGATION",
]

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class Company(BaseModel):
    name: str
    biz_no: Optional[str] = None
    vendor_id: Optional[str] = None


class SearchConfig(BaseModel):
    enabled: bool = True
    query: str = ""
    max_results: int = 20
    sources: List[str] = Field(default_factory=lambda: ["news", "gov", "court", "public_db"])
    lang: str = "ko"


class DocItem(BaseModel):
    doc_id: str
    title: str
    source: str
    published_at: str  # YYYY-MM-DD
    url: str
    text: str = ""
    snippet: str = ""


class RagConfig(BaseModel):
    enabled: bool = True
    top_k: int = 6
    chunk_size: int = 800


class Options(BaseModel):
    strict_grounding: bool = True
    return_evidence_text: bool = True


class ExternalRiskDetectRequest(BaseModel):
    company: Company
    time_window_days: int = 90
    categories: List[Category] = Field(
        default_factory=lambda: [
            "SAFETY_ACCIDENT",
            "LEGAL_SANCTION",
            "LABOR_DISPUTE",
            "ENV_COMPLAINT",
            "FINANCE_LITIGATION",
        ]
    )
    search: SearchConfig = Field(default_factory=SearchConfig)
    documents: List[DocItem] = Field(default_factory=list)
    rag: RagConfig = Field(default_factory=RagConfig)
    options: Options = Field(default_factory=Options)


class Offset(BaseModel):
    start: int = 0
    end: int = 0


class EvidenceItem(BaseModel):
    doc_id: str
    source: str
    url: str
    quote: str
    offset: Offset


class Signal(BaseModel):
    category: Category
    severity: int = 0  # 0~5
    score: float = 0.0
    title: str = ""
    summary_ko: str = ""
    why: str = ""
    published_at: str = ""
    evidence: List[EvidenceItem] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    is_estimated: bool = False


class RetrievalMeta(BaseModel):
    search_used: bool = False
    rag_used: bool = False
    docs_count: int = 0
    top_sources: List[str] = Field(default_factory=list)


class ExternalRiskDetectResponse(BaseModel):
    external_risk_level: RiskLevel
    total_score: float
    signals: List[Signal] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    disclaimer: str = ""
    retrieval_meta: RetrievalMeta


# 20260202 이종헌 신규: 여러 협력사 일괄 감지 요청/응답 스키마(기존 단건 스키마 유지)
class ExternalRiskDetectBatchRequest(BaseModel):
    # 협력사 목록
    vendors: List[Company]  # 여러 회사

    # 20260202 이종헌 신규: 단건과 동일한 옵션을 공통 적용
    time_window_days: int = 90
    categories: List[Category] = Field(default_factory=lambda: [  # 기본 카테고리
        "SAFETY_ACCIDENT",
        "LEGAL_SANCTION",
        "LABOR_DISPUTE",
        "ENV_COMPLAINT",
        "FINANCE_LITIGATION",
    ])
    search: SearchConfig = Field(default_factory=SearchConfig)  # 검색 옵션
    rag: RagConfig = Field(default_factory=RagConfig)  # RAG 옵션
    options: Options = Field(default_factory=Options)  # 옵션

class BatchItem(BaseModel):
    company: Company  # 신규: 회사 정보
    # 신규: 성공 결과(성공 시만)
    result: Optional[ExternalRiskDetectResponse] = None 
    # 신규: 실패 사유(실패 시만)
    error: Optional[str] = None

class ExternalRiskDetectBatchResponse(BaseModel):
    # 신규: 배치 결과 목록(회사별)
    items: List[BatchItem] = Field(default_factory=list)