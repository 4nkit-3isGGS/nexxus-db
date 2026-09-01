"""
Ingestion API Routes
--------------------
POST /api/graph/ingest — accepts Abhidha's NLP output contract, runs full ingestion pipeline.
"""

from fastapi import APIRouter, HTTPException
from backend.app.ingestion.graph_ingestor import ingest_nlp_payload
from backend.app.models.entities import NLPOutputPayload

router = APIRouter(prefix="/api/graph", tags=["Ingestion"])


@router.post("/ingest")
def ingest_payload(payload: NLPOutputPayload) -> dict:
    """
    Accepts the NLP-extracted payload and ingests it into the knowledge graph.

    Runs entity resolution on Person entities, creates/merges all node types,
    and processes relationships with full provenance.
    """
    try:
        result = ingest_nlp_payload(payload.model_dump())
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion Failed: {str(e)}")
