"""
Unit Tests for Fuzzy Matcher
----------------------------
Tests name similarity scoring, phone matching, and alias resolution.
"""

import pytest
from backend.app.resolution.matcher import (
    calculate_name_similarity,
    calculate_org_similarity,
    is_phone_match,
    is_alias_match,
)


class TestCalculateNameSimilarity:
    def test_exact_matches(self):
        assert calculate_name_similarity("Rahul Sharma", "Rahul Sharma") == 1.0
        assert calculate_name_similarity("Mr. Rahul Sharma", "rahul sharma") == 1.0

    def test_token_inversion(self):
        # Order should not matter in token sort ratio
        assert calculate_name_similarity("Sharma Rahul", "Rahul Sharma") == 1.0

    def test_typos_and_spelling_variations(self):
        score = calculate_name_similarity("Rahool Sharma", "Rahul Sharma")
        assert 0.80 <= score < 1.0

    def test_dissimilar_names(self):
        # Dissimilar names should score well below review threshold (< 0.60)
        score = calculate_name_similarity("Rahul Sharma", "Vikram Malhotra")
        assert score < 0.60

        low_overlap = calculate_name_similarity("Alice Smith", "Bob Jones")
        assert low_overlap <= 0.20

    def test_empty_and_none_inputs(self):
        assert calculate_name_similarity("", "Rahul Sharma") == 0.0
        assert calculate_name_similarity(None, "Rahul Sharma") == 0.0
        assert calculate_name_similarity("Rahul Sharma", "") == 0.0
        assert calculate_name_similarity("Rahul Sharma", None) == 0.0
        assert calculate_name_similarity(None, None) == 0.0
        assert calculate_name_similarity("", "") == 0.0


class TestIsPhoneMatch:
    def test_matching_phones_different_formats(self):
        assert is_phone_match("+91 98765-43210", "9876543210") is True
        assert is_phone_match("09876543210", "+919876543210") is True
        assert is_phone_match("9876543210", "9876543210") is True

    def test_non_matching_phones(self):
        assert is_phone_match("9876543210", "9876543211") is False
        assert is_phone_match("9876543210", "8876543210") is False

    def test_empty_or_none_phones(self):
        assert is_phone_match("", "9876543210") is False
        assert is_phone_match("9876543210", "") is False
        assert is_phone_match(None, "9876543210") is False
        assert is_phone_match("9876543210", None) is False
        assert is_phone_match("", "") is False
        assert is_phone_match(None, None) is False


class TestIsAliasMatch:
    def test_matching_alias_exact_and_fuzzy(self):
        aliases = ["Chhota Don", "Bhai", "Munna"]
        assert is_alias_match(aliases, "chhota don") is True
        assert is_alias_match(aliases, "Don Chhota") is True
        assert is_alias_match(aliases, "Munna") is True

    def test_non_matching_alias(self):
        aliases = ["Bhai", "Munna"]
        assert is_alias_match(aliases, "Rahul Sharma") is False

    def test_empty_alias_list_or_target(self):
        assert is_alias_match([], "Chhota Don") is False
        assert is_alias_match(None, "Chhota Don") is False
        assert is_alias_match(["Bhai"], "") is False
        assert is_alias_match(["Bhai"], None) is False

    def test_threshold_parameter(self):
        aliases = ["Rahool Sharma"]
        # With high threshold (e.g. 0.99), slight typo won't match
        assert is_alias_match(aliases, "Rahul Sharma", threshold=0.99) is False
        # With standard threshold (0.85), slight typo matches
        assert is_alias_match(aliases, "Rahul Sharma", threshold=0.85) is True


class TestCalculateOrgSimilarity:
    def test_suffix_stripping_equivalence(self):
        # Suffix differences should be normalized away
        score = calculate_org_similarity(
            "Shubh Laxmi Finance Pvt Ltd",
            "Shubh Laxmi Finance Private Limited",
        )
        assert score == 1.0

    def test_token_inversion(self):
        score = calculate_org_similarity(
            "Finance Shubh Laxmi",
            "Shubh Laxmi Finance",
        )
        assert score == 1.0

    def test_shell_firm_minor_variation(self):
        score = calculate_org_similarity(
            "Shubh Laxmi Finance",
            "Subh Laxmi Financial Services",
        )
        assert score >= 0.75

    def test_completely_different_orgs(self):
        score = calculate_org_similarity(
            "Shubh Laxmi Finance",
            "Apex Global Shipping",
        )
        # Completely different orgs should score well below review threshold (< 0.75)
        assert score < 0.50

