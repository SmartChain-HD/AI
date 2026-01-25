# app/graph/nodes/evidence.py
'''
5) 근거 링크 노드
Day3: extract에서 evidence_ref 생성했다고 가정 -> pass-through
'''

from __future__ import annotations
from app.graph.state import EsgGraphState

def esg_evidence_node(state: EsgGraphState) -> EsgGraphState:
    return state