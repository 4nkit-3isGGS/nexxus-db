"""Agent Tools Package for Nexxus DB Multi-Agent Criminal Investigation Platform."""

from backend.app.agents.tools.graph_tools import (
    GRAPH_TOOLS,
    get_entity_tool,
    get_neighbors_tool,
    get_subgraph_tool,
    get_shortest_path_tool,
    search_entities_tool,
)
from backend.app.agents.tools.risk_tools import (
    RISK_TOOLS,
    get_risk_score_tool,
    get_network_centrality_tool,
    get_communities_tool,
    detect_anomalies_tool,
)
from backend.app.agents.tools.evidence_tools import (
    EVIDENCE_TOOLS,
    get_relationship_evidence_tool,
    verify_evidence_integrity_tool,
    generate_evidence_hash_tool,
)

ALL_INVESTIGATION_TOOLS = GRAPH_TOOLS + RISK_TOOLS + EVIDENCE_TOOLS

__all__ = [
    # Tool Registries
    "GRAPH_TOOLS",
    "RISK_TOOLS",
    "EVIDENCE_TOOLS",
    "ALL_INVESTIGATION_TOOLS",
    # Graph Boundary Tools
    "get_entity_tool",
    "get_neighbors_tool",
    "get_subgraph_tool",
    "get_shortest_path_tool",
    "search_entities_tool",
    # Risk Analytics Boundary Tools
    "get_risk_score_tool",
    "get_network_centrality_tool",
    "get_communities_tool",
    "detect_anomalies_tool",
    # Evidence & BSA §65B Tools
    "get_relationship_evidence_tool",
    "verify_evidence_integrity_tool",
    "generate_evidence_hash_tool",
]
