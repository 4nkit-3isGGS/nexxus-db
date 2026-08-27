"""
Entity Resolution - Decision Engine Module
-------------------------------------------
Combines name similarity, phone matching, and alias verification to determine
whether incoming suspect entities should be merged, flagged for manual review,
or created as new nodes in the knowledge graph.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.app.resolution.matcher import (
    calculate_name_similarity,
    is_alias_match,
    is_phone_match,
)


class ResolutionDecision(str, Enum):
    AUTO_MERGE = "AUTO_MERGE"          # High confidence duplicate -> Merge into existing entity
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW" # Probable match -> Requires investigator verification
    CREATE_NEW = "CREATE_NEW"          # Distinct entity -> Create new Person node


@dataclass
class ResolutionResult:
    decision: ResolutionDecision
    matched_entity_id: str | None = None
    confidence_score: float = 0.0
    match_reasons: list[str] = field(default_factory=list)


def evaluate_candidate(
    incoming_name: str,
    incoming_phone: str | None,
    incoming_aliases: list[str],
    candidate_id: str,
    candidate_name: str,
    candidate_phones: list[str],
    candidate_aliases: list[str],
) -> ResolutionResult:
    """Evaluates an incoming entity against a single candidate entity in the graph."""
    reasons: list[str] = []

    # 1. Calculate name similarity
    name_score = calculate_name_similarity(incoming_name, candidate_name)
    if name_score > 0:
        reasons.append(f"Name Similarity score: {name_score:.2f}")

    # 2. Check for phone number match
    has_phone_match = (
        any(is_phone_match(incoming_phone, p) for p in candidate_phones)
        if incoming_phone
        else False
    )
    if has_phone_match:
        reasons.append(f"Phone match: {incoming_phone} ")

    # 3. Check for alias match (name vs alias OR shared aliases)
    has_alias_match = (
        is_alias_match(candidate_aliases, incoming_name)
        or is_alias_match(incoming_aliases, candidate_name)
        or any(is_alias_match(candidate_aliases, a) for a in incoming_aliases)
    )
    if has_alias_match:
        reasons.append("Alias match detected")

    # 4. Decision Engine Logic
    # Case A: AUTO_MERGE
    # - Exact phone match (strong physical identifier), OR
    # - High name similarity (>= 0.85) supported by an alias match
    if has_phone_match or (name_score >= 0.85 and has_alias_match):
        confidence = max(name_score, 0.95 if has_phone_match else 0.90)
        return ResolutionResult(
            decision=ResolutionDecision.AUTO_MERGE,
            matched_entity_id=candidate_id,
            confidence_score=round(confidence, 4),
            match_reasons=reasons,
        )

    # Case B: FLAG_FOR_REVIEW
    # - High name similarity without supporting phone/alias (>= 0.85), OR
    # - Moderate name similarity (0.60 <= score < 0.85), OR
    # - Alias match found without phone or high name score
    if name_score >= 0.60 or has_alias_match:
        confidence = max(name_score, 0.70 if has_alias_match else name_score)
        return ResolutionResult(
            decision=ResolutionDecision.FLAG_FOR_REVIEW,
            matched_entity_id=candidate_id,
            confidence_score=round(confidence, 4),
            match_reasons=reasons,
        )

    # Case C: CREATE_NEW
    # - Low name similarity (< 0.60) and no matching phone or alias
    if not reasons:
        reasons.append("Low name similarity score (< 0.60) and no identifier matches")

    return ResolutionResult(
        decision=ResolutionDecision.CREATE_NEW,
        matched_entity_id=None,
        confidence_score=round(name_score, 4),
        match_reasons=reasons,
    )


def resolve_entity(
    incoming_record: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> ResolutionResult:
    """Evaluates an incoming entity against a list of candidate graph entities.

    Selects the candidate with the highest resolution confidence.
    """
    if not candidates:
        return ResolutionResult(
            decision=ResolutionDecision.CREATE_NEW,
            matched_entity_id=None,
            confidence_score=0.0,
            match_reasons=["No candidates in graph to evaluate"],
        )

    incoming_name = incoming_record.get("name", "")
    incoming_phone = incoming_record.get("phone")
    incoming_aliases = incoming_record.get("aliases") or []

    evaluated_results: list[ResolutionResult] = []

    for cand in candidates:
        res = evaluate_candidate(
            incoming_name=incoming_name,
            incoming_phone=incoming_phone,
            incoming_aliases=incoming_aliases,
            candidate_id=str(cand.get("id", "")),
            candidate_name=cand.get("name", ""),
            candidate_phones=cand.get("phones") or ([cand["phone"]] if "phone" in cand and cand["phone"] else []),
            candidate_aliases=cand.get("aliases") or [],
        )
        evaluated_results.append(res)

    # Sort results by confidence score descending
    best_result = max(evaluated_results, key=lambda r: r.confidence_score)

    return best_result
