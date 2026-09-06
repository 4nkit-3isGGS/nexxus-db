"""
schemas.py
Local copy of Person 4's official backend contract (pasted 2026-08-29).
DO NOT EDIT casually -- this defines what Person 4's FastAPI actually
accepts/returns. If it changes on their end, update this file to match,
don't diverge silently.

We import these classes and construct real instances of them in
schema_mapper.py before serializing -- so if our output doesn't conform,
Pydantic raises a validation error HERE, in our own testing, instead of
failing inside Person 4's API during integration/demo.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EntityType = Literal["Person", "Phone", "Location", "Vehicle", "Organization"]
RelationshipType = Literal["CALLED", "TRANSACTED_WITH", "PRESENT_AT", "OWNS_VEHICLE", "MEMBER_OF", "OWNS_PHONE"]


class NodeProperties(BaseModel):
    name: str | None = None
    normalized_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    number: str | None = None
    normalized_number: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    registration_number: str | None = None
    vehicle_type: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    type: EntityType
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    group: str | None = None
    properties: NodeProperties = Field(default_factory=NodeProperties)


class EdgeProperties(BaseModel):
    timestamp: str | None = None
    duration: int | None = None
    amount: float | None = None
    transaction_id: str | None = None
    role: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_doc: str | None = None
    evidence: str | None = None


class GraphEdge(BaseModel):
    id: str | None = None
    source: str
    target: str
    type: RelationshipType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    doc_id: str | None = None
    properties: EdgeProperties = Field(default_factory=EdgeProperties)


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RiskBreakdown(BaseModel):
    degree_centrality: float = Field(default=0.0, ge=0.0, le=100.0)
    pagerank_score: float = Field(default=0.0, ge=0.0, le=100.0)
    betweenness_centrality: float = Field(default=0.0, ge=0.0, le=100.0)
    call_frequency_score: float = Field(default=0.0, ge=0.0, le=100.0)
    cross_case_score: float = Field(default=0.0, ge=0.0, le=100.0)
    financial_anomaly_score: float = Field(default=0.0, ge=0.0, le=100.0)


class EntityDetailResponse(BaseModel):
    id: str
    name: str
    type: EntityType
    overall_risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_breakdown: RiskBreakdown
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    direct_connections_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    doc_id: str
    doc_type: str
    excerpt: str
    timestamp: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    verified_by_nlp: bool = True
