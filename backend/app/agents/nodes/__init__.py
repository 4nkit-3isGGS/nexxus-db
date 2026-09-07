"""
LangGraph Multi-Agent Nodes Package
-----------------------------------
Contains all specialized agent nodes for the Nexxus DB investigation system:
- Supervisor (Planning, Evaluation, Routing & Reporting)
- Graph Investigator (Neo4j Subgraph & Asset Discovery)
- Risk Analyst (Centrality, Profiling & Anomalies)
- Evidence Verifier (BSA §65B Cryptographic Audit)
- Financial & Cyber Analyst (Mule Accounts & Crypto Trails)
- Analysis Agent (Hypothesis Engine)
- Critic / Verifier Agent (Quality Gatekeeper)
- Report Agent (Dossier Compiler & API)
"""

from backend.app.agents.nodes.supervisor import (
    supervisor_plan_node,
    supervisor_evaluate_node,
    supervisor_report_node,
    route_next_step,
    create_investigation_graph,
    MAX_ITERATIONS,
)
from backend.app.agents.nodes.graph_investigator import graph_investigator_node
from backend.app.agents.nodes.risk_analyst import risk_analyst_node
from backend.app.agents.nodes.evidence_verifier import evidence_verifier_node
from backend.app.agents.nodes.financial_analyst import financial_analyst_node

__all__ = [
    "supervisor_plan_node",
    "supervisor_evaluate_node",
    "supervisor_report_node",
    "route_next_step",
    "create_investigation_graph",
    "MAX_ITERATIONS",
    "graph_investigator_node",
    "risk_analyst_node",
    "evidence_verifier_node",
    "financial_analyst_node",
]

