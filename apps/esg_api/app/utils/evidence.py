# app/utils/evidence.py
'''
evidence_ref 유틸
EV::{kind}::{file_id}::{location} 포맷으로 근거 링크 문자열 생성
'''

from __future__ import annotations

def esg_make_evidence_ref(*, file_id: str, kind: str, location: str) -> str:
    # 단순/고정 포맷 (나중에 object로 확장 가능)
    return f"EV|{file_id}|{kind}|{location}"