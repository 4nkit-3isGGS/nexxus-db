"""
Unit Tests for Resolution Decision Engine
------------------------------------------
Tests candidate evaluation, decision thresholds, and multi-candidate resolution.
"""

import pytest
from backend.app.resolution.resolver import (
    ResolutionDecision,
    ResolutionResult,
    evaluate_candidate,
    evaluate_org_candidate,
    resolve_entity,
    resolve_organization,
)


class TestEvaluateCandidate:
    def test_auto_merge_on_matching_phone(self):
        result = evaluate_candidate(
            incoming_name="Rahul Sharma",
            incoming_phone="+91 98765-43210",
            incoming_aliases=[],
            candidate_id="person-001",
            candidate_name="R. Sharma",
            candidate_phones=["9876543210"],
            candidate_aliases=[],
        )
        assert result.decision == ResolutionDecision.AUTO_MERGE
        assert result.matched_entity_id == "person-001"
        assert result.confidence_score >= 0.95
        assert any("Phone match" in r for r in result.match_reasons)

    def test_auto_merge_on_high_name_and_alias_match(self):
        result = evaluate_candidate(
            incoming_name="Rahul Sharma",
            incoming_phone=None,
            incoming_aliases=["Chhota Don"],
            candidate_id="person-002",
            candidate_name="Sharma Rahul",
            candidate_phones=[],
            candidate_aliases=["Chhota Don"],
        )
        assert result.decision == ResolutionDecision.AUTO_MERGE
        assert result.matched_entity_id == "person-002"
        assert result.confidence_score >= 0.90
        assert any("Alias match" in r for r in result.match_reasons)

    def test_flag_for_review_high_name_similarity_only(self):
        result = evaluate_candidate(
            incoming_name="Rahul Sharma",
            incoming_phone=None,
            incoming_aliases=[],
            candidate_id="person-003",
            candidate_name="Rahool Sharma",
            candidate_phones=[],
            candidate_aliases=[],
        )
        assert result.decision == ResolutionDecision.FLAG_FOR_REVIEW
        assert result.matched_entity_id == "person-003"
        assert 0.60 <= result.confidence_score < 0.95

    def test_flag_for_review_moderate_similarity(self):
        result = evaluate_candidate(
            incoming_name="Rahul Kumar Sharma",
            incoming_phone=None,
            incoming_aliases=[],
            candidate_id="person-004",
            candidate_name="Rahul Sharma",
            candidate_phones=[],
            candidate_aliases=[],
        )
        assert result.decision == ResolutionDecision.FLAG_FOR_REVIEW
        assert result.matched_entity_id == "person-004"
        assert 0.60 <= result.confidence_score < 0.85

    def test_create_new_distinct_person(self):
        result = evaluate_candidate(
            incoming_name="Alice Smith",
            incoming_phone="9123456780",
            incoming_aliases=["Queen"],
            candidate_id="person-005",
            candidate_name="Bob Jones",
            candidate_phones=["9876543210"],
            candidate_aliases=["King"],
        )
        assert result.decision == ResolutionDecision.CREATE_NEW
        assert result.matched_entity_id is None
        assert result.confidence_score < 0.60


class TestResolveEntity:
    def test_resolve_with_no_candidates(self):
        incoming = {"name": "Rahul Sharma", "phone": "9876543210", "aliases": []}
        result = resolve_entity(incoming, [])
        assert result.decision == ResolutionDecision.CREATE_NEW
        assert result.matched_entity_id is None

    def test_resolve_selects_best_candidate(self):
        incoming = {
            "name": "Rahul Sharma",
            "phone": "9876543210",
            "aliases": ["Don"],
        }
        candidates = [
            {
                "id": "p-1",
                "name": "Vikram Malhotra",
                "phones": ["9111111111"],
                "aliases": [],
            },
            {
                "id": "p-2",
                "name": "Sharma Rahul",
                "phones": ["9876543210"],
                "aliases": ["Don"],
            },
        ]
        result = resolve_entity(incoming, candidates)
        assert result.decision == ResolutionDecision.AUTO_MERGE
        assert result.matched_entity_id == "p-2"


class TestResolveOrganization:
    def test_auto_merge_on_matching_tax_id(self):
        result = evaluate_org_candidate(
            incoming_name="SLF Finance",
            incoming_aliases=[],
            incoming_tax_id="07AAAAA0000A1Z5",
            candidate_id="org-001",
            candidate_name="Shubh Laxmi Financial Services",
            candidate_aliases=[],
            candidate_tax_id="07AAAAA0000A1Z5",
        )
        assert result.decision == ResolutionDecision.AUTO_MERGE
        assert result.matched_entity_id == "org-001"
        assert result.confidence_score == 1.0

    def test_auto_merge_on_suffix_equivalence(self):
        result = evaluate_org_candidate(
            incoming_name="Shubh Laxmi Finance Pvt Ltd",
            incoming_aliases=[],
            incoming_tax_id=None,
            candidate_id="org-002",
            candidate_name="Shubh Laxmi Finance Private Limited",
            candidate_aliases=[],
            candidate_tax_id=None,
        )
        assert result.decision == ResolutionDecision.AUTO_MERGE
        assert result.matched_entity_id == "org-002"
        assert result.confidence_score >= 0.92

    def test_flag_for_review_on_fuzzy_variant(self):
        result = evaluate_org_candidate(
            incoming_name="Shubh Laxmi Finance",
            incoming_aliases=[],
            incoming_tax_id=None,
            candidate_id="org-003",
            candidate_name="Subh Laxmi Financial Services",
            candidate_aliases=[],
            candidate_tax_id=None,
        )
        assert result.decision == ResolutionDecision.FLAG_FOR_REVIEW
        assert result.matched_entity_id == "org-003"
        assert 0.75 <= result.confidence_score < 0.92

    def test_create_new_distinct_org(self):
        result = evaluate_org_candidate(
            incoming_name="Apex Logistics Inc",
            incoming_aliases=[],
            incoming_tax_id=None,
            candidate_id="org-004",
            candidate_name="Shubh Laxmi Finance",
            candidate_aliases=[],
            candidate_tax_id=None,
        )
        assert result.decision == ResolutionDecision.CREATE_NEW
        assert result.matched_entity_id is None

    def test_resolve_organization_best_match(self):
        incoming = {
            "name": "Shubh Laxmi Finance Pvt Ltd",
            "aliases": ["SLF"],
        }
        candidates = [
            {"id": "org-1", "name": "Apex Global Traders", "aliases": []},
            {"id": "org-2", "name": "Shubh Laxmi Finance", "aliases": ["SLF"]},
        ]
        result = resolve_organization(incoming, candidates)
        assert result.decision == ResolutionDecision.AUTO_MERGE
        assert result.matched_entity_id == "org-2"

