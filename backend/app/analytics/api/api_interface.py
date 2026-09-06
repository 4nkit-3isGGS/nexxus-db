"""
api_interface.py
THIS is the file Person 4 imports. Don't import analytics.py, risk_engine.py,
or schema_mapper.py directly in the FastAPI app -- import this instead, so
internal refactors on Person 3's side don't break Person 4's routes.

Everything returned here is already validated against Person 4's own
schemas.py contract (GraphResponse / EntityDetailResponse) -- if something
doesn't conform, it fails here during testing, not inside their API.

Usage in Person 4's FastAPI app:

    from api_interface import get_full_analysis, get_entity_detail

    @app.get("/api/graph", response_model=GraphResponse)
    def get_graph():
        return get_full_analysis()

    @app.get("/api/entity/{entity_id}", response_model=EntityDetailResponse)
    def get_entity(entity_id: str):
        result = get_entity_detail(entity_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return result
"""

from graph.data_sources.graph_loader import load_graph
from graph.api.schema_mapper import build_graph_response, build_entity_detail
from graph.contracts.schemas import GraphResponse, EntityDetailResponse


def get_full_analysis() -> GraphResponse:
    """One call, everything the frontend/graph view needs. Cache this in
    Person 4's API layer (e.g. recompute every N minutes) -- it's not
    designed to be fast enough for high request volume."""
    G = load_graph()
    return build_graph_response(G)


def get_entity_detail(entity_id: str) -> EntityDetailResponse | None:
    """Single-entity lookup for GET /api/entity/{id} style endpoints."""
    G = load_graph()
    return build_entity_detail(G, entity_id)


if __name__ == "__main__":
    result = get_full_analysis()
    print(result.model_dump_json(indent=2))
    print("\n--- Example entity detail (Rahul) ---")
    detail = get_entity_detail("Rahul")
    if detail:
        print(detail.model_dump_json(indent=2))
