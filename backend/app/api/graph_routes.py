"""
Graph API Routes
----------------
Endpoints for graph-wide operations: paths, search, stats.
"""


from fastapi import APIRouter, Query

from backend.app.services.graph_service import (
    get_graph_stats,
    get_shortest_path,
    search_entities
)

router = APIRouter(prefix="/api/graph", tags=["Graph"])

@router.get("/path")
def shortest_path(id1: str= Query(...), id2: str= Query(...)) -> dict:
    """Finds the shortest path between two entities."""
    return get_shortest_path(id1, id2)

@router.get("/stats")
def graph_stats() -> dict:
    """Returns node and relationship counts for the dashboard."""
    stats = get_graph_stats()
    total_nodes = sum(s["count"] for s in stats if s.get("category") == "node")
    total_relationships = sum(s["count"] for s in stats if s.get("category") == "relationship")
    return {
        "total_nodes": total_nodes,
        "total_relationships": total_relationships,
        "breakdown": stats
    }

@router.get("/search")
def search(query: str = Query(..., min_length=1), limit: int= Query(20, ge=1, le=100)):
    """Searches Person entities by name or alias (case-insensitive)."""
    return search_entities(query, limit)

