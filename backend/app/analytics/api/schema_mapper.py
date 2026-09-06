"""
schema_mapper.py
Converts our internal networkx graph + risk_engine output into REAL
instances of Person 4's Pydantic models (schemas.py) -- not just dicts.

Why this matters: if our output doesn't conform to their contract, Pydantic
raises a validation error HERE, in our own test run, instead of failing
inside Person 4's FastAPI during integration or (worse) during the demo.

This is what api_interface.py calls -- Person 4 should never need to touch
analytics.py or risk_engine.py directly.
"""

import warnings

from graph.contracts.schemas import (
    GraphNode, GraphEdge, GraphResponse, NodeProperties, EdgeProperties,
    RiskBreakdown, EntityDetailResponse,
)
from graph.contracts.constants import normalize_entity_type, OFFICIAL_EDGE_TYPES
from graph.engine.risk_engine import compute_risk_breakdown
from graph.engine.analytics import detect_communities
from graph.engine.explanation import get_entity_evidence, get_explanation_path


def _build_node_properties(node_id: str, data: dict) -> NodeProperties:
    entity_type = data.get("type")
    display_name = data.get("name", node_id)
    props = NodeProperties(
        aliases=data.get("aliases", []),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )
    if entity_type == "Phone":
        props.number = display_name
    elif entity_type == "Vehicle":
        props.registration_number = display_name
        props.vehicle_type = data.get("vehicle_type")
    elif entity_type == "Location":
        props.name = display_name
        props.latitude = data.get("latitude")
        props.longitude = data.get("longitude")
    else:  # Person, Organization, and any unmapped type
        props.name = display_name
    return props


def build_graph_response(G) -> GraphResponse:
    """Full graph for the /api/graph style endpoint."""
    risk = compute_risk_breakdown(G)
    communities = detect_communities(G)

    nodes = []
    for node_id, data in G.nodes(data=True):
        entity_type = normalize_entity_type(data.get("type", ""))
        if entity_type not in {"Person", "Phone", "Location", "Vehicle", "Organization"}:
            warnings.warn(
                f"Node '{node_id}' has unrecognized type '{data.get('type')}' "
                f"(likely a stub from a dangling reference) -- skipping from GraphResponse. "
                f"Fix at the source (Person 1/2's extraction)."
            )
            continue

        nodes.append(GraphNode(
            id=node_id,
            label=data.get("name", node_id),
            type=entity_type,
            risk_score=risk.get(node_id, {}).get("overall_risk_score", 0.0),
            group=str(communities.get(node_id)) if node_id in communities else None,
            properties=_build_node_properties(node_id, data),
        ))

    valid_node_ids = {n.id for n in nodes}

    edges = []
    seen = set()
    skipped_dangling = 0
    for idx, (u, v, data) in enumerate(G.edges(data=True)):
        if u not in valid_node_ids or v not in valid_node_ids:
            # source/target was a stub node with an unrecognized type
            # (dangling reference from Person 1/2's extraction) -- can't
            # safely put this in the API response, would break frontend
            # graph rendering with an edge pointing at a node that isn't there.
            skipped_dangling += 1
            continue

        edge_type = data.get("edge_type")
        if edge_type not in OFFICIAL_EDGE_TYPES:
            # e.g. ASSOCIATED_WITH -- not in Person 4's official RelationshipType.
            # Kept in our internal graph for analytics, filtered out here.
            continue

        # Collapse duplicate calls/txns of the same type between the same
        # pair into one edge for the graph view (avoids 18 lines for a burst)
        collapse_key = (u, v, edge_type)
        if collapse_key in seen:
            continue
        seen.add(collapse_key)

        edges.append(GraphEdge(
            id=f"e{idx}",
            source=u,
            target=v,
            type=edge_type,
            confidence=data.get("confidence", 1.0),
            doc_id=data.get("source_doc_id") or data.get("source_doc"),
            properties=EdgeProperties(
                timestamp=data.get("timestamp"),
                duration=data.get("duration_sec") or data.get("duration"),
                amount=data.get("amount"),
                transaction_id=data.get("transaction_id"),
                role=data.get("role"),
                confidence=data.get("confidence", 1.0),
                source_doc=data.get("source_doc"),
                evidence=data.get("evidence"),
            ),
        ))

    if skipped_dangling:
        warnings.warn(
            f"Skipped {skipped_dangling} edge(s) pointing at entities missing "
            f"from the entities list. This is data loss in the API response -- "
            f"Person 1/2 need to fix their extraction so every referenced "
            f"entity ID has a full entity record."
        )

    return GraphResponse(nodes=nodes, edges=edges)


def build_entity_detail(G, entity_id: str) -> EntityDetailResponse | None:
    """For the /api/entity/{id} style endpoint."""
    if entity_id not in G.nodes:
        return None

    data = G.nodes[entity_id]
    risk = compute_risk_breakdown(G).get(entity_id)
    if risk is None:
        return None

    entity_type = normalize_entity_type(data.get("type", ""))
    if entity_type not in {"Person", "Phone", "Location", "Vehicle", "Organization"}:
        return None  # stub/unknown node, no valid EntityDetailResponse to build

    evidence = get_entity_evidence(G, entity_id)
    explanation = get_explanation_path(G, entity_id)

    return EntityDetailResponse(
        id=entity_id,
        name=data.get("name", entity_id),
        type=entity_type,
        overall_risk_score=risk["overall_risk_score"],
        risk_breakdown=RiskBreakdown(**risk["risk_breakdown"]),
        aliases=data.get("aliases", []),
        tags=risk["tags"],
        direct_connections_count=risk["direct_connections_count"],
        metadata={
            "case_ids": data.get("case_ids", []),
            "percentile_rank": risk["percentile_rank"],
            "recency_multiplier": risk["recency_multiplier"],
            "watchlist_reason": risk["watchlist_reason"],
            "bridge_score": risk["bridge_score"],
            "evidence": [e.model_dump() for e in evidence],
            "explanation_path": explanation,
        },
    )
