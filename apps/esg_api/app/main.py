# app/main.py
'''
FastAPI 엔트리/라우팅
- POST /ai/agent/run : 메인 검증 플로우(메인 서비스)
- POST /ai/rag/lookup : B-1 규정/가이드 근거 조회(사이드 패널, 판정 영향 0)
- POST /ai/supplychain/predict : 지능형 공급망 분석/예측(사이드 서비스)
'''

from __future__ import annotations

from fastapi import FastAPI, UploadFile, File, Form
from app.schemas import (
    EsgRunResponse,
    EsgRagLookupRequest, EsgRagLookupResponse,
    EsgSupplyChainPredictRequest, EsgSupplyChainPredictResponse,
)
from app.utils.files import esg_save_uploads
from app.graph.build import esg_build_graph
from app.services.rag_lookup import esg_rag_lookup
from app.services.supplychain_predict import esg_supplychain_predict

app = FastAPI(title="ESG Supplier Validation AI (Demo)")

graph = esg_build_graph()  # 서버 시작 시 1회 compile 후 재사용


@app.post("/ai/agent/run", response_model=EsgRunResponse)
def esg_run_agent(
    draft_id: str = Form(...),
    files: list[UploadFile] = File(...),
):
    saved_files = esg_save_uploads(files)

    init_state = {
        "draft_id": draft_id,
        "files": saved_files,
        "slot_hint": None,

        # graph intermediate/output (초기화)
        "triage": {},
        "slot_map": [],
        "extracted": [],
        "issues": [],
        "questions": [],
        "summary_cards": [],
        "status": "OK",

        # 부가서비스용
        "anomaly_candidates": [],
        "resubmit_diff": None,
    }

    out = graph.invoke(init_state)

    # 응답 스키마와 100% 일치시키기
    return {
        "draft_id": out["draft_id"],
        "status": out["status"],
        "triage": out.get("triage", {}),
        "files": out.get("files", []),
        "slot_map": out.get("slot_map", []),
        "extracted": out.get("extracted", []),
        "issues": out.get("issues", []),

        # A-2 결과(요청서 문장)
        "questions": out.get("questions", []),

        # A-1 / A-3 결과
        "anomaly_candidates": out.get("anomaly_candidates", []),
        "resubmit_diff": out.get("resubmit_diff", None),

        "summary_cards": out.get("summary_cards", []),
    }


@app.post("/ai/rag/lookup", response_model=EsgRagLookupResponse)
def rag_lookup(req: EsgRagLookupRequest):
    # 판정 영향 0, 사이드 패널 전용
    return esg_rag_lookup(req)


@app.post("/ai/supplychain/predict", response_model=EsgSupplyChainPredictResponse)
def supplychain_predict(req: EsgSupplyChainPredictRequest):
    # 판정 영향 0, 운영 참고용 예측 카드
    return esg_supplychain_predict(req)