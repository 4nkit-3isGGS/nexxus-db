"""
case_utils.py
Shared logic for deriving case_ids on Person nodes, used by every loader
(json_loader.py, neo4j_loader.py) so this assumption lives in one place.

ASSUMPTION TO CONFIRM WITH PERSON 1/2/4: "one FIR number == one case".
Any source_doc matching FIR_<something> is treated as a distinct case
reference; CDR/financial/MCA/RTO records are supporting evidence, not
separate cases. If the team's definition of "case" differs, change
FIR_PATTERN or the collection logic here -- everything downstream
(cross_case_score in risk_engine.py) depends on this.
"""

import re
from collections import defaultdict

FIR_PATTERN = re.compile(r"^fir", re.IGNORECASE)  # matches "FIR_102", "fir_101", "CASE001-FIR-3", etc.


def derive_case_ids(G) -> None:
    """Mutates G in place: sets case_ids on every Person node, derived from
    FIR-pattern source_doc references on its entity record and on any edge
    touching it."""
    fir_refs = defaultdict(set)

    for u, v, data in G.edges(data=True):
        doc = data.get("source_doc_id") or data.get("source_doc") or ""
        if FIR_PATTERN.search(doc):
            fir_refs[u].add(doc)
            fir_refs[v].add(doc)

    for node_id, node_data in G.nodes(data=True):
        doc = node_data.get("source_doc_id") or node_data.get("source_doc") or ""
        if FIR_PATTERN.search(doc):
            fir_refs[node_id].add(doc)

    for node_id, node_data in G.nodes(data=True):
        if node_data.get("type") == "Person":
            node_data["case_ids"] = sorted(fir_refs.get(node_id, set()))
