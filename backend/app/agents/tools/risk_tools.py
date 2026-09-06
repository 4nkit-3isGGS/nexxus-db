"""
LangGraph Agent Tools: Risk Analytics Boundary 
------------------------------------------------------------------
Exposes algorithmic risk scoring, network centrality, community detection,
and forensic anomaly detection (money laundering loops, call bursts, cross-case links)
to the multi-agent investigation system.

Integrates with Arnish's analytics package (backend.app.analytics).
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.tools import tool

import backend.app.analytics  # Initializes 'graph' namespace alias
from backend.app.analytics.api.api_interface import get_entity_detail
from backend.app.analytics.engine.analytics import (
    compute_centrality,
    detect_communities,
    detect_circular_transactions,
    detect_call_bursts,
    detect_cross_case_entities,
)
from backend.app.analytics.data_sources.graph_loader import load_graph
from backend.app.analytics.data_sources.mock_graph import build_mock_graph


def safe_load_graph():
    """Safely loads graph from configured source (Neo4j/JSON),

    falling back to synthetic mock graph if the live database is offline.
    """
    try:
        return load_graph()
    except Exception as e:
        print(f"[Risk Tools Warning] Live graph load failed ({e}), falling back to mock graph.")
        return build_mock_graph()


class GetRiskScoreInput(BaseModel):
    """Input schema for fetching comprehensive risk metrics for an entity."""
    entity_id: str = Field(
        ...,
        description="Unique identifier or name of the entity to score (e.g., 'P001', 'Rahul').",
        min_length=1,
    )


@tool("get_risk_score", args_schema=GetRiskScoreInput)
def get_risk_score_tool(entity_id: str) -> Dict[str, Any]:
    """Fetches the algorithmic risk score and detailed 6-factor risk breakdown for an entity.

    Use this tool to evaluate a suspect's threat level. Returns:
    - overall_risk_score: Normalized 0-100 criminal risk score.
    - risk_level: Categorical assessment (HIGH >= 70, MEDIUM >= 40, LOW < 40).
    - risk_breakdown: Sub-scores for degree centrality, PageRank (kingpin likelihood),
      betweenness centrality (broker role), call frequency bursts, cross-case history,
      and financial anomalies (mule/layering activity).
    - tags: Behavioral tags (e.g., 'High Risk', 'Key Broker', 'Vehicle Anomaly').

    Args:
        entity_id: Target entity identifier.

    Returns:
        Structured dictionary with risk score, breakdown, and tags.
    """
    clean_id = entity_id.strip()
    if not clean_id:
        return {
            "found": False,
            "overall_risk_score": 0.0,
            "error": "Entity ID cannot be empty."
        }

    try:
        detail = get_entity_detail(clean_id)
    except Exception:
        # If default loader fails, retry using safe fallback graph
        G = safe_load_graph()
        from backend.app.analytics.api.schema_mapper import build_entity_detail
        detail = build_entity_detail(G, clean_id)

    if detail is None:
        return {
            "entity_id": clean_id,
            "found": False,
            "overall_risk_score": 0.0,
            "message": f"Entity '{clean_id}' was not found in the risk analytics engine."
        }

    score = detail.overall_risk_score
    if score >= 70.0:
        level = "HIGH"
    elif score >= 40.0:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "entity_id": detail.id,
        "name": detail.name,
        "type": detail.type,
        "found": True,
        "overall_risk_score": round(score, 1),
        "risk_level": level,
        "risk_breakdown": detail.risk_breakdown.model_dump(),
        "tags": detail.tags,
        "direct_connections_count": detail.direct_connections_count,
    }



class GetCentralityInput(BaseModel):
    """Input schema for identifying top influential actors and communication brokers."""
    top_n: int = Field(
        default=5,
        description="Number of top ranked entities to return (bounded between 1 and 25).",
        ge=1,
        le=25,
    )
    metric: Literal["pagerank", "betweenness", "all"] = Field(
        default="all",
        description="Metric to rank by: 'pagerank' (influential kingpins), 'betweenness' (bridge/brokers), or 'all'.",
    )


@tool("get_network_centrality", args_schema=GetCentralityInput)
def get_network_centrality_tool(top_n: int = 5, metric: str = "all") -> Dict[str, Any]:
    """Ranks network entities by graph centrality to identify kingpins and cross-cell brokers.

    Use this tool when you need to understand the leadership hierarchy or communication
    chokepoints across the entire criminal syndicate.

    Args:
        top_n: How many top individuals to return per metric (default: 5).
        metric: 'pagerank' for influence, 'betweenness' for brokers, or 'all'.

    Returns:
        Dictionary containing top ranked entities and their respective centrality scores.
    """
    bounded_n = max(1, min(top_n, 25))
    G = safe_load_graph()
    centrality_results = compute_centrality(G)

    sorted_pr = sorted(
        centrality_results.items(),
        key=lambda item: item[1].get("pagerank", 0.0),
        reverse=True,
    )[:bounded_n]

    sorted_bw = sorted(
        centrality_results.items(),
        key=lambda item: item[1].get("betweenness_centrality", 0.0),
        reverse=True,
    )[:bounded_n]

    response: Dict[str, Any] = {"count": bounded_n}

    if metric in ("pagerank", "all"):
        response["top_influential_kingpins"] = [
            {
                "entity_id": node,
                "pagerank": round(metrics.get("pagerank", 0.0), 4),
                "degree": round(metrics.get("degree_centrality", 0.0), 4),
            }
            for node, metrics in sorted_pr
        ]

    if metric in ("betweenness", "all"):
        response["top_communication_brokers"] = [
            {
                "entity_id": node,
                "betweenness": round(metrics.get("betweenness_centrality", 0.0), 4),
                "degree": round(metrics.get("degree_centrality", 0.0), 4),
            }
            for node, metrics in sorted_bw
        ]

    return response


class GetCommunitiesInput(BaseModel):
    """Input schema for detecting criminal syndicates and gang clusters."""
    entity_id: Optional[str] = Field(
        default=None,
        description="Optional entity ID (e.g., 'Rahul'). If specified, returns that entity's specific gang cluster and co-members.",
    )


@tool("get_communities", args_schema=GetCommunitiesInput)
def get_communities_tool(entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Detects closely knit criminal communities, syndicates, and operational cells.

    Uses community detection algorithms (Louvain/modularity) to partition the network
    into distinct criminal clusters. Can return either the whole syndicate breakdown
    or inspect which specific syndicate an individual suspect belongs to.

    Args:
        entity_id: Optional entity ID to inspect specific membership.

    Returns:
        Dictionary containing community clusters and member node IDs.
    """
    G = safe_load_graph()
    communities_dict = detect_communities(G)

    # Group members by community ID
    clusters: Dict[str, List[str]] = {}
    for node, comm_id in communities_dict.items():
        key = f"Syndicate_{comm_id}"
        clusters.setdefault(key, []).append(node)

    if entity_id:
        clean_id = entity_id.strip()
        comm_id = communities_dict.get(clean_id)
        if comm_id is None:
            return {
                "entity_id": clean_id,
                "found": False,
                "message": f"Entity '{clean_id}' was not assigned to any community.",
            }
        cluster_key = f"Syndicate_{comm_id}"
        members = clusters.get(cluster_key, [])
        return {
            "entity_id": clean_id,
            "found": True,
            "community_id": comm_id,
            "cluster_name": cluster_key,
            "total_members": len(members),
            "co_members": [m for m in members if m != clean_id],
        }

    return {
        "total_communities": len(clusters),
        "communities": [
            {"name": name, "member_count": len(members), "members": members}
            for name, members in clusters.items()
        ]
    }


