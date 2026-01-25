# app/api/v1/review.py
from fastapi import APIRouter, UploadFile, File
from app.services.pipeline import run_compliance_pipeline # 파이프라인 가져오기
from app.models.response import ComplianceResult

router = APIRouter()

@router.post("/upload", response_model=ComplianceResult)
async def upload_document(file: UploadFile = File(...)):
    # 껍데기 메시지 대신 진짜 분석 공정(Pipeline) 실행
    result = await run_compliance_pipeline(file)
    return result