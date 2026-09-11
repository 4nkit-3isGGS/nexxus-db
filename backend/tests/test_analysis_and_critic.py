"""
Unit Tests for Phase 4 Analysis Agent (Hypothesis Engine)
---------------------------------------------------------
Tests:
1. Hypothesis formulation and evaluation
2. Bridge suspect detection from centrality
3. Burner phone detection from phone nodes & call relationships
4. Financial layering & mule account detection
5. Evidentiary guardrail (claims without evidence marked WEAK)
"""

import pytest
from backend.app.agents.state import initial_state
from backend.app.agents.nodes.analysis_agent import analysis_agent_node


class TestAnalysisAgentNode:
    """Test suite for Analysis Agent (Hypothesis Engine)."""

    def test_evaluates_and_promotes_corroborated_hypothesis(self):
        state = initial_state("Investigate Rahul Sharma", "P001")
        state["discovered_entities"] = [
            {"id": "P001", "name": "Rahul Sharma", "risk_score": 85},
            {"id": "P002", "name": "Vikram Singh", "risk_score": 75},
        ]
        state["discovered_relationships"] = [
            {"source": "P001", "target": "P002", "type": "ASSOCIATED_WITH"}
        ]
        state["risk_analysis"] = {"risk_score": 85, "centrality_metrics": {"betweenness": 0.45}}
        state["evidence_items"] = [
            {"doc_id": "FIR-101", "raw_content": "Suspect coordinated hawala shipments."}
        ]
        state["hypotheses"] = [
            {
                "id": "H-001",
                "claim": "Rahul Sharma is a central operator.",
                "status": "WEAK",
                "rationale": "Initial query suspicion.",
                "supported_evidence_id": [],
            }
        ]

        result = analysis_agent_node(state)

        # Hypothesis 1 should be promoted to SUPPORTED
        assert len(result["hypotheses"]) >= 1
        h1 = result["hypotheses"][0]
        assert h1["status"] == "SUPPORTED"
        assert "FIR-101" in h1["supported_evidence_id"]
        assert result["iteration"] == 1
        assert any(t["tool_name"] == "analysis_agent" for t in result["tool_history"])

    def test_synthesizes_bridge_suspect_hypothesis(self):
        state = initial_state("Investigate Rahul Sharma", "P001")
        state["discovered_entities"] = [
            {"id": "P001", "name": "Rahul Sharma"},
            {"id": "P002", "name": "Vikram"},
            {"id": "P003", "name": "Manoj"},
        ]
        state["risk_analysis"] = {
            "risk_score": 70,
            "centrality_metrics": {"betweenness": 0.65},
        }
        state["evidence_items"] = [{"doc_id": "CDR-991", "raw_content": "Toll calls verified"}]

        result = analysis_agent_node(state)
        claims = [h["claim"] for h in result["hypotheses"]]
        assert any("bridge" in c.lower() or "broker" in c.lower() for c in claims)

    def test_synthesizes_burner_phone_hypothesis(self):
        state = initial_state("Investigate Rahul Sharma", "P001")
        state["discovered_entities"] = [
            {"id": "P001", "name": "Rahul Sharma"},
            {"id": "PHONE:9876543210", "label": "Phone", "number": "9876543210"},
            {"id": "PHONE:9123456780", "label": "Phone", "number": "9123456780"},
        ]
        state["discovered_relationships"] = [
            {"source": "P001", "target": "PHONE:9876543210", "type": "USES_PHONE"},
            {"source": "P001", "target": "PHONE:9123456780", "type": "USES_PHONE"},
        ]
        state["evidence_items"] = [{"doc_id": "TELCO-01", "raw_content": "Dual SIM activation"}]

        result = analysis_agent_node(state)
        claims = [h["claim"] for h in result["hypotheses"]]
        assert any("burner" in c.lower() or "sim" in c.lower() for c in claims)

    def test_synthesizes_financial_layering_hypothesis(self):
        state = initial_state("Investigate Rahul Sharma", "P001")
        state["financial_analysis"] = {
            "mule_accounts": ["MULE-ACC-8819"],
            "circular_transactions": [{"loop": ["A", "B", "A"]}],
        }
        state["evidence_items"] = [{"doc_id": "BANK-04", "raw_content": "Mule ledger confirmed"}]

        result = analysis_agent_node(state)
        claims = [h["claim"] for h in result["hypotheses"]]
        assert any("mule" in c.lower() or "layering" in c.lower() or "fund" in c.lower() for c in claims)

    def test_guardrail_unsupported_when_evidence_missing(self):
        state = initial_state("Investigate Rahul Sharma", "P001")
        # No evidence items provided!
        state["evidence_items"] = []
        state["risk_analysis"] = {"risk_score": 20}
        state["hypotheses"] = [
            {
                "id": "H-001",
                "claim": "Rahul Sharma is the kingpin.",
                "status": "WEAK",
                "rationale": "Uncorroborated claim.",
                "supported_evidence_id": [],
            }
        ]

        result = analysis_agent_node(state)
        # All hypotheses must remain WEAK or REJECTED when evidence is zero
        for h in result["hypotheses"]:
            assert h["status"] in ("WEAK", "REJECTED")


