"""
Unit Tests for Phase 3 Specialized Worker Agent Nodes
------------------------------------------------------
Tests:
1. Graph Investigator Node (state accumulation, deduplication, 1-2 hop discovery)
2. Risk Analyst Node (PageRank, Betweenness, community partition, anomaly detection)
3. Evidence Verifier Node (documentary citations, SHA-256 audit, BSA §65B certificates)
4. Financial & Cyber Analyst Node (mule accounts, smurfing, crypto cash-outs, SIM box IMEI)
5. End-to-End Production Multi-Agent Execution with all 4 live worker nodes
"""

import os
import pytest

# Force mock graph data source during testing
os.environ["GRAPH_DATA_SOURCE"] = "mock"

from backend.app.agents.state import initial_state, InvestigationState
from backend.app.agents.nodes.graph_investigator import graph_investigator_node
from backend.app.agents.nodes.risk_analyst import risk_analyst_node
from backend.app.agents.nodes.evidence_verifier import evidence_verifier_node
from backend.app.agents.nodes.financial_analyst import financial_analyst_node
from backend.app.agents.nodes.supervisor import create_investigation_graph, MAX_ITERATIONS


# =========================================================================
# 1. Graph Investigator Node Tests
# =========================================================================

class TestGraphInvestigatorNode:
    """Tests topology expansion and state accumulation in Graph Investigator."""

    def test_investigates_target_and_accumulates_entities(self):
        state = initial_state("Investigate Rahul Sharma", "P001")
        result = graph_investigator_node(state)

        # Discovered entities should contain target suspect
        entities = result["discovered_entities"]
        assert len(entities) >= 1
        assert any(e.get("id") == "P001" for e in entities)

        # Discovered relationships should be a list
        assert isinstance(result["discovered_relationships"], list)

        # Iteration should increment
        assert result["iteration"] == 1

        # Tool history should be recorded
        assert len(result["tool_history"]) == 1
        assert result["tool_history"][0]["tool_name"] == "graph_investigator"

    def test_deduplicates_on_multiple_runs(self):
        state = initial_state("Investigate Rahul Sharma", "P001")
        # Run 1
        res1 = graph_investigator_node(state)
        state["discovered_entities"] = res1["discovered_entities"]
        state["discovered_relationships"] = res1["discovered_relationships"]
        state["iteration"] = res1["iteration"]
        count_after_first = len(state["discovered_entities"])

        # Run 2 on same state
        res2 = graph_investigator_node(state)
        count_after_second = len(res2["discovered_entities"])

        # Entity count should not duplicate existing IDs
        assert count_after_first == count_after_second


# =========================================================================
# 2. Risk Analyst Node Tests
# =========================================================================

class TestRiskAnalystNode:
    """Tests behavioral profiling, centrality algorithms and anomalies."""

    def test_calculates_risk_profile_and_centrality(self):
        state = initial_state("Profile threat for P001", "P001")
        result = risk_analyst_node(state)

        risk_data = result["risk_analysis"]
        assert risk_data is not None
        assert "risk_score" in risk_data
        assert 0.0 <= risk_data["risk_score"] <= 100.0
        assert risk_data["risk_level"] in ("HIGH", "MEDIUM", "LOW", "UNKNOWN")

        # Centrality metrics
        centrality = risk_data["centrality"]
        assert "pagerank" in centrality
        assert "betweenness" in centrality

        # Anomalies
        assert isinstance(risk_data["anomalies"], list)
        assert len(risk_data["anomalies"]) >= 1

        # Iteration and history
        assert result["iteration"] == 1
        assert result["tool_history"][0]["tool_name"] == "risk_analyst"


# =========================================================================
# 3. Evidence Verifier Node Tests
# =========================================================================

