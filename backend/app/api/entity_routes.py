#  GET /api/entity/{id} — entity detail with phones
#  GET /api/entity/{id}/neighbors — 1-hop connections
#  GET /api/entity/{id}/subgraph — multi-hop (configurable depth)
#  GET /api/entity/{id}/shared-locations — co-occurrence
#  GET /api/entity/{id1}/evidence/{id2}
"""
Entity API Routes
-----------------
Endpoints for querying individual entities and their connections.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.app.services.graph_service import (
    get_entity,
    get_neighbors,
    get_subgraph,
    get_shared_locations,
    get_evidence,
    get_review_queue,
    merge_duplicate_entities,
)

router = APIRouter(prefix="/api/entity", tags=["Entity"])


class MergeEntitiesRequest(BaseModel):
    target_id: str
    duplicate_id: str


@router.get("/review-queue")
def entity_review_queue() -> list[dict]:
    """Returns all entity pairs flagged with POSSIBLE_DUPLICATE for investigator review."""
    return get_review_queue()


@router.post("/merge")
def entity_merge(req: MergeEntitiesRequest) -> dict:
    """Approves and executes the merge of duplicate_id into target_id."""
    result = merge_duplicate_entities(req.target_id, req.duplicate_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Merge failed"))
    return result


# Plural alias router (/api/entities/...) for dashboard compatibility
entities_router = APIRouter(prefix="/api/entities", tags=["Entities"])
entities_router.add_api_route("/review-queue", entity_review_queue, methods=["GET"], summary="Review Queue (Entities Alias)")
entities_router.add_api_route("/merge", entity_merge, methods=["POST"], summary="Merge Entities (Entities Alias)")


@router.get("/{entity_id}")
def entity_details(entity_id: str) -> dict:
    """Returns a Person entity with all properties and linked phone numbers."""

    result = get_entity(entity_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    return result


@router.get("/{entity_id}/neighbors")
def entity_neighbors(entity_id: str) -> list[dict]:
    """Returns all direct 1-hop connections of an entity."""
    return get_neighbors(entity_id)
    

@router.get("/{entity_id}/subgraph")
def entity_subgraph(entity_id: str, depth: int = Query(2, ge=1, le=5)):
    """Returns multi-hop subgraph around an entity up to given depth."""
    return get_subgraph(entity_id, depth)


@router.get("/{entity_id}/shared-locations")
def entity_shared_locations(entity_id: str) -> list[dict]:
    """Finds other people present at the same locations as the given person."""
    return get_shared_locations(entity_id)


@router.get("/{id1}/evidence/{id2}")
def entity_evidence(id1: str, id2: str) -> list[dict]:
    """Returns provenance/evidence data for relationships between two entities."""
    return get_evidence(id1, id2)

