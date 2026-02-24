from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Category(str, Enum):
    SAFETY_ACCIDENT = "SAFETY_ACCIDENT"
    LEGAL_SANCTION = "LEGAL_SANCTION"
    GENERAL = "GENERAL"


class RagConfig(BaseModel):
    enabled: bool = False


class SearchConfig(BaseModel):
    time_window_days: int = Field(default=365, ge=30, le=3650)
    max_results: int = Field(default=30, ge=5, le=100)


class DocItem(BaseModel):
    doc_id: str
    title: str
    url: str
    source: str
    published_at: Optional[str] = None
    snippet: Optional[str] = None


class Signal(BaseModel):
    category: Category
    severity: int = Field(ge=0)
    score: float = Field(ge=0)
    title: str
    summary_ko: str
    why: str
    published_at: Optional[str] = None


class ExternalRiskDetectVendorResult(BaseModel):
    vendor: str
    external_risk_level: RiskLevel
    total_score: float = Field(ge=0)
    docs_count: int = Field(ge=0)
    reason_1line: Optional[str] = None
    reason_3lines: List[str] = Field(default_factory=list)
    evidence: List[DocItem] = Field(default_factory=list)


class ExternalRiskDetectBatchRequest(BaseModel):
    vendors: List[str]
    rag: RagConfig = Field(default_factory=RagConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)


class ExternalRiskDetectBatchResponse(BaseModel):
    results: List[ExternalRiskDetectVendorResult] = Field(default_factory=list)


class SearchPreviewRequest(BaseModel):
    vendor: str
    gdelt_url: Optional[str] = None
    rag: RagConfig = Field(default_factory=RagConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)


class SearchPreviewResponse(BaseModel):
    vendor: str
    used: bool
    docs_count: int
    documents: List[DocItem] = Field(default_factory=list)
