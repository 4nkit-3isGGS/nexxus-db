"""
NexxusDB — Criminal Network Intelligence API
---------------------------------------------
FastAPI entry point. Connects to Neo4j on startup, registers all route modules,
and exposes the graph ingestion + query API for the team.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.neo4j_driver import db
from backend.app.api import ingestion_routes, entity_routes, graph_routes, health_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages Neo4j connection lifecycle."""
    db.connect()
    print("[NexxusDB] Neo4j connected")
    yield
    db.close()
    print("[NexxusDB] Neo4j connection closed")


app = FastAPI(
    title="NexxusDB — Criminal Network Intelligence API",
    description="Knowledge Graph API for the AI-Powered Criminal Network Analysis System (SIH 2026)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend and LangGraph agents to access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(health_routes.router)
app.include_router(ingestion_routes.router)
app.include_router(entity_routes.router)
app.include_router(entity_routes.entities_router)
app.include_router(graph_routes.router)


@app.get("/")
def root():
    return {
        "name": "NexxusDB", 
        "status": "running"
    }