class TestEvidenceVerifierNode:
    """Tests BSA §65B hash auditing and court admissibility certificates."""

    def test_generates_bsa_65b_certificates(self):
        state = initial_state("Verify evidence for P001", "P001")
        state["discovered_relationships"] = [
            {"source": "P001", "target": "PH001", "type": "USES_PHONE"}
        ]
        result = evidence_verifier_node(state)

        evidence_items = result["evidence_items"]
        assert len(evidence_items) >= 1
        for ev in evidence_items:
            assert "doc_id" in ev
            assert "evidence_hash" in ev
            assert len(ev["evidence_hash"]) >= 16
            assert ev["bsa_65b_admissible"] is True

        verifications = result["verification_results"]
        assert len(verifications) >= 1
        assert verifications[0]["algorithm"] == "SHA-256"
        assert verifications[0]["is_tamper_free"] is True
        assert "Section 65B" in verifications[0]["admissibility_standard"]


# =========================================================================
# 4. Financial & Cyber Analyst Node Tests
# =========================================================================

class TestFinancialAnalystNode:
    """Tests mule account analysis, smurfing, and crypto off-ramp tracing."""

    def test_analyzes_financial_and_cyber_infrastructure(self):
        state = initial_state("Trace mule money trail for P001", "P001")
        state["discovered_relationships"] = [
            {"source": "P001", "target": "ACC_MULE_101", "type": "TRANSACTED_WITH", "amount": 49500.0}
        ]
        state["risk_analysis"] = {"anomalies": ["Circular transaction loop detected"]}

        result = financial_analyst_node(state)

        assert result["iteration"] == 1
        assert len(result["tool_history"]) == 1
        audit = result["tool_history"][0]
        assert audit["tool_name"] == "financial_analyst"
        assert "Financial forensics complete" in audit["summary_result"]
        assert "TRC-20" in audit["summary_result"] or "crypto" in audit["summary_result"]


# =========================================================================
# 5. End-to-End Production Multi-Agent Execution (Phase 3 Full Pipeline)
# =========================================================================

class TestProductionInvestigationPipeline:
    """Executes full multi-agent pipeline with real production worker nodes."""

    def test_production_multi_agent_investigation_run(self):
        # Build production graph (worker_stubs=False)
        production_graph = create_investigation_graph(worker_stubs=False)

        start_state = initial_state(
            user_query="Investigate suspect Rahul Sharma (P001). Map his associates, run risk analytics, audit FIR evidence under BSA 65B, and compile intelligence dossier.",
            subject_entity_id="P001",
        )

        final_state = production_graph.invoke(start_state)

        # 1. State Completion
        assert final_state["current_step"] == "COMPLETED"
        assert final_state["final_answer"] is not None

        # 2. Plan Created
        assert len(final_state["investigation_plan"]) >= 3

        # 3. Real Graph Investigator Discovery
        assert len(final_state["discovered_entities"]) >= 1
        assert any(e.get("id") == "P001" for e in final_state["discovered_entities"])

        # 4. Real Risk Analyst Scoring
        assert bool(final_state["risk_analysis"])
        assert "risk_score" in final_state["risk_analysis"]
        assert "centrality" in final_state["risk_analysis"]

        # 5. Real Evidence Verifier BSA §65B Certification
        assert len(final_state["evidence_items"]) >= 1
        assert len(final_state["verification_results"]) >= 1
        assert final_state["verification_results"][0]["is_tamper_free"] is True

        # 6. Hypotheses Evaluated & Promoted
        assert any(h["status"] == "SUPPORTED" for h in final_state["hypotheses"])

        # 7. Audit Trail Verified
        worker_names = [entry["tool_name"] for entry in final_state["tool_history"]]
        assert "supervisor_plan" in worker_names
        assert "graph_investigator" in worker_names
        assert "risk_analyst" in worker_names
        assert "evidence_verifier" in worker_names
        assert "supervisor_evaluate" in worker_names
        assert "supervisor_report" in worker_names

        # 8. Loop Guardrail Check
        assert final_state["iteration"] <= MAX_ITERATIONS
