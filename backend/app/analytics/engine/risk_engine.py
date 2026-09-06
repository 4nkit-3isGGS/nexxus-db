"""
risk_engine.py
Computes per-entity risk signals in the exact shape Person 4's
RiskBreakdown / EntityDetailResponse schema expects (see schemas.py).

Includes:
  - the six normalized (0-100) RiskBreakdown sub-scores
  - a flat watchlist boost for known prior offenders (watchlist.py)
  - time-decay: recent anomalies count more than old ones
  - a percentile_rank across the whole entity set (in metadata, not part
    of the official RiskBreakdown schema -- Person 4's schema is fixed,
    so anything extra goes in EntityDetailResponse.metadata)

Anomaly-based signals (call_frequency_score, financial_anomaly_score) are
computed directly per-node -- NOT diluted through a normalized-average
with centrality -- so a peripheral/leaf node caught in a real anomaly
still scores meaningfully high (this was a real bug in an earlier
version of this file -- see project history).
"""

import json
from datetime import datetime

from graph.engine.analytics import (
    compute_centrality,
    compute_bridge_score,
    detect_communities,
    detect_circular_transactions,
    detect_call_bursts,
    detect_cross_case_entities,
)
from graph.engine.watchlist import check_watchlist, WATCHLIST_BOOST

WEIGHTS = {
    "degree_centrality": 0.05,
    "pagerank_score": 0.05,
    "betweenness_centrality": 0.20,
    "call_frequency_score": 0.20,
    "cross_case_score": 0.25,
    "financial_anomaly_score": 0.25,
}
CALL_BURST_THRESHOLD = 10  # calls/day that count as "unusual"
DECAY_HALF_LIFE_DAYS = 90  # anomaly signal halves in weight every N days of age


