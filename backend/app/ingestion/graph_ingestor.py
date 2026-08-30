"""
Graph Ingestion Pipeline
------------------------
Receives structured JSON data (from NLP extraction of FIRs and CDRs),
runs Entity Resolution to deduplicate, and persists entities and
relationships into Neo4j.
"""

import uuid
from datetime import datetime, timezone

from backend.app.neo4j_driver import db
from backend.app.resolution.normalizer import normalize_name
from backend.app.resolution.resolver import resolve_entity


def get_person_candidates() -> list:
    """Fetches all Person nodes from Neo4j with their phones and aliases.

    Returns a list of dicts matching the format resolve_entity() expects:
    [{"id": ..., "name": ..., "aliases": [...], "phones": [...]}, ...]
    """
    cypher_query = """
    MATCH (p:Person)
    OPTIONAL MATCH (p)-[:OWNS_PHONE]->(ph:Phone)
    RETURN p.id AS id, p.name AS name, p.aliases AS aliases, collect(ph.number) AS phones
    """
    return db.query(cypher_query)


def create_new_person(suspect: dict, source_doc: str) -> str:
    """Creates a new Person node in Neo4j with a generated UUID.

    Returns the generated person_id for use in linking relationships.
    """
    norm_name = normalize_name(suspect.get("name"))
    person_id = f"P-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher_query = """
    MERGE (p:Person {id: $id})
    SET p.name = $name,
        p.normalized_name = $normalized_name,
        p.aliases = $aliases,
        p.created_at = $timestamp,
        p.updated_at = $timestamp
    """
    db.query(cypher_query, {
        "id": person_id,
        "name": suspect.get("name"),
        "normalized_name": norm_name,
        "aliases": suspect.get("aliases", []),
        "timestamp": timestamp,
    })

    return person_id


def update_existing_person(person_id: str, suspect: dict, source_doc: str):
    """Merges new aliases into an existing Person node (used on AUTO_MERGE).

    Appends only aliases that don't already exist on the node,
    and updates the updated_at timestamp.
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher_query = """
    MATCH (p:Person {id: $id})
    SET p.aliases = COALESCE(p.aliases, []) + [x IN $new_aliases WHERE NOT x IN COALESCE(p.aliases, [])],
        p.updated_at = $timestamp
    """
    db.query(cypher_query, {
        "id": person_id,
        "new_aliases": suspect.get("aliases", []),
        "timestamp": timestamp,
    })
