"""
explanation.py
Builds the "why was this flagged" evidence trail per entity: the actual
source documents/excerpts behind a risk signal, and (for circular
transactions) the exact path of entities involved.

This is what Person 4's LangGraph explanation-agent (Phase 2, agentic
layer) should call when answering a natural-language investigator query
like "why is Rahul high risk?" -- feed straight into
AgentQueryResponse.evidence and .highlighted_nodes.
"""

import re
from graph.contracts.schemas import EvidenceItem
from graph.engine.analytics import detect_circular_transactions

_DOC_TYPE_PATTERNS = [
    (re.compile(r"^FIR_"), "FIR"),
    (re.compile(r"^CDR"), "CDR"),
    (re.compile(r"^FIN"), "BANK_TXN"),
    (re.compile(r"^MCA"), "MCA_RECORD"),
    (re.compile(r"^RTO"), "RTO_RECORD"),
]


def _infer_doc_type(source_doc: str) -> str:
    for pattern, doc_type in _DOC_TYPE_PATTERNS:
        if pattern.match(source_doc or ""):
            return doc_type
    return "OTHER"


def get_entity_evidence(G, entity_id: str) -> list[EvidenceItem]:
    """All source-document evidence for edges touching this entity --
    the exact excerpts that justify a risk score, for court-ready
    traceability (not just a number, but where it came from)."""
    if entity_id not in G.nodes:
        return []

    items = []
    seen = set()
    edges = list(G.edges(entity_id, data=True)) + list(G.in_edges(entity_id, data=True))
    for u, v, data in edges:
        doc_id = data.get("source_doc_id") or data.get("source_doc")
        excerpt = data.get("evidence")
        if not doc_id or not excerpt:
            continue
        key = (doc_id, excerpt)
        if key in seen:
            continue
        seen.add(key)
        items.append(EvidenceItem(
            doc_id=doc_id,
            doc_type=_infer_doc_type(doc_id),
            excerpt=excerpt,
            timestamp=data.get("timestamp", ""),
            confidence=data.get("confidence", 1.0),
            verified_by_nlp=True,
        ))
    return items


def get_explanation_path(G, entity_id: str) -> dict:
    """For an entity flagged in a circular transaction, returns the exact
    cycle of entities that make up the pattern -- ready to highlight on
    the frontend graph (highlighted_nodes in AgentQueryResponse).
    Prefers a `significant` cycle (consistent amounts, tight time window --
    a real deliberate routing loop) over one merely detected as a graph
    cycle (which can also fire on coincidental noise -- see analytics.py)."""
    cycles = detect_circular_transactions(G)
    matching = [c for c in cycles if entity_id in c["path"]]
    if not matching:
        return {"pattern": None, "path": []}

    significant = [c for c in matching if c["significant"]]
    best = significant[0] if significant else matching[0]
    return {
        "pattern": "circular_transaction",
        "path": best["path"],
        "significant": best["significant"],
        "amount_consistency": best["amount_consistency"],
        "time_span_hours": best["time_span_hours"],
    }
