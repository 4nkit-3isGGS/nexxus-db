"""
analytics.py
Core graph analytics: centrality, community detection, anomaly detection.

All functions take a networkx graph (MultiDiGraph) and return plain
dicts/lists so they're easy to JSON-serialize for Person 4's API layer.
"""

import networkx as nx
from collections import defaultdict
from datetime import datetime


# ---------------------------------------------------------------------------
# Centrality
# ---------------------------------------------------------------------------

def compute_centrality(G: nx.MultiDiGraph) -> dict:
    """Returns per-node centrality scores, all normalized to [0, 1]."""
    # networkx betweenness/pagerank on MultiDiGraph can be slow/inconsistent;
    # collapse to a simple weighted DiGraph for these calculations.
    simple = _collapse_to_weighted_digraph(G)

    degree = nx.degree_centrality(simple)
    betweenness = nx.betweenness_centrality(simple, weight="weight")
    try:
        pagerank = nx.pagerank(simple, weight="weight")
    except nx.PowerIterationFailedConvergence:
        pagerank = {n: 0.0 for n in simple.nodes()}

    result = {}
    for node in simple.nodes():
        result[node] = {
            "degree_centrality": round(degree.get(node, 0.0), 4),
            "betweenness_centrality": round(betweenness.get(node, 0.0), 4),
            "pagerank": round(pagerank.get(node, 0.0), 4),
        }
    return result


def _collapse_to_weighted_digraph(G: nx.MultiDiGraph) -> nx.DiGraph:
    """Multiple edges between the same pair (e.g. 18 calls) become one
    edge with weight = count, so a burst of calls correctly increases
    that connection's importance in centrality math."""
    simple = nx.DiGraph()
    simple.add_nodes_from(G.nodes(data=True))
    for u, v, data in G.edges(data=True):
        if simple.has_edge(u, v):
            simple[u][v]["weight"] += 1
        else:
            simple.add_edge(u, v, weight=1)
    return simple


def compute_bridge_score(centrality: dict) -> dict:
    """Betweenness centrality per unit of degree -- surfaces 'hidden'
    low-profile coordinators (few visible connections, but sitting on a
    disproportionate share of shortest paths) as distinct from a merely
    well-connected hub node that also happens to have high betweenness
    (many connections AND many shortest paths through it -- structurally
    important, but not 'hidden').

    A high raw betweenness alone can flag the wrong person: a hub with
    dozens of connections will often out-rank a genuine low-degree bridge
    node on betweenness alone, even though the bridge node is the one
    whose absence would actually disconnect two otherwise-separate
    clusters. This ratio is what separates the two profiles.
    """
    scores = {}
    for node, c in centrality.items():
        degree = max(c["degree_centrality"], 0.05)  # floor avoids divide-by-near-zero blowups
        scores[node] = round(c["betweenness_centrality"] / degree, 4)
    return scores


# ---------------------------------------------------------------------------
# Community detection
# ---------------------------------------------------------------------------

def detect_communities(G: nx.MultiDiGraph) -> dict:
    """Returns {node: community_id}. Louvain needs an undirected simple graph."""
    undirected = nx.Graph()
    undirected.add_nodes_from(G.nodes())
    for u, v in G.edges():
        if undirected.has_edge(u, v):
            undirected[u][v]["weight"] += 1
        else:
            undirected.add_edge(u, v, weight=1)

    communities = nx.algorithms.community.louvain_communities(undirected, weight="weight", seed=42)

    node_to_community = {}
    for idx, community in enumerate(communities):
        for node in community:
            node_to_community[node] = idx
    return node_to_community


# ---------------------------------------------------------------------------
# Anomaly detection (rule-based -- deliberately simple for hackathon scope)
# ---------------------------------------------------------------------------

SIGNIFICANCE_AMOUNT_CONSISTENCY = 0.85  # cycle's smallest/largest amount ratio must be >= this
SIGNIFICANCE_WINDOW_HOURS = 72  # cycle must close within this many hours to count as deliberate


def _parse_ts_safe(ts):
    if not ts:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _amount_consistency(amounts: list) -> float:
    """1.0 = identical amounts, closer to 0 = wildly different. A real
    layering loop typically moves ~the same sum through each hop (minus a
    small cut); a coincidental cycle formed from unrelated transactions
    usually won't line up in size."""
    if len(amounts) < 2:
        return 0.0
    lo, hi = min(amounts), max(amounts)
    if hi == 0:
        return 0.0
    return round(lo / hi, 3)