class TestCriticVerifierNode:
    """Test suite for Phase 5 Critic / Verifier Agent & Quality Gatekeeper."""

    def test_approves_verified_corroborated_findings(self):
        from backend.app.agents.nodes.critic_verifier import critic_verifier_node, route_critic_decision

        state = initial_state("Investigate Rahul Sharma", "P001")
        state["iteration"] = 2
        state["evidence_items"] = [
            {
                "doc_id": "FIR-101",
                "source": "State Police FIR",
                "evidence_hash": "a" * 64,
                "bsa_65b_admissible": True,
            },
            {
                "doc_id": "BANK-01",
                "source": "Financial Intelligence Unit",
                "evidence_hash": "b" * 64,
                "bsa_65b_admissible": True,
            },
        ]
        state["hypotheses"] = [
            {
                "id": "H-001",
                "claim": "Rahul operates mule bank accounts.",
                "status": "SUPPORTED",
                "rationale": "Corroborated by bank ledger.",
                "supported_evidence_id": ["BANK-01"],
            }
        ]

        result = critic_verifier_node(state)
        latest_audit = result["verification_results"][-1]

        assert latest_audit["is_sufficient"] is True
        assert latest_audit["routing_decision"] == "supervisor_report"
        assert result["iteration"] == 3
        assert route_critic_decision(result) == "supervisor_report"

    def test_demotes_orphaned_hypotheses_without_evidence(self):
        from backend.app.agents.nodes.critic_verifier import critic_verifier_node

        state = initial_state("Investigate Rahul Sharma", "P001")
        state["iteration"] = 2
        # Evidence items do NOT contain "FICTIONAL-DOC"
        state["evidence_items"] = [{"doc_id": "REAL-DOC-01", "evidence_hash": "c" * 64, "bsa_65b_admissible": True}]
        state["hypotheses"] = [
            {
                "id": "H-ORPHAN",
                "claim": "Rahul is the international kingpin.",
                "status": "SUPPORTED",
                "rationale": "Fabricated claim.",
                "supported_evidence_id": ["FICTIONAL-DOC"],
            }
        ]

        result = critic_verifier_node(state)
        # Should be demoted to WEAK
        orphan_h = [h for h in result["hypotheses"] if h["id"] == "H-ORPHAN"][0]
        assert orphan_h["status"] == "WEAK"
        assert "Demoted" in orphan_h["rationale"]

    def test_detects_single_source_bias(self):
        from backend.app.agents.nodes.critic_verifier import critic_verifier_node

        state = initial_state("Investigate Rahul Sharma", "P001")
        state["iteration"] = 2
        state["risk_analysis"] = {"risk_score": 85}  # High risk
        state["evidence_items"] = [
            {
                "doc_id": "FIR-001",
                "source": "FIR-001",
                "evidence_hash": "d" * 64,
                "bsa_65b_admissible": True,
            }
        ]
        state["hypotheses"] = [
            {
                "id": "H-001",
                "claim": "High risk syndicate coordinator.",
                "status": "SUPPORTED",
                "rationale": "Cited from sole FIR.",
                "supported_evidence_id": ["FIR-001"],
            }
        ]

        result = critic_verifier_node(state)
        latest_audit = result["verification_results"][-1]
        assert latest_audit["single_source_bias"] is True

    def test_enforces_replan_when_evidence_insufficient_and_under_budget(self):
        from backend.app.agents.nodes.critic_verifier import critic_verifier_node, route_critic_decision

        state = initial_state("Investigate Rahul Sharma", "P001")
        state["iteration"] = 2  # Well under MAX_ITERATIONS = 10
        state["evidence_items"] = []
        state["hypotheses"] = []

        result = critic_verifier_node(state)
        latest_audit = result["verification_results"][-1]

        assert latest_audit["is_sufficient"] is False
        assert latest_audit["routing_decision"] == "supervisor_plan"
        assert "Collect corroborating evidence" in result["investigation_plan"][-1]
        assert route_critic_decision(result) == "supervisor_plan"

    def test_forces_report_when_iteration_budget_exhausted(self):
        from backend.app.agents.nodes.critic_verifier import critic_verifier_node, route_critic_decision

        state = initial_state("Investigate Rahul Sharma", "P001")
        state["iteration"] = 4  # Current + 1 reaches 5 (MAX_ITERATIONS)
        state["evidence_items"] = []
        state["hypotheses"] = []

        result = critic_verifier_node(state)
        latest_audit = result["verification_results"][-1]

        # Forced to report despite insufficient evidence because budget is exhausted
        assert result["iteration"] == 5
        assert latest_audit["routing_decision"] == "supervisor_report"
        assert "EXHAUSTED" in latest_audit["critique"]
        assert route_critic_decision(result) == "supervisor_report"

    def test_flags_missing_cryptographic_hashes(self):
        from backend.app.agents.nodes.critic_verifier import audit_cryptographic_provenance

        evidence_items = [
            {"doc_id": "VALID-01", "evidence_hash": "e" * 64, "bsa_65b_admissible": True},
            {"doc_id": "INVALID-02", "evidence_hash": "invalid-short-hash", "bsa_65b_admissible": True},
            {"doc_id": "NO-HASH-03", "bsa_65b_admissible": False},
        ]
        audit = audit_cryptographic_provenance(evidence_items)
        assert audit["provenance_valid"] is False
        assert "INVALID-02" in audit["missing_hash_items"]
        assert "NO-HASH-03" in audit["missing_hash_items"]
        assert "VALID-01" in audit["verified_items"]


