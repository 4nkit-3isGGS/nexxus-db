"""
Unit Tests for Supervisor Agent & Routing Core (Phase 2)
---------------------------------------------------------
Tests:
1. Subject entity extraction and disambiguation
2. Supervisor planning node (plan generation & initial hypotheses)
3. Supervisor evaluation & routing node (dynamic dispatching)
4. Guardrails: MAX_ITERATIONS limit
5. Supervisor report synthesis node (grounded Markdown dossier & BSA §65B hash manifest)
6. End-to-End LangGraph StateGraph compiled execution
"""

import os
import pytest
from langgraph.graph import END

# Force mock graph data source so tests never depend on an external Neo4j instance
os.environ["GRAPH_DATA_SOURCE"] = "mock"

from backend.app.agents.state import initial_state, InvestigationState
from backend.app.agents.nodes.supervisor import (
    extract_potential_names_or_ids,
    resolve_subject_entity,
    supervisor_plan_node,
    supervisor_evaluate_node,
    supervisor_report_node,
    route_next_step,
    create_investigation_graph,
    MAX_ITERATIONS,
)


# =========================================================================
# 1. Subject Extraction & Disambiguation Tests
# =========================================================================

class TestSubjectExtraction:
    """Tests subject extraction and entity resolution logic."""

    def test_extract_entity_ids(self):
        query = "Investigate P001 who was spotted with vehicle V002 in FIR-102"
        candidates = extract_potential_names_or_ids(query)
        assert "P001" in candidates
        assert "V002" in candidates
        assert "FIR-102" in candidates

    def test_extract_vehicle_plates(self):
        query = "Track suspect driving car DL-01-AB-1234 near border"
        candidates = extract_potential_names_or_ids(query)
        assert any("DL-01-AB-1234" in c or "DL" in c for c in candidates)

    def test_extract_person_names(self):
        query = "Determine key contacts and financial conduits for Vikram Malhotra"
        candidates = extract_potential_names_or_ids(query)
        assert "Vikram Malhotra" in candidates

    def test_resolve_with_explicit_id(self):
        subject_id, meta = resolve_subject_entity("Investigate someone", explicit_id="P001")
        assert subject_id == "P001"
        assert meta is not None
        assert meta.get("id") == "P001"

    def test_resolve_fallback_when_not_found(self):
        subject_id, meta = resolve_subject_entity("Find unidentified John Doe 99999")
        # Should gracefully return None without crashing
        assert subject_id is None or isinstance(subject_id, str)


# =========================================================================
# 2. Planning Node Tests: supervisor_plan_node
# =========================================================================

class TestSupervisorPlanNode:
    """Tests the strategic planning node."""

    def test_plan_generation_with_explicit_subject(self):
        state = initial_state(
            user_query="Investigate Rahul Sharma and map his burner phones",
            subject_entity_id="P001",
        )
        result = supervisor_plan_node(state)

        assert result["subject_entity_id"] == "P001"
        assert len(result["investigation_plan"]) >= 3
        assert len(result["investigation_plan"]) <= 5
        assert result["current_step"] == "graph_investigator"
        assert result["iteration"] == 1
        assert len(result["tool_history"]) == 1

        # Check hypotheses
        assert len(result["hypotheses"]) >= 1
        for hyp in result["hypotheses"]:
            assert hyp["status"] == "WEAK"
            assert len(hyp["claim"]) > 10
            assert hyp["supported_evidence_id"] == []

    def test_plan_adapts_to_financial_query(self):
        state = initial_state(
            user_query="Trace circular money laundering and mule accounts for Vikram Malhotra"
        )
        result = supervisor_plan_node(state)

        plan_str = " ".join(result["investigation_plan"]).lower()
        assert "financial" in plan_str or "money" in plan_str or "risk" in plan_str
        assert any("financial" in h["claim"].lower() or "money" in h["claim"].lower() or "syndicate" in h["claim"].lower() for h in result["hypotheses"])


# =========================================================================
# 3. Dynamic Evaluation & Dispatch Tests: supervisor_evaluate_node
# =========================================================================

class TestSupervisorEvaluateNode:
    """Tests progressive routing and dynamic worker dispatch."""

    def test_routes_to_graph_if_no_entities(self):
        state = initial_state("Test query", "P001")
        state["iteration"] = 1
        # No entities discovered yet
        result = supervisor_evaluate_node(state)
        assert result["current_step"] == "graph_investigator"
        assert result["iteration"] == 2

    def test_routes_to_risk_if_entities_found_but_no_risk(self):
        state = initial_state("Test query", "P001")
        state["iteration"] = 2
        state["discovered_entities"] = [{"id": "P001", "name": "Rahul"}]
        state["discovered_relationships"] = [{"source": "P001", "target": "PH001"}]
        # Risk analysis is empty
        result = supervisor_evaluate_node(state)
        assert result["current_step"] == "risk_analyst"

    def test_routes_to_evidence_if_risk_found_but_no_evidence(self):
        state = initial_state("Test query", "P001")
        state["iteration"] = 3
        state["discovered_entities"] = [{"id": "P001", "name": "Rahul"}, {"id": "PH001"}]
        state["discovered_relationships"] = [{"source": "P001", "target": "PH001"}]
        state["risk_analysis"] = {"risk_score": 70, "centrality": {"degree": 3}}
        # Evidence items is empty
        result = supervisor_evaluate_node(state)
        assert result["current_step"] == "evidence_verifier"

    def test_routes_to_report_when_all_stages_complete(self):
        state = initial_state("Test query", "P001")
        state["iteration"] = 4
        state["discovered_entities"] = [{"id": "P001", "name": "Rahul"}, {"id": "PH001"}]
        state["discovered_relationships"] = [{"source": "P001", "target": "PH001"}]
        state["risk_analysis"] = {"risk_score": 75, "anomalies": ["Call bursts"]}
        state["evidence_items"] = [{"doc_id": "FIR-102", "evidence_hash": "abc"}]
        state["hypotheses"] = [{
            "id": "H-001",
            "claim": "Rahul is kingpin",
            "status": "WEAK",
            "rationale": "Initial",
            "supported_evidence_id": [],
        }]

        result = supervisor_evaluate_node(state)
        assert result["current_step"] == "supervisor_report"
        # Hypotheses should be promoted to SUPPORTED
        assert result["hypotheses"][0]["status"] == "SUPPORTED"
        assert len(result["hypotheses"][0]["supported_evidence_id"]) > 0

    def test_guardrail_max_iterations_halts_loop(self):
        state = initial_state("Test query", "P001")
        state["iteration"] = MAX_ITERATIONS  # Hit ceiling
        result = supervisor_evaluate_node(state)
        assert result["current_step"] == "supervisor_report"
        assert result["iteration"] == MAX_ITERATIONS + 1
        assert any("MAX_ITERATIONS" in h["summary_result"] for h in result["tool_history"])


