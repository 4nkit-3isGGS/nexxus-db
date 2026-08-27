"""
Entity Resolution - Fuzzy Matcher Module (Work In Progress)
-----------------------------------------------------------
Implements name similarity scoring via RapidFuzz, phone matching,
and alias verification for criminal entity deduplication.
"""

from backend.app.resolution.normalizer import normalize_name, normalize_phone
from rapidfuzz import fuzz

def calculate_name_similarity(name1: str | None, name2: str | None) -> float:
    """Calculates fuzzy similarity between two names (returns float 0.0 to 1.0)."""
    norm1, norm2 = normalize_name(name1), normalize_name(name2)

    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0

    # Token sort ratio handles word reordering (e.g. 'sharma rahul' vs 'rahul sharma')
    fuzz_score = fuzz.token_sort_ratio(norm1, norm2)
    return round(fuzz_score / 100.0, 4)


def is_phone_match(phone1: str | None, phone2: str | None) -> bool:
    """Returns True only if both phone numbers are valid/non-empty and match exactly."""
    norm_ph1 = normalize_phone(phone1)
    norm_ph2 = normalize_phone(phone2)

    if not norm_ph1 or not norm_ph2:
        return False

    return norm_ph1 == norm_ph2


def is_alias_match(aliases: list[str] | None, target_name: str | None, threshold: float = 0.85) -> bool:
    """Returns True if any alias in the list matches target_name above the threshold."""
    if not aliases or not target_name:
        return False

    for alias in aliases:
        score = calculate_name_similarity(alias, target_name)
        if score >= threshold:
            return True

    return False