class TestFullInvestigationPipeline:
    """End-to-end integration tests for the full 7-agent pipeline and API (Phase 6)."""

    def test_full_7_agent_state_graph_compiles_and_executes(self):
        from backend.app.agents.nodes.supervisor import create_full_investigation_graph

        graph = create_full_investigation_graph(worker_stubs=True)

        state = initial_state(
            user_query="Investigate suspect Rahul Sharma (P001) for money laundering and hawala operations.",
            subject_entity_id="P001",
        )
        state["full_pipeline"] = True

        final_state = graph.invoke(state)

        # 1. State machine completed
        assert final_state["current_step"] == "COMPLETED"
        assert final_state["final_answer"] is not None
        assert "# 🚨 CRIMINAL NETWORK INTELLIGENCE DOSSIER" in final_state["final_answer"]

        # 2. All key agents participated in tool history
        tool_names = [call["tool_name"] for call in final_state["tool_history"]]
        assert "supervisor_plan" in tool_names
        assert "supervisor_evaluate" in tool_names
        assert "analysis_agent" in tool_names
        assert "critic_verifier" in tool_names
        assert "supervisor_report" in tool_names

        # 3. Hypotheses and Critic verification were populated
        assert len(final_state["hypotheses"]) >= 1
        assert len(final_state["verification_results"]) >= 1
        assert final_state["iteration"] <= 15

    def test_post_investigate_api_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app

        client = TestClient(app)
        payload = {
            "query": "Investigate Rahul Sharma (P001) for hawala banking.",
            "subject_id": "P001",
            "mock_mode": True,
        }

        response = client.post("/api/investigate", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["subject_id"] == "P001"
        assert data["status"] == "COMPLETED"
        assert data["iterations"] >= 1
        assert len(data["dossier"]) > 200
        assert "CRIMINAL NETWORK INTELLIGENCE DOSSIER" in data["dossier"]
        assert len(data["hypotheses"]) >= 1
        assert len(data["verification_audit"]) >= 1
