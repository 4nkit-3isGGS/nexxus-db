"""
Graph Query Service Layer
--------------------------
Python functions wrapping reusable Cypher queries.
Used by API routes and LangGraph agents to query the criminal network graph.
"""

from backend.app.neo4j_driver import db


def get_entity(entity_id: str) -> dict | None:
    """Fetches a single Person node by ID with all its properties."""
    cypher = """
    MATCH (p:Person {id: $id})
    OPTIONAL MATCH (p)-[:OWNS_PHONE]->(ph:Phone)
    RETURN p {.*, phones: collect(ph.number)} AS person
    """
    result = db.query(cypher, {"id": entity_id})
    return result[0]["person"] if result else None


def get_neighbors(entity_id: str) -> list[dict]:
    """Returns all direct 1-hop connections of a Person."""
    cypher = """
    MATCH (p:Person {id: $id})-[r]-(other)
    RETURN type(r) AS relationship,
           labels(other)[0] AS entity_type,
           other {.*} AS entity,
           properties(r) AS details
    """
    return db.query(cypher, {"id": entity_id})


def get_subgraph(entity_id: str, depth: int = 2) -> list[dict]:
    """Returns multi-hop subgraph around a Person up to given depth."""
    cypher = f"""
    MATCH path = (p:Person {{id: $id}})-[*1..{min(depth, 5)}]-(connected)
    UNWIND nodes(path) AS n
    UNWIND relationships(path) AS r
    WITH DISTINCT n, r
    RETURN collect(DISTINCT n {{.*, labels: labels(n)}}) AS nodes,
           collect(DISTINCT {{
               source: startNode(r).id,
               target: endNode(r).id,
               type: type(r),
               properties: properties(r)
           }}) AS edges
    """
    result = db.query(cypher, {"id": entity_id})
    return result[0] if result else {"nodes": [], "edges": []}


def get_shortest_path(id1: str, id2: str) -> list[dict]:
    """Finds the shortest path between two Person nodes."""
    cypher = """
    MATCH path = shortestPath(
        (p1:Person {id: $id1})-[*]-(p2:Person {id: $id2})
    )
    RETURN [n IN nodes(path) | n {.*, labels: labels(n)}] AS nodes,
           [r IN relationships(path) | {
               source: startNode(r).id,
               target: endNode(r).id,
               type: type(r),
               properties: properties(r)
           }] AS edges
    """
    result = db.query(cypher, {"id1": id1, "id2": id2})
    return result[0] if result else {"nodes": [], "edges": []}


def get_shared_locations(entity_id: str) -> list[dict]:
    """Finds other people present at the same locations as the given person."""
    cypher = """
    MATCH (p:Person {id: $id})-[:PRESENT_AT]->(l:Location)<-[:PRESENT_AT]-(other:Person)
    RETURN l.name AS location,
           collect(DISTINCT other {.id, .name}) AS co_located_persons
    """
    return db.query(cypher, {"id": entity_id})


def get_graph_stats() -> list[dict]:
    """Returns node/relationship counts for the dashboard."""
    cypher = """
    CALL {
        MATCH (n)
        RETURN labels(n)[0] AS type, 'node' AS category, count(n) AS count
    UNION ALL
        MATCH ()-[r]->()
        RETURN type(r) AS type, 'relationship' AS category, count(r) AS count
    }
    RETURN type, category, count
    ORDER BY category, type
    """
    return db.query(cypher)


def search_entities(query: str, limit: int = 20) -> list[dict]:
    """Searches Person nodes by name (case-insensitive contains)."""
    cypher = """
    MATCH (p:Person)
    WHERE toLower(p.name) CONTAINS toLower($query)
       OR any(alias IN p.aliases WHERE toLower(alias) CONTAINS toLower($query))
    OPTIONAL MATCH (p)-[:OWNS_PHONE]->(ph:Phone)
    RETURN p {.*, phones: collect(ph.number)} AS person
    LIMIT $limit
    """
    return db.query(cypher, {"query": query, "limit": limit})


def get_evidence(entity_id1: str, entity_id2: str) -> list[dict]:
    """Returns provenance data for relationships between two entities."""
    cypher = """
    MATCH (a {id: $id1})-[r]-(b {id: $id2})
    RETURN type(r) AS relationship,
           r.source_doc_id AS source_doc,
           r.confidence AS confidence,
           r.timestamp AS timestamp,
           properties(r) AS full_properties
    """
    return db.query(cypher, {"id1": entity_id1, "id2": entity_id2})
