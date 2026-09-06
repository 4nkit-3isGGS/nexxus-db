"""
Unit Tests for LangGraph Agent Tools Suite
-------------------------------------------
Tests the full Phase 1 tool boundary:
1. Graph Tools (get_entity, get_neighbors, get_subgraph, get_shortest_path, search_entities)
2. Risk Analytics Tools (get_risk_score, get_network_centrality, get_communities, detect_anomalies)
3. Evidence & BSA §65B Tools (get_evidence, verify_evidence_integrity, generate_evidence_hash)
"""

import os
import hashlib
import pytest
from unittest.mock import patch
from pydantic import ValidationError

# Force mock graph data source during testing so tests never depend on an external Neo4j instance
os.environ["GRAPH_DATA_SOURCE"] = "mock"

from backend.app.agents.tools import (
    ALL_INVESTIGATION_TOOLS,
    GRAPH_TOOLS,
    RISK_TOOLS,
    EVIDENCE_TOOLS,
    get_entity_tool,
    get_neighbors_tool,
    get_subgraph_tool,
    get_shortest_path_tool,
    search_entities_tool,
    get_risk_score_tool,
    get_network_centrality_tool,
    get_communities_tool,
    detect_anomalies_tool,
    get_relationship_evidence_tool,
    verify_evidence_integrity_tool,
    generate_evidence_hash_tool,
)


# =========================================================================
# 1. Tool Registry Verification
# =========================================================================

class TestToolRegistries:
    """Verifies that all tools are registered with proper names and schemas."""

    def test_tool_counts(self):
        assert len(GRAPH_TOOLS) == 5
        assert len(RISK_TOOLS) == 4
        assert len(EVIDENCE_TOOLS) == 3
        assert len(ALL_INVESTIGATION_TOOLS) == 12

    def test_tool_names(self):
        names = [t.name for t in ALL_INVESTIGATION_TOOLS]
        expected_names = [
            "get_entity",
            "get_neighbors",
            "get_subgraph",
            "get_shortest_path",
            "search_entities",
            "get_risk_score",
            "get_network_centrality",
            "get_communities",
            "detect_anomalies",
            "get_evidence",
            "verify_evidence_integrity",
            "generate_evidence_hash",
        ]
        for exp in expected_names:
            assert exp in names, f"Expected tool '{exp}' not found in registry."


# =========================================================================
# 2. Graph Tools Tests
# =========================================================================

