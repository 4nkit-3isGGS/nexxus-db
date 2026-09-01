"""
Health API Routes
-----------------
Neo4j connectivity health check.
"""

from fastapi import APIRouter
from backend.app.neo4j_driver import db

router = APIRouter(tags=["health"])


@router.get("/api/health")
def check_health() -> dict:
    """Checks the Neo4j Connectivity."""
    is_connected = db.verify_connectivity()

    return {
        "status": "Healthy" if is_connected else "Unhealthy",
        "Neo4j": "Connected" if is_connected else "Unconnected" 
    }
