# app/llm/schemas.py
'''
LLM 강제 JSON 출력 스키마(Structured Outputs)
'''

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List

class EsgLLMSlotMapItem(BaseModel):
    file_id: str
    slot_name: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)

class EsgLLMSlottingOutput(BaseModel):
    slot_map: List[EsgLLMSlotMapItem]

class EsgLLMQuestionsOutput(BaseModel):
    questions: List[str] = Field(description="보완요청 문장 리스트(2~6개)")