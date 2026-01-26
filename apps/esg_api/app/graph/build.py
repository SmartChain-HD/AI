# app/graph/build.py
'''
LangGraph 빌더
메인 플로우 + (Day3~Day4) 부가서비스(A-2/A-1/A-3) 포함 노드 구성
'''

from __future__ import annotations
from langgraph.graph import StateGraph, END
from app.graph.state import EsgGraphState

from app.graph.nodes.triage import esg_triage_node
from app.graph.nodes.slotting import esg_slotting_node
from app.graph.nodes.extract import esg_extract_node
from app.graph.nodes.validate import esg_validate_node
from app.graph.nodes.evidence import esg_evidence_node

# A-2 (issues -> 보완요청서 문장)
from app.graph.nodes.remediation import esg_remediation_node

# A-1 (이상치 원인 후보)
from app.graph.nodes.anomaly_causes import esg_anomaly_causes_node

# A-3 (재제출 개선 비교)
from app.graph.nodes.resubmit_diff import esg_resubmit_diff_node

from app.graph.nodes.summary import esg_summary_node


def esg_build_graph():
    g = StateGraph(EsgGraphState)

    g.add_node("triage", esg_triage_node)
    g.add_node("slotting", esg_slotting_node)
    g.add_node("extract", esg_extract_node)
    g.add_node("validate", esg_validate_node)
    g.add_node("evidence", esg_evidence_node)

    # 부가서비스(메인 시나리오에 포함)
    g.add_node("remediation", esg_remediation_node)      # A-2
    g.add_node("anomaly_causes", esg_anomaly_causes_node)  # A-1
    g.add_node("resubmit_diff", esg_resubmit_diff_node)    # A-3

    g.add_node("summary", esg_summary_node)

    g.set_entry_point("triage")
    g.add_edge("triage", "slotting")
    g.add_edge("slotting", "extract")
    g.add_edge("extract", "validate")
    g.add_edge("validate", "evidence")

    g.add_edge("evidence", "remediation")
    g.add_edge("remediation", "anomaly_causes")
    g.add_edge("anomaly_causes", "resubmit_diff")

    g.add_edge("resubmit_diff", "summary")
    g.add_edge("summary", END)

    return g.compile()