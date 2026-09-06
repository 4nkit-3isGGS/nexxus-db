"""
json_loader.py
Converts Person 1/2's real extraction output (entities + relationships JSON)
into the networkx.MultiDiGraph everything else in this folder expects.

Handles two real-world data quality issues found in the actual output:

1. DANGLING REFERENCES: a relationship can reference an entity id (e.g. "P002")
   that never appears in the `entities` list. Rather than crashing, we create
   a minimal stub node and log a warning -- so Person 1/2 can be told exactly
   which ids are missing.

2. NO EXPLICIT case_ids FIELD: the schema has `source_doc` per entity/edge,
   not a `case_ids` list. We derive case membership by treating any
   source_doc matching the pattern "FIR_<number>" as a case reference
   (CDR/financial/MCA/RTO records are supporting evidence, not a distinct
   case) and collect the FIR references touching each PERSON node.

   ASSUMPTION TO CONFIRM WITH PERSON 1/2: that "one FIR number == one case".
   If their notion of "case" differs, change FIR_PATTERN or the collection
   logic below accordingly.
"""

import re
import json
import warnings
from collections import defaultdict

import networkx as nx
from graph.contracts.constants import normalize_entity_type
from graph.data_sources.case_utils import derive_case_ids

FIR_PATTERN = re.compile(r"^FIR_")


def load_from_json(data: dict) -> nx.MultiDiGraph:
    """
    data: parsed JSON with "entities" and "relationships" keys,
    exactly as produced by Person 1/2's pipeline.
    """
    entities = data.get("entities", [])
    relationships = data.get("relationships", [])

    G = nx.MultiDiGraph()
    known_ids = set()

    # --- Add real entities ---
    for e in entities:
        node_id = e["id"]
        attrs = {k: v for k, v in e.items() if k != "id"}
        if "type" in attrs:
            attrs["type"] = normalize_entity_type(attrs["type"])
        G.add_node(node_id, **attrs)
        known_ids.add(node_id)

    # --- Add relationships, creating stub nodes for dangling references ---
    for idx, r in enumerate(relationships):
        src, tgt, rel_type = r["source"], r["target"], r["type"]

        for node_id in (src, tgt):
            if node_id not in known_ids:
                warnings.warn(
                    f"Relationship #{idx} references unknown entity '{node_id}' "
                    f"(not present in entities list) -- creating a stub node. "
                    f"Flag this to Person 1/2, their entities list is incomplete."
                )
                G.add_node(node_id, type="UNKNOWN", name=node_id)
                known_ids.add(node_id)

        edge_attrs = {k: v for k, v in r.items() if k not in ("source", "target", "type")}
        edge_attrs["edge_type"] = rel_type
        G.add_edge(src, tgt, key=f"rel{idx}", **edge_attrs)

    derive_case_ids(G)  # shared logic -- see case_utils.py

    return G


def load_from_json_file(path: str) -> nx.MultiDiGraph:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return load_from_json(data)


if __name__ == "__main__":
    # quick smoke test against a saved sample
    import sys
    from pathlib import Path
    default_path = str(Path(__file__).resolve().parent.parent / "sample_data" / "sample_person2_data.json")
    path = sys.argv[1] if len(sys.argv) > 1 else default_path
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        G = load_from_json_file(path)
        for w in caught:
            print(f"[WARNING] {w.message}")

    print(f"\nNodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
    for node, data in G.nodes(data=True):
        print(f"  {node}: {data}")