# =========================================================================
# 4. Routing Helper Tests: route_next_step
# =========================================================================

class TestRoutingFunction:
    """Tests the LangGraph conditional edge routing function."""

    def test_valid_worker_routes(self):
        for worker in ["graph_investigator", "risk_analyst", "evidence_verifier", "financial_analyst"]:
            state = {"current_step": worker}
            assert route_next_step(state) == worker

    def test_terminal_step_returns_end(self):
        for terminal in ["COMPLETED", "COMPLETE", "__end__", END]:
            state = {"current_step": terminal}
            assert route_next_step(state) == END

    def test_supervisor_report_route(self):
        state = {"current_step": "supervisor_report"}
        assert route_next_step(state) == "supervisor_report"

    def test_unknown_step_fallback(self):
        state = {"current_step": "non_existent_step"}
        assert route_next_step(state) == "supervisor_evaluate"


# =========================================================================
# 5. Final Report Synthesis Tests: supervisor_report_node
# =========================================================================

class TestSupervisorReportNode:
    """Tests dossier formatting and legal citation structure."""

    def test_report_generation_structure(self):
        state = initial_state("Investigate Rahul Sharma in FIR-102", "P001")
        state["iteration"] = 5
        state["discovered_entities"] = [
            {"id": "P001", "name": "Rahul Sharma", "label": "Person", "risk_score": 80, "aadhaar": "XXXX-XXXX-1234"},
            {"id": "PH001", "number": "+91-9876543210", "label": "Phone"},
        ]
        state["discovered_relationships"] = [{"source": "P001", "target": "PH001", "type": "USES_PHONE"}]
        state["risk_analysis"] = {
            "risk_score": 80,
            "centrality": {"degree": 5, "pagerank": 0.42, "betweenness": 0.71},
            "anomalies": ["High-frequency night call bursts"],
        }
        state["hypotheses"] = [{
            "id": "H-001",
            "claim": "Rahul operates a criminal syndicate",
            "status": "SUPPORTED",
            "rationale": "Validated by 2 nodes and PageRank 0.42",
            "supported_evidence_id": ["FIR-102"],
        }]
        state["evidence_items"] = [{
            "doc_id": "FIR-102/2026",
            "evidence_hash": "e50fd6c89283fbc3d4924823485723948572093845bca1283948572394857239",
            "bsa_65b_admissible": True,
        }]

        result = supervisor_report_node(state)
        dossier = result["final_answer"]

        assert dossier is not None
        assert result["current_step"] == "COMPLETED"

        # Verify key sections are present
        assert "# 🚨 CRIMINAL NETWORK INTELLIGENCE DOSSIER" in dossier
        assert "Rahul Sharma" in dossier
        assert "P001" in dossier
        assert "Section 65B Bharatiya Sakshya Adhiniyam" in dossier
        assert "e50fd6c89283fbc3" in dossier
        assert "PageRank Centrality" in dossier
        assert "H-001" in dossier
        assert "Freeze Assets" in dossier


# =========================================================================
# 6. End-to-End Compiled StateGraph Execution
# =========================================================================

class TestEndToEndSupervisorGraph:
    """Executes the full LangGraph state machine from START to COMPLETED."""

    def test_full_investigation_run(self):
        # Create and compile the graph
        investigation_graph = create_investigation_graph(worker_stubs=True)

        # Initialize investigation state
        start_state = initial_state(
            user_query="Investigate suspect Rahul Sharma (P001), uncover associates and test risk anomalies.",
            subject_entity_id="P001",
        )

        # Run state machine through all cycles
        final_state = investigation_graph.invoke(start_state)

        # Verify graph completed execution
        assert final_state["current_step"] == "COMPLETED"
        assert final_state["final_answer"] is not None
        assert len(final_state["final_answer"]) > 200

        # Verify investigation plan was created
        assert len(final_state["investigation_plan"]) >= 3

        # Verify workers ran and contributed to state
        assert len(final_state["discovered_entities"]) >= 1
        assert bool(final_state["risk_analysis"])
        assert len(final_state["evidence_items"]) >= 1

        # Verify hypotheses were evaluated
        assert len(final_state["hypotheses"]) >= 1
        assert any(h["status"] == "SUPPORTED" for h in final_state["hypotheses"])

        # Verify safety guardrail
        assert final_state["iteration"] <= MAX_ITERATIONS

        # Verify audit trail is populated
        tool_names = [call["tool_name"] for call in final_state["tool_history"]]
        assert "supervisor_plan" in tool_names
        assert "supervisor_evaluate" in tool_names
        assert "supervisor_report" in tool_names