def _time_span_hours(timestamps: list):
    if len(timestamps) < 2:
        return None
    return round((max(timestamps) - min(timestamps)).total_seconds() / 3600, 1)


def detect_circular_transactions(G: nx.MultiDiGraph, max_cycle_len: int = 4) -> list:
    """Finds cycles of TRANSACTED_WITH edges -- classic laundering pattern
    (A pays B, B pays C, C pays back A) -- and scores each one so a
    genuine deliberate routing loop can be told apart from a coincidental
    cycle that happens to form from unrelated back-and-forth transactions
    between the same accounts (which real data can absolutely produce --
    see project history for a worked example).

    Returns a list of dicts:
        {"path": [...node ids...], "significant": bool,
         "amount_consistency": float, "time_span_hours": float | None}

    A cycle is `significant` when it has 3+ hops, its amounts are
    consistent with each other (within SIGNIFICANCE_AMOUNT_CONSISTENCY),
    and it closes within SIGNIFICANCE_WINDOW_HOURS. Those two signals --
    consistent amounts, tight timing -- are what separates deliberate
    layering from noise; cycle existence alone is not enough.
    """
    txn_graph = nx.DiGraph()
    edge_lookup = {}
    for u, v, data in G.edges(data=True):
        if data.get("edge_type") == "TRANSACTED_WITH":
            txn_graph.add_edge(u, v)
            edge_lookup[(u, v)] = data  # last parallel edge wins if there are duplicates

    results = []
    for cycle in nx.simple_cycles(txn_graph, length_bound=max_cycle_len):
        if len(cycle) < 2:
            continue

        amounts, timestamps = [], []
        for i in range(len(cycle)):
            u, v = cycle[i], cycle[(i + 1) % len(cycle)]
            edge = edge_lookup.get((u, v), {})
            if edge.get("amount") is not None:
                amounts.append(edge["amount"])
            ts = _parse_ts_safe(edge.get("timestamp"))
            if ts:
                timestamps.append(ts)

        amount_consistency = _amount_consistency(amounts)
        time_span_hours = _time_span_hours(timestamps)

        significant = (
            len(cycle) >= 3
            and amount_consistency >= SIGNIFICANCE_AMOUNT_CONSISTENCY
            and time_span_hours is not None
            and time_span_hours <= SIGNIFICANCE_WINDOW_HOURS
        )

        results.append({
            "path": cycle,
            "significant": significant,
            "amount_consistency": amount_consistency,
            "time_span_hours": time_span_hours,
        })

    return results


def detect_call_bursts(G: nx.MultiDiGraph, threshold_per_day: int = 10) -> list:
    """Flags (source, target) pairs with more than `threshold_per_day` CALLED
    edges on the same calendar day."""
    calls_by_pair_day = defaultdict(int)

    for u, v, data in G.edges(data=True):
        if data.get("edge_type") != "CALLED":
            continue
        ts = data.get("timestamp")
        if not ts:
            continue
        ts = ts.replace("Z", "+00:00")  # handle UTC 'Z' suffix Person 1/2's data uses
        day = datetime.fromisoformat(ts).date().isoformat()
        calls_by_pair_day[(u, v, day)] += 1

    flagged = []
    for (u, v, day), count in calls_by_pair_day.items():
        if count > threshold_per_day:
            flagged.append({"source": u, "target": v, "date": day, "call_count": count})
    return flagged


def detect_cross_case_entities(G: nx.MultiDiGraph) -> dict:
    """Returns {node: num_distinct_cases} for entities appearing in 2+ cases --
    a strong investigative signal on its own. Works off case_ids regardless
    of node type, so it doesn't actually need the type check -- but we guard
    on it anyway since only Person nodes are expected to carry case_ids."""
    result = {}
    for node, data in G.nodes(data=True):
        case_ids = data.get("case_ids", [])
        if len(case_ids) >= 2:
            result[node] = len(case_ids)
    return result


if __name__ == "__main__":
    from graph.data_sources.graph_loader import load_graph
    import json

    G = load_graph()

    print("\n=== Centrality ===")
    print(json.dumps(compute_centrality(G), indent=2))

    print("\n=== Communities ===")
    print(json.dumps(detect_communities(G), indent=2))

    print("\n=== Circular transactions ===")
    print(json.dumps(detect_circular_transactions(G), indent=2))

    print("\n=== Call bursts (>10/day) ===")
    print(json.dumps(detect_call_bursts(G), indent=2))

    print("\n=== Cross-case entities ===")
    print(json.dumps(detect_cross_case_entities(G), indent=2))
