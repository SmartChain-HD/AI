# app/services/pipeline.py
from fastapi import UploadFile
from app.services.ocr_service import extract_text_from_image
from app.services.ai_service import analyze_risk
from app.models.response import ComplianceResult, Highlight

async def run_compliance_pipeline(file: UploadFile) -> ComplianceResult:
    # 1. 파일 데이터 읽기
    content = await file.read()
    
    # 2. Clova OCR로 텍스트 및 위치 추출
    full_text, ocr_data = await extract_text_from_image(content, file.filename)
    
    # 3. GPT-4o로 리스크 분석
    ai_result = await analyze_risk(full_text)
    
    # 4. 결과 매핑 및 반환
    return ComplianceResult(
        filename=file.filename,
        risk_score=ai_result.get("risk_score", 0),
        summary=ai_result.get("summary", ""),
        feedback_text=ai_result.get("feedback_text", ""),
        highlights=[] # 여기에 ocr_data를 매칭하는 로직이 들어갑니다.
    )