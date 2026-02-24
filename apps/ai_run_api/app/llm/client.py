"""OpenAI chat completions — text + vision 지원."""

from __future__ import annotations

import base64

from openai import AsyncOpenAI

from app.core.config import OPENAI_API_KEY, OPENAI_MODEL_HEAVY, OPENAI_MODEL_LIGHT, OPENAI_MODEL_VISION

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


async def ask_llm(
    system: str,
    user: str,
    *,
    heavy: bool = False,
    temperature: float = 0.0,
) -> str:
    """Text-only chat completion."""
    client = _get_client()
    model = OPENAI_MODEL_HEAVY if heavy else OPENAI_MODEL_LIGHT
    resp = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


async def ask_llm_vision(
    system: str,
    user_text: str,
    image_data: bytes,
    image_format: str = "png",
    *,
    temperature: float = 0.0,
) -> str:
    """Vision chat completion."""
    client = _get_client()
    b64 = base64.b64encode(image_data).decode()
    media_type = "image/jpeg" if image_format in ("jpg", "jpeg") else f"image/{image_format}"
    models: list[str] = []
    # Prefer dedicated vision model first; default is gpt-4o via config.
    for m in (OPENAI_MODEL_VISION, "gpt-4o", OPENAI_MODEL_LIGHT, OPENAI_MODEL_HEAVY):
        if m and m not in models:
            models.append(m)

    last_exc: Exception | None = None
    for model in models:
        try:
            resp = await client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{b64}"},
                            },
                        ],
                    },
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            last_exc = exc

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No vision model configured")