class TestGraphTools:
    """Tests the Neo4j Knowledge Graph boundary tools."""

    def test_get_entity_found(self):
        mock_entity = {"id": "P001", "name": "Rahul Sharma", "labels": ["Person"]}
        with patch("backend.app.agents.tools.graph_tools.get_entity", return_value=mock_entity):
            res = get_entity_tool.invoke({"entity_id": "P001"})
            assert res["found"] is True
            assert res["result"]["name"] == "Rahul Sharma"

    def test_get_entity_not_found(self):
        with patch("backend.app.agents.tools.graph_tools.get_entity", return_value=None):
            res = get_entity_tool.invoke({"entity_id": "P_MISSING"})
            assert res["found"] is False
            assert "not found" in res["message"].lower()

    def test_get_entity_empty_id(self):
        with pytest.raises(Exception):
            get_entity_tool.invoke({"entity_id": ""})

    def test_get_neighbors_success(self):
        mock_neighbors = [
            {"relationship": "OWNS_PHONE", "entity": {"id": "PH001", "number": "+919999999999"}}
        ]
        with patch("backend.app.agents.tools.graph_tools.get_neighbors", return_value=mock_neighbors):
            res = get_neighbors_tool.invoke({"entity_id": "P001"})
            assert res["found"] is True
            assert res["count"] == 1
            assert res["result"][0]["relationship"] == "OWNS_PHONE"

    def test_get_neighbors_empty_id(self):
        with pytest.raises(Exception):
            get_neighbors_tool.invoke({"entity_id": ""})

    def test_get_subgraph_valid_depth(self):
        mock_subgraph = {"nodes": [{"id": "P001"}, {"id": "P002"}], "edges": [{"source": "P001", "target": "P002"}]}
        with patch("backend.app.agents.tools.graph_tools.get_subgraph", return_value=mock_subgraph) as mock_get:
            res = get_subgraph_tool.invoke({"entity_id": "P001", "depth": 3})
            assert res["depth"] == 3
            assert res["found"] is True
            mock_get.assert_called_with("P001", depth=3)

    def test_get_subgraph_depth_out_of_bounds(self):
        with pytest.raises(Exception):
            get_subgraph_tool.invoke({"entity_id": "P001", "depth": 10})

    def test_get_shortest_path_success(self):
        mock_path = {
            "nodes": [{"id": "P001"}, {"id": "P002"}],
            "edges": [{"source": "P001", "target": "P002", "type": "CALLED"}]
        }
        with patch("backend.app.agents.tools.graph_tools.get_shortest_path", return_value=mock_path):
            res = get_shortest_path_tool.invoke({"source_id": "P001", "target_id": "P002"})
            assert res["path_found"] is True
            assert res["length"] == 1

    def test_get_shortest_path_identical_entities(self):
        res = get_shortest_path_tool.invoke({"source_id": "P001", "target_id": "P001"})
        assert res["path_found"] is True
        assert res["length"] == 0
        assert "identical" in res["message"]

    def test_search_entities_success(self):
        mock_results = [{"id": "P001", "name": "Rahul"}]
        with patch("backend.app.agents.tools.graph_tools.search_entities", return_value=mock_results) as mock_search:
            res = search_entities_tool.invoke({"query": "Rahul", "limit": 10})
            assert res["found"] is True
            mock_search.assert_called_with("Rahul", limit=10)

    def test_search_entities_limit_out_of_bounds(self):
        with pytest.raises(Exception):
            search_entities_tool.invoke({"query": "Rahul", "limit": 100})


# =========================================================================
# 3. Risk Analytics Tools Tests (Arnish Engine)
# =========================================================================

class TestRiskTools:
    """Tests the risk and graph analytics boundary tools."""

    def test_get_risk_score_success(self):
        res = get_risk_score_tool.invoke({"entity_id": "Rahul"})
        assert res["found"] is True
        assert "overall_risk_score" in res
        assert 0.0 <= res["overall_risk_score"] <= 100.0
        assert res["risk_level"] in ("HIGH", "MEDIUM", "LOW")
        assert "risk_breakdown" in res
        assert "degree_centrality" in res["risk_breakdown"]
        assert "pagerank_score" in res["risk_breakdown"]

    def test_get_risk_score_not_found(self):
        res = get_risk_score_tool.invoke({"entity_id": "NON_EXISTENT_SUSPECT_XYZ"})
        assert res["found"] is False
        assert res["overall_risk_score"] == 0.0

    def test_get_risk_score_empty_id(self):
        with pytest.raises(Exception):
            get_risk_score_tool.invoke({"entity_id": ""})

    def test_get_network_centrality_pagerank_and_betweenness(self):
        res = get_network_centrality_tool.invoke({"top_n": 3, "metric": "all"})
        assert "top_influential_kingpins" in res
        assert "top_communication_brokers" in res
        assert len(res["top_influential_kingpins"]) <= 3
        assert len(res["top_communication_brokers"]) <= 3

        # Verify items have expected keys
        first_kingpin = res["top_influential_kingpins"][0]
        assert "entity_id" in first_kingpin
        assert "pagerank" in first_kingpin

    def test_get_communities_all(self):
        res = get_communities_tool.invoke({})
        assert "total_communities" in res
        assert res["total_communities"] > 0
        assert "communities" in res

    def test_get_communities_single_entity(self):
        res = get_communities_tool.invoke({"entity_id": "Rahul"})
        assert res["found"] is True
        assert res["entity_id"] == "Rahul"
        assert "cluster_name" in res
        assert isinstance(res["co_members"], list)

    def test_detect_anomalies_all(self):
        res = detect_anomalies_tool.invoke({"anomaly_type": "all"})
        assert "circular_transactions" in res
        assert "call_bursts" in res
        assert "cross_case_entities" in res
        assert "count" in res["circular_transactions"]
        assert "count" in res["call_bursts"]