def _normalize_to_100(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return round(min(value / max_value, 1.0) * 100, 1)


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _graph_reference_time(G) -> datetime | None:
    """'Now', for decay purposes, is the most recent timestamp anywhere in
    the graph -- not wall-clock time. The mock/demo data lives in its own
    timeline (e.g. Aug 2026), so decaying against real wall-clock time
    would make everything look ancient."""
    latest = None
    for _, _, data in G.edges(data=True):
        ts = _parse_ts(data.get("timestamp"))
        if ts and (latest is None or ts > latest):
            latest = ts
    return latest


def _most_recent_activity(G, node, reference_dt: datetime | None) -> datetime | None:
    if reference_dt is None:
        return None
    latest = None
    touching = list(G.edges(node, data=True)) + list(G.in_edges(node, data=True))
    for _, _, data in touching:
        ts = _parse_ts(data.get("timestamp"))
        if ts and (latest is None or ts > latest):
            latest = ts
    return latest


def _recency_multiplier(G, node, reference_dt: datetime | None) -> float:
    """1.0 = activity as recent as the newest event in the graph.
    Decays toward 0 the older the node's most recent activity is,
    with a half-life of DECAY_HALF_LIFE_DAYS. Floors at 0.1 so an old
    anomaly still counts for something, not zero."""
    if reference_dt is None:
        return 1.0
    last_active = _most_recent_activity(G, node, reference_dt)
    if last_active is None:
        return 1.0  # no timestamped activity to judge recency by -- don't penalize
    age_days = max((reference_dt - last_active).total_seconds() / 86400, 0)
    multiplier = 0.5 ** (age_days / DECAY_HALF_LIFE_DAYS)
    return round(max(multiplier, 0.1), 3)


def compute_risk_breakdown(G) -> dict:
    """Returns {entity_id: {risk_breakdown, overall_risk_score, tags,
    direct_connections_count, percentile_rank, recency_multiplier,
    watchlist_reason}} for every node in G."""
    centrality = compute_centrality(G)
    bridge_scores = compute_bridge_score(centrality)
    cross_case = detect_cross_case_entities(G)
    circular_txns = detect_circular_transactions(G)
    call_bursts = detect_call_bursts(G)
    reference_dt = _graph_reference_time(G)

    nodes_in_circular = {node for cycle in circular_txns for node in cycle["path"] if cycle["significant"]}
    nodes_in_noise_cycle = {node for cycle in circular_txns for node in cycle["path"] if not cycle["significant"]} - nodes_in_circular

    max_daily_calls = {}
    for burst in call_bursts:
        for node in (burst["source"], burst["target"]):
            max_daily_calls[node] = max(max_daily_calls.get(node, 0), burst["call_count"])

    max_degree = max((v["degree_centrality"] for v in centrality.values()), default=1) or 1
    max_pagerank = max((v["pagerank"] for v in centrality.values()), default=1) or 1
    max_betweenness = max((v["betweenness_centrality"] for v in centrality.values()), default=1) or 1
    max_cases = max(cross_case.values(), default=1) or 1
    max_bridge_score = max(bridge_scores.values(), default=1) or 1

    results = {}
    for node, scores in centrality.items():
        degree_centrality = _normalize_to_100(scores["degree_centrality"], max_degree)
        pagerank_score = _normalize_to_100(scores["pagerank"], max_pagerank)
        betweenness_centrality = _normalize_to_100(scores["betweenness_centrality"], max_betweenness)
        cross_case_score = _normalize_to_100(cross_case.get(node, 0), max_cases)

        daily_calls = max_daily_calls.get(node, 0)
        raw_call_frequency_score = round(min(daily_calls / CALL_BURST_THRESHOLD, 1.0) * 100, 1) if daily_calls else 0.0
        raw_financial_anomaly_score = 100.0 if node in nodes_in_circular else (30.0 if node in nodes_in_noise_cycle else 0.0)

        # Time-decay: recent anomalies count more than old ones. Only
        # applied to the two anomaly/behavior signals -- centrality is a
        # structural property, not a recency-sensitive one.
        recency = _recency_multiplier(G, node, reference_dt)
        call_frequency_score = round(raw_call_frequency_score * recency, 1)
        financial_anomaly_score = round(raw_financial_anomaly_score * recency, 1)

        breakdown = {
            "degree_centrality": degree_centrality,
            "pagerank_score": pagerank_score,
            "betweenness_centrality": betweenness_centrality,
            "call_frequency_score": call_frequency_score,
            "cross_case_score": cross_case_score,
            "financial_anomaly_score": financial_anomaly_score,
        }

        base_overall = sum(WEIGHTS[k] * v for k, v in breakdown.items())

        # Watchlist boost: a flat bonus, independent of graph structure --
        # a known prior offender is a risk signal on its own.
        node_name = G.nodes[node].get("name")
        watchlist_reason = check_watchlist(node, node_name)
        watchlist_bonus = WATCHLIST_BOOST if watchlist_reason else 0

        overall_risk_score = round(min(base_overall + watchlist_bonus, 100.0), 1)

        bridge_score_normalized = _normalize_to_100(bridge_scores.get(node, 0.0), max_bridge_score)

        tags = []
        if betweenness_centrality >= 70:
            tags.append("Bridge Node")
        if bridge_score_normalized >= 70 and degree_centrality <= 50:
            # High betweenness relative to how few connections this node
            # actually has -- a low-profile coordinator, not just a hub.
            # See project history: raw betweenness alone flagged the wrong
            # person (a well-connected hub) over the real bridge node.
            tags.append("Hidden Kingpin")
        if overall_risk_score >= 75 and cross_case_score >= 50:
            tags.append("Kingpin")
        if financial_anomaly_score >= 50 and degree_centrality < 30:
            tags.append("Money Mule")
        if call_frequency_score >= 70:
            tags.append("High Communication Volume")
        if watchlist_reason:
            tags.append("Watchlisted")

        distinct_neighbors = set(G.predecessors(node)) | set(G.successors(node))

        results[node] = {
            "risk_breakdown": breakdown,
            "overall_risk_score": overall_risk_score,
            "tags": tags,
            "direct_connections_count": len(distinct_neighbors),
            "recency_multiplier": recency,
            "watchlist_reason": watchlist_reason,
            "bridge_score": bridge_score_normalized,
        }

    # Percentile rank needs the full score distribution -- computed after
    # the main loop, once every node's overall_risk_score is known.
    all_scores = sorted(v["overall_risk_score"] for v in results.values())
    n = len(all_scores)
    for node, result in results.items():
        score = result["overall_risk_score"]
        rank = sum(1 for s in all_scores if s <= score)
        result["percentile_rank"] = round((rank / n) * 100, 1) if n else 0.0

    return results


if __name__ == "__main__":
    from graph.data_sources.graph_loader import load_graph

    G = load_graph()
    breakdown = compute_risk_breakdown(G)
    ranked = sorted(breakdown.items(), key=lambda x: x[1]["overall_risk_score"], reverse=True)
    print(json.dumps({k: v for k, v in ranked}, indent=2))
