# app/services/ai_service.py
from openai import AsyncOpenAI
import json
from app.core.config import settings
from app.logic.subcontract import get_rules_text

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def analyze_risk(full_text: str):
    """
    GPT-4o를 이용해 OCR로 추출된 텍스트에서 법적 리스크를 분석합니다.
    """
    rules_context = get_rules_text()
    
    system_prompt = f"""
    당신은 대기업 컴플라이언스 전문 변호사 AI입니다.
    사용자가 업로드한 계약서 내용을 분석하여 '하도급법' 위반 소지가 있는 부분을 찾아내세요.
    
    [준수해야 할 법적 기준]
    {rules_context}
    
    반드시 아래 JSON 형식으로만 답변하세요. 다른 말은 하지 마세요.
    {{
        "risk_score": (0~100 사이 정수, 높을수록 위험),
        "summary": "전체적인 분석 요약 (한글)",
        "risks": [
            {{
                "text": "위반이 의심되는 계약서 내 문구 원문",
                "reason": "위반 사유 및 근거 법령"
            }}
        ],
        "feedback_text": "협력사에 보낼 정중한 수정 요청 메일 본문"
    }}
    """

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"다음 계약서 내용을 분석해줘:\n{full_text[:3000]}"} # 토큰 제한 고려
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)