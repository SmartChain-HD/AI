# app/graph/nodes/remediation.py
'''
A-2) 보완요청서 생성 노드 (메인 시나리오 포함)
- issues를 기반으로 "협력사에 요청할 문장" questions(list[str]) 생성
- LLM이 있어도 되고 없어도 되도록(데모 안정)
'''

from __future__ import annotations
import os
from app.graph.state import EsgGraphState
from app.llm.openai_client import esg_try_llm_parse_structured
from app.llm.schemas import EsgLLMQuestionsOutput

def _rule_questions(issues: list[dict]) -> list[str]:
    qs: list[str] = []
    # FAIL/WARN 중심으로 요청서 생성
    for it in issues:
        lvl = it.get("level")
        code = it.get("code")
        slot = it.get("slot_name") or "unknown"
        if lvl not in ["FAIL", "WARN"]:
            continue

        if code in ["ANOMALY_SPIKE_RATIO", "SPIKE_RATIO_WARN", "MISSING_BASELINE"]:
            qs.append(
                "전력 사용량 급증(10/12~10/19) 원인 확인을 위해 아래 자료를 추가 제출해 주세요: "
                "① 전기요금 고지서 원본(PDF) ② 계측기 교정 성적서(해당 기간) ③ 생산량/가동률 일별 또는 주간 데이터(XLSX/CSV)."
            )
        elif code in ["MISSING_CODE_OF_CONDUCT", "CANNOT_VERIFY_APPROVAL_INFO"]:
            qs.append(
                "행동강령/윤리 서약 문서의 최신 승인본을 제출해 주세요. "
                "승인일/결의 주체/버전 정보가 포함된 파일(이미지 또는 PDF)을 권장합니다."
            )
        elif code == "MISSING_ISO_45001":
            qs.append("ISO 45001 인증서(PDF)를 제출해 주세요. 유효기간/발급기관/인증번호가 보이도록 제출 바랍니다.")
        elif code == "MISSING_ELECTRICITY_2024":
            qs.append("전년 대비 비교를 위해 2024년 전기 사용량 파일(XLSX)을 추가 제출해 주세요.")
        else:
            qs.append(f"[보완요청] ({slot}) {it.get('message','이슈')} 관련 근거 자료를 추가 제출해 주세요.")

    # 최소 2개는 나오게(데모)
    return qs[:6] if qs else ["[보완요청] 추가 자료 제출을 요청드립니다."]


def esg_remediation_node(state: EsgGraphState) -> EsgGraphState:
    issues = state.get("issues", []) or []

    # 1) 룰 기반(항상 동작)
    base_qs = _rule_questions(issues)

    # 2) LLM로 문장 polish(실패해도 base 유지)
    model = os.getenv("OPENAI_MODEL_ISSUE", "gpt-5-mini")
    system = (
        "You are an enterprise compliance assistant.\n"
        "Rewrite the given draft requests into concise, polite Korean.\n"
        "Do NOT invent facts. Do NOT change the meaning.\n"
        "Return JSON with {questions:[...]} only.\n"
    )
    user = f"draft_questions = {base_qs}\nReturn improved questions (2~6)."

    parsed = esg_try_llm_parse_structured(
        model=model,
        system=system,
        user=user,
        schema_model=EsgLLMQuestionsOutput,
        temperature=0.2,
        max_output_tokens=450,
    )

    state["questions"] = parsed.questions[:6] if parsed else base_qs
    return state