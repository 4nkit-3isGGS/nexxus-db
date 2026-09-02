"""
Integration Tests for Graph Service Queries
---------------------------------------------
Tests Cypher query wrappers for fetching entities, neighbors, subgraphs,
shortest paths, graph statistics, search, and relationship evidence.
"""

import pytest
from backend.app.neo4j_driver import db
from backend.app.services.graph_service import (
    get_entity,
    get_neighbors,
    get_subgraph,
    get_shortest_path,
    get_shared_locations,
    get_graph_stats,
    search_entities,
    get_evidence,
)


@pytest.fixture(scope="module", autouse=True)
def check_db_connection():
    """Ensures Neo4j is connected before running integration tests."""
    if not db.verify_connectivity():
        pytest.skip("Neo4j database is not reachable. Skipping integration tests.")


class TestGraphQueries:
    def test_get_entity_person(self):
        result = get_entity("P001")
        assert result is not None
        assert result["id"] == "P001"
        assert result["name"] == "Rahul Sharma"
        assert "Person" in result["labels"]

    def test_get_entity_phone(self):
        result = get_entity("PH002")
        assert result is not None
        assert result["id"] == "PH002"
        assert result["number"] == "+919123456789"
        assert "Phone" in result["labels"]

    def test_get_entity_nonexistent(self):
        result = get_entity("NONEXISTENT_99999")
        assert result is None

    def test_get_neighbors(self):
        neighbors = get_neighbors("P001")
        assert isinstance(neighbors, list)
        if len(neighbors) > 0:
            first = neighbors[0]
            assert "relationship" in first
            assert "entity" in first

    def test_get_subgraph(self):
        subgraph = get_subgraph("P001", depth=2)
        assert isinstance(subgraph, dict)
        assert "nodes" in subgraph
        assert "edges" in subgraph
        assert isinstance(subgraph["nodes"], list)
        assert isinstance(subgraph["edges"], list)

    def test_get_shortest_path(self):
        path = get_shortest_path("P001", "P002")
        assert isinstance(path, dict)
        assert "nodes" in path
        assert "edges" in path

    def test_get_shared_locations(self):
        shared = get_shared_locations("P001")
        assert isinstance(shared, list)

    def test_get_graph_stats(self):
        stats = get_graph_stats()
        assert isinstance(stats, list)
        assert len(stats) > 0
        categories = {s.get("category") for s in stats}
        assert "node" in categories or "relationship" in categories

    def test_search_entities_name(self):
        results = search_entities("rahul", limit=10)
        assert isinstance(results, list)
        assert len(results) > 0
        names = [r.get("name") for r in results if r.get("name")]
        assert any("Rahul" in name for name in names)

    def test_search_entities_number(self):
        results = search_entities("9123", limit=10)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_get_evidence(self):
        evidence = get_evidence("P001", "P002")
        assert isinstance(evidence, list)
