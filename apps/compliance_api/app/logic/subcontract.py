# app/logic/subcontract.py

# 하도급법 주요 체크리스트 (RAG 대용으로 프롬프트에 주입할 데이터)
SUBCONTRACT_RULES = [
    {
        "id": "RULE-01",
        "category": "대금지급",
        "description": "목적물 수령일로부터 60일 이내에 대금을 지급해야 한다.",
        "law": "하도급법 제13조(하도급대금의 지급 등)"
    },
    {
        "id": "RULE-02",
        "category": "부당결제",
        "description": "원청의 사정에 따라 대금 지급을 유보하거나 지연한다는 조항은 무효다.",
        "law": "하도급법 제3조(서면의 발급 및 보존)"
    },
    {
        "id": "RULE-03",
        "category": "기술자료",
        "description": "정당한 사유 없이 수급사업자의 기술자료를 본인 또는 제3자에게 제공하도록 요구해서는 안 된다.",
        "law": "하도급법 제12조의3(기술자료 제공 요구 금지 등)"
    }
]

def get_rules_text():
    """AI 프롬프트에 넣기 위해 텍스트로 변환"""
    text = "다음은 필수적으로 준수해야 할 하도급법 기준이다:\n"
    for rule in SUBCONTRACT_RULES:
        text += f"- {rule['law']}: {rule['description']}\n"
    return text