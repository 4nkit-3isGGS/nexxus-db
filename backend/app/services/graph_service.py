"""
Graph Query Service Layer
--------------------------
Python functions wrapping reusable Cypher queries.
Used by API routes and LangGraph agents to query the criminal network graph.
"""

from backend.app.neo4j_driver import db


def get_entity(entity_id: str) -> dict | None:
    """Fetches a single entity node (Person, Phone, Location, Vehicle, Organization) by ID."""
    cypher = """
    MATCH (e {id: $id})
    OPTIONAL MATCH (e)-[:OWNS_PHONE]->(ph:Phone)
    WITH e, labels(e) AS lbls, collect(ph.number) AS phones
    RETURN e {.*, labels: lbls, phones: phones} AS entity
    """
    try:
        result = db.query(cypher, {"id": entity_id})
        return result[0]["entity"] if result else None
    except Exception as e:
        print(f"[Neo4j Error] get_entity failed: {e}")
        return None


def get_neighbors(entity_id: str) -> list[dict]:
    """Returns all direct 1-hop connections of an entity."""
    cypher = """
    MATCH (e {id: $id})-[r]-(other)
    RETURN type(r) AS relationship,
           labels(other)[0] AS entity_type,
           other {.*} AS entity,
           properties(r) AS details
    """
    try:
        return db.query(cypher, {"id": entity_id})
    except Exception as e:
        print(f"[Neo4j Error] get_neighbors failed: {e}")
        return []


def get_subgraph(entity_id: str, depth: int = 2) -> dict:
    """Returns multi-hop subgraph around an entity up to given depth."""
    cypher = f"""
    MATCH path = (e {{id: $id}})-[*1..{min(depth, 5)}]-(connected)
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
    try:
        result = db.query(cypher, {"id": entity_id})
        return result[0] if result else {"nodes": [], "edges": []}
    except Exception as e:
        print(f"[Neo4j Error] get_subgraph failed: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}


def get_shortest_path(id1: str, id2: str) -> dict:
    """Finds the shortest path between two entities."""
    cypher = """
    MATCH path = shortestPath(
        (e1 {id: $id1})-[*]-(e2 {id: $id2})
    )
    UNWIND nodes(path) AS n
    UNWIND relationships(path) AS r
    WITH collect(DISTINCT n {.*, labels: labels(n)}) AS nodes,
         collect(DISTINCT {
             source: startNode(r).id,
             target: endNode(r).id,
             type: type(r),
             properties: properties(r)
         }) AS edges
    RETURN nodes, edges
    """
    try:
        result = db.query(cypher, {"id1": id1, "id2": id2})
        return result[0] if result else {"nodes": [], "edges": []}
    except Exception as e:
        print(f"[Neo4j Error] get_shortest_path failed: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}


def get_shared_locations(entity_id: str) -> list[dict]:
    """Finds other entities/people present at the same locations as the given entity."""
    cypher = """
    MATCH (e {id: $id})-[:PRESENT_AT]->(l:Location)<-[:PRESENT_AT]-(other:Person)
    RETURN l.name AS location,
           collect(DISTINCT other {.id, .name}) AS co_located_persons
    """
    try:
        return db.query(cypher, {"id": entity_id})
    except Exception as e:
        print(f"[Neo4j Error] get_shared_locations failed: {e}")
        return []


def get_graph_stats() -> list[dict]:
    """Returns node/relationship counts for the dashboard."""
    cypher = """
    CALL () {
        MATCH (n)
        RETURN labels(n)[0] AS type, 'node' AS category, count(n) AS count
    UNION ALL
        MATCH ()-[r]->()
        RETURN type(r) AS type, 'relationship' AS category, count(r) AS count
    }
    RETURN type, category, count
    ORDER BY category, type
    """
    try:
        return db.query(cypher)
    except Exception as e:
        print(f"[Neo4j Error] get_graph_stats failed: {e}")
        return []


def search_entities(query: str, limit: int = 20) -> list[dict]:
    """Searches entities (Person, Phone, Location, Vehicle, Organization) by name, alias, number, etc."""
    cypher = """
    MATCH (e)
    WHERE (e.name IS NOT NULL AND toLower(e.name) CONTAINS toLower($query))
       OR (e.normalized_name IS NOT NULL AND toLower(e.normalized_name) CONTAINS toLower($query))
       OR (e.number IS NOT NULL AND toLower(e.number) CONTAINS toLower($query))
       OR (e.registration_number IS NOT NULL AND toLower(e.registration_number) CONTAINS toLower($query))
       OR any(alias IN COALESCE(e.aliases, []) WHERE toLower(alias) CONTAINS toLower($query))
    OPTIONAL MATCH (e)-[:OWNS_PHONE]->(ph:Phone)
    WITH e, labels(e) AS lbls, collect(ph.number) AS phones
    RETURN e {.*, labels: lbls, phones: phones} AS person
    LIMIT $limit
    """
    try:
        result = db.query(cypher, {"query": query, "limit": limit})
        return [r["person"] for r in result]
    except Exception as e:
        print(f"[Neo4j Error] search_entities failed: {e}")
        return []


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
    try:
        return db.query(cypher, {"id1": entity_id1, "id2": entity_id2})
    except Exception as e:
        print(f"[Neo4j Error] get_evidence failed: {e}")
        return []