# =========================================================================
# 4. Evidence & BSA §65B Tools Tests
# =========================================================================

class TestEvidenceTools:
    """Tests evidence provenance and cryptographic BSA §65B verification."""

    def test_generate_evidence_hash(self):
        sample_text = "FIR-102/2026: Suspect Rahul transferred 50,000 INR to account PH-9123."
        res = generate_evidence_hash_tool.invoke({"content": sample_text})
        expected_hash = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()

        assert res["algorithm"] == "SHA-256"
        assert res["hash"] == expected_hash
        assert res["length_characters"] == len(sample_text)

    def test_generate_evidence_hash_empty(self):
        with pytest.raises(Exception):
            generate_evidence_hash_tool.invoke({"content": ""})

    def test_verify_evidence_integrity_authentic(self):
        raw_text = "CDR Airtel Log: Call from +919123456789 to +919876543210 duration 340s"
        valid_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        res = verify_evidence_integrity_tool.invoke({
            "raw_content": raw_text,
            "expected_hash": valid_hash
        })
        assert res["is_valid"] is True
        assert res["integrity_status"] == "VERIFIED_AUTHENTIC"
        assert res["bsa_65b_admissible"] is True
        assert "PASSED" in res["audit_message"]

    def test_verify_evidence_integrity_tampered(self):
        original_text = "CDR Airtel Log: Call from +919123456789 to +919876543210 duration 340s"
        tampered_text = "CDR Airtel Log: Call from +919123456789 to +919876543210 duration 9999s"
        original_hash = hashlib.sha256(original_text.encode("utf-8")).hexdigest()

        res = verify_evidence_integrity_tool.invoke({
            "raw_content": tampered_text,
            "expected_hash": original_hash
        })
        assert res["is_valid"] is False
        assert res["integrity_status"] == "TAMPER_DETECTED"
        assert res["bsa_65b_admissible"] is False
        assert "FAILED" in res["audit_message"]

    def test_get_relationship_evidence_success(self):
        mock_evidence = [
            {
                "relationship": "CALLED",
                "source_doc": "CDR_LOG_2026",
                "confidence": 0.95,
                "timestamp": "2026-08-15T10:00:00Z",
                "full_properties": {
                    "duration": 120,
                    "evidence_hash": "a1b2c3d4e5f6",
                    "source_span": "Call lasted 120s between tower 4A and 7B",
                }
            }
        ]
        with patch("backend.app.agents.tools.evidence_tools.get_evidence", return_value=mock_evidence):
            res = get_relationship_evidence_tool.invoke({"entity_id1": "P001", "entity_id2": "P002"})
            assert res["evidence_found"] is True
            assert res["count"] == 1
            item = res["evidence"][0]
            assert item["source_doc_id"] == "CDR_LOG_2026"
            assert item["confidence"] == 0.95
            assert item["evidence_hash"] == "a1b2c3d4e5f6"

    def test_get_relationship_evidence_identical_ids(self):
        res = get_relationship_evidence_tool.invoke({"entity_id1": "P001", "entity_id2": "P001"})
        assert res["evidence_found"] is False
        assert "identical" in res["message"]

    def test_get_relationship_evidence_empty_ids(self):
        with pytest.raises(Exception):
            get_relationship_evidence_tool.invoke({"entity_id1": "", "entity_id2": "P002"})
