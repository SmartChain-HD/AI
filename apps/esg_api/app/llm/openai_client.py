# app/llm/openai_client.py
'''
OpenAI Structured Outputs 파서(단일 파일로 통일)
- 실패 시 None 반환하는 wrapper 제공
'''

from __future__ import annotations

import os
from typing import Type, TypeVar, Optional
from pydantic import BaseModel, ValidationError
from openai import OpenAI

T = TypeVar("T", bound=BaseModel)


def esg_get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")
    return OpenAI(api_key=api_key)


def esg_llm_parse_structured(
    *,
    model: str,
    system: str,
    user: str,
    schema_model: Type[T],
    temperature: float = 0.2,
    max_output_tokens: int = 900,
) -> T:
    client = esg_get_openai_client()
    resp = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        text_format=schema_model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    parsed = getattr(resp, "output_parsed", None)
    if parsed is None:
        raise RuntimeError("LLM parse failed: output_parsed is None")
    return parsed


def esg_try_llm_parse_structured(
    *,
    model: str,
    system: str,
    user: str,
    schema_model: Type[T],
    temperature: float = 0.2,
    max_output_tokens: int = 900,
) -> Optional[T]:
    try:
        return esg_llm_parse_structured(
            model=model,
            system=system,
            user=user,
            schema_model=schema_model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    except (ValidationError, Exception):
        return None