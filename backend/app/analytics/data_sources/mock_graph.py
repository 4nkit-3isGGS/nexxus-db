"""
mock_graph.py
Builds a synthetic criminal-network graph for testing analytics
BEFORE Person 1/2's real extraction + Neo4j pipeline is ready.

The graph deliberately contains:
  - a circular transaction (money-laundering pattern): Suresh -> Amit -> Rahul -> Suresh
  - a high-betweenness "bridge" node (Rahul) connecting two otherwise separate clusters
  - a burst-calling pattern (Rahul <-> Priya, many calls in one day)
  - a small community (Vikram, Neha, Sanjay) isolated from the main cluster

Swap this module out for a Neo4j-backed loader once Person 2's graph DB is ready --
everything downstream (analytics.py, risk_engine.py) only needs a networkx.DiGraph,
so the swap is a one-line change (see graph_loader.py).
"""

import networkx as nx
from datetime import datetime, timedelta


def build_mock_graph() -> nx.MultiDiGraph:
    """Returns a MultiDiGraph so multiple relationship types/instances
    can exist between the same pair of nodes (e.g. many calls)."""
    G = nx.MultiDiGraph()

    # --- Node metadata (mirrors the entity schema Person 1/2 will produce) ---
    people = {
        "Rahul": {"type": "Person", "case_ids": ["CASE001", "CASE002", "CASE003"]},
        "Amit": {"type": "Person", "case_ids": ["CASE001"]},
        "Suresh": {"type": "Person", "case_ids": ["CASE001", "CASE002"]},
        "Priya": {"type": "Person", "case_ids": ["CASE003"]},
        "Vikram": {"type": "Person", "case_ids": ["CASE004"]},
        "Neha": {"type": "Person", "case_ids": ["CASE004"]},
        "Sanjay": {"type": "Person", "case_ids": ["CASE004"]},
    }
    for name, attrs in people.items():
        G.add_node(name, **attrs)

    # --- Circular transaction: classic laundering red flag ---
    G.add_edge("Suresh", "Amit", key="txn1", edge_type="TRANSACTED_WITH",
               amount=50000, timestamp="2026-08-01T10:00:00", source_doc="CASE001-FIR-3")
    G.add_edge("Amit", "Rahul", key="txn2", edge_type="TRANSACTED_WITH",
               amount=48000, timestamp="2026-08-01T14:00:00", source_doc="CASE001-FIR-3")
    G.add_edge("Rahul", "Suresh", key="txn3", edge_type="TRANSACTED_WITH",
               amount=47000, timestamp="2026-08-01T18:00:00", source_doc="CASE001-FIR-3")

    # --- Rahul as bridge node: connects main cluster to Priya's case ---
    G.add_edge("Rahul", "Priya", key="assoc1", edge_type="PRESENT_AT",
               location="Howrah Bridge", timestamp="2026-08-02T09:00:00",
               source_doc="CASE003-FIR-1")

    # --- Burst calling pattern: Rahul <-> Priya, many calls in one day ---
    base_time = datetime(2026, 8, 3, 8, 0, 0)
    for i in range(18):  # 18 calls in a day -> should trip the anomaly threshold
        t = base_time + timedelta(minutes=i * 25)
        G.add_edge("Rahul", "Priya", key=f"call{i}", edge_type="CALLED",
                   duration_sec=120 + i * 10, timestamp=t.isoformat(),
                   source_doc="CDR-0091")

    # --- Cross-case connection ---
    G.add_edge("Amit", "Suresh", key="assoc2", edge_type="ASSOCIATED_WITH",
               timestamp="2026-07-28T00:00:00", source_doc="CASE002-FIR-1")

    # --- Small isolated community (should show up as its own Louvain cluster) ---
    G.add_edge("Vikram", "Neha", key="c1", edge_type="CALLED",
               duration_sec=300, timestamp="2026-08-04T11:00:00", source_doc="CDR-0102")
    G.add_edge("Neha", "Sanjay", key="c2", edge_type="TRANSACTED_WITH",
               amount=15000, timestamp="2026-08-04T12:00:00", source_doc="CDR-0102")
    G.add_edge("Sanjay", "Vikram", key="c3", edge_type="ASSOCIATED_WITH",
               timestamp="2026-08-04T13:00:00", source_doc="CDR-0102")

    return G


if __name__ == "__main__":
    g = build_mock_graph()
    print(f"Nodes: {g.number_of_nodes()}, Edges: {g.number_of_edges()}")
    print("Node list:", list(g.nodes()))