# =========================================================================
# Tool 4: Forensic Anomaly Detection
# =========================================================================

class DetectAnomaliesInput(BaseModel):
    """Input schema for running forensic pattern detection."""
    anomaly_type: Literal["circular_transactions", "call_bursts", "cross_case", "all"] = Field(
        default="all",
        description="Type of anomaly: 'circular_transactions' (money laundering), 'call_bursts' (burner phones), 'cross_case' (repeat offenders), or 'all'.",
    )


@tool("detect_anomalies", args_schema=DetectAnomaliesInput)
def detect_anomalies_tool(anomaly_type: str = "all") -> Dict[str, Any]:
    """Scans the criminal network for suspicious forensic patterns.

    Detects:
    1. Circular Transactions: Money laundering round-tripping cycles (A -> B -> C -> A)
       with matching timestamps and amounts.
    2. Call Bursts: Intense telecommunication spikes (>= 10 calls/day) typical of burner SIMs.
    3. Cross-Case Entities: Key entities appearing across multiple separate crime incident FIRs.

    Args:
        anomaly_type: Filter by 'circular_transactions', 'call_bursts', 'cross_case', or 'all'.

    Returns:
        Structured report of all detected criminal anomalies.
    """
    G = safe_load_graph()
    report: Dict[str, Any] = {"anomaly_type": anomaly_type}

    if anomaly_type in ("circular_transactions", "all"):
        cycles = detect_circular_transactions(G, max_cycle_len=4)
        report["circular_transactions"] = {
            "count": len(cycles),
            "cycles": cycles,
        }

    if anomaly_type in ("call_bursts", "all"):
        bursts = detect_call_bursts(G, threshold_per_day=10)
        report["call_bursts"] = {
            "count": len(bursts),
            "bursts": bursts,
        }

    if anomaly_type in ("cross_case", "all"):
        cross_cases = detect_cross_case_entities(G)
        report["cross_case_entities"] = {
            "count": len(cross_cases),
            "entities": cross_cases,
        }

    return report



# Exported Tool Registry

RISK_TOOLS = [
    get_risk_score_tool,
    get_network_centrality_tool,
    get_communities_tool,
    detect_anomalies_tool,
]