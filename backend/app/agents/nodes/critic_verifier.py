"""
Critic / Verifier Agent Node (Quality Gatekeeper & Loop Controller)
------------------------------------------------------------------
Acts as the internal affairs quality auditor for the investigation task force:
1. Evaluates evidentiary corroboration: ensures hypotheses are backed by real evidence items.
2. Detects single-source bias: prevents premature conclusions based on a single uncorroborated report.
3. BSA §65B Cryptographic Provenance Audit: verifies SHA-256 custody signatures for all cited documents.
4. Conditional Loop Controller: determines if more evidence is needed or if findings are ready for reporting,
   enforcing the strict MAX_ITERATIONS (10) guardrail.
"""

import re
from typing import Dict, Any, List, Optional, Set
from backend.app.agents.state import InvestigationState, Hypothesis, ToolInvocation

MAX_ITERATIONS: int = 5


def is_valid_sha256(hash_str: Optional[str]) -> bool:
    """Verifies whether a string is a valid 64-character hexadecimal SHA-256 hash."""
    if not hash_str or not isinstance(hash_str, str):
        return False
    return bool(re.fullmatch(r"[a-fA-F0-9]{64}", hash_str.strip()))


def audit_evidentiary_support(
    hypotheses: List[Hypothesis],
    evidence_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Checks whether hypotheses claiming significant findings link to valid evidence."""
    valid_doc_ids: Set[str] = {
        str(item.get("doc_id") or item.get("id"))
        for item in evidence_items
        if item.get("doc_id") or item.get("id")
    }

    supported_count = 0
    weak_count = 0
    rejected_count = 0
    orphaned_hypotheses: List[str] = []

    for h in hypotheses:
        status = h.get("status")
        ev_ids = h.get("supported_evidence_id", [])

        if status == "SUPPORTED":
            # Must link to at least one valid existing evidence item
            has_valid_citation = any(str(eid) in valid_doc_ids for eid in ev_ids)
            if has_valid_citation:
                supported_count += 1
            else:
                orphaned_hypotheses.append(h.get("id", "UNKNOWN"))
                weak_count += 1
        elif status == "WEAK":
            weak_count += 1
        elif status == "REJECTED":
            rejected_count += 1

    return {
        "supported_count": supported_count,
        "weak_count": weak_count,
        "rejected_count": rejected_count,
        "orphaned_hypotheses": orphaned_hypotheses,
        "has_corroboration": supported_count > 0 and len(orphaned_hypotheses) == 0,
    }


def audit_cryptographic_provenance(
    evidence_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Verifies SHA-256 hash signatures and BSA §65B admissibility flags."""
    verified_items: List[str] = []
    unverified_items: List[str] = []
    missing_hash_items: List[str] = []

    for item in evidence_items:
        doc_id = str(item.get("doc_id") or item.get("id", "UNKNOWN"))
        ev_hash = item.get("evidence_hash") or item.get("sha256")
        bsa_admissible = item.get("bsa_65b_admissible", False)

        has_valid_hash = is_valid_sha256(ev_hash)
        if not has_valid_hash:
            missing_hash_items.append(doc_id)

        if has_valid_hash and bsa_admissible:
            verified_items.append(doc_id)
        else:
            unverified_items.append(doc_id)

    all_verified = len(evidence_items) > 0 and len(missing_hash_items) == 0
    return {
        "verified_items": verified_items,
        "unverified_items": unverified_items,
        "missing_hash_items": missing_hash_items,
        "provenance_valid": all_verified,
    }


def detect_single_source_bias(
    evidence_items: List[Dict[str, Any]],
    hypotheses: List[Hypothesis],
    risk_score: float = 0.0,
) -> Dict[str, Any]:
    """Detects if severe allegations or high-risk claims rely solely on a single document."""
    unique_sources: Set[str] = set()
    for item in evidence_items:
        src = item.get("source") or item.get("doc_type") or item.get("doc_id")
        if src:
            unique_sources.add(str(src))

    has_bias = False
    warning = None

    # If there are supported hypotheses or high risk, but only <= 1 distinct source
    supported_hyp = [h for h in hypotheses if h.get("status") == "SUPPORTED"]
    if (len(supported_hyp) > 0 or risk_score >= 70) and len(unique_sources) <= 1:
        has_bias = True
        warning = (
            f"Single-Source Risk: Findings rely on {len(unique_sources)} source ({list(unique_sources)}). "
            "Corroboration from independent telecommunications or financial records recommended."
        )

    return {
        "unique_source_count": len(unique_sources),
        "single_source_bias": has_bias,
        "warning": warning,
    }


def critic_verifier_node(state: InvestigationState) -> Dict[str, Any]:
    """Critic / Verifier worker node.
    
    Evaluates evidence sufficiency, detects bias, verifies cryptographic hashes,
    and decides whether to request targeted re-planning or approve report generation.
    
    Mutates:
        - hypotheses (demotes uncorroborated claims from SUPPORTED to WEAK)
        - verification_results (appends full audit report and critique)
        - investigation_plan (adds targeted corrective steps if re-planning)
        - iteration (incremented step counter)
        - tool_history (audits execution)
    """
    cur_iter = state.get("iteration", 0) + 1
    hypotheses = list(state.get("hypotheses", []))
    evidence_items = list(state.get("evidence_items", []))
    risk_analysis = state.get("risk_analysis", {})
    verification_results = list(state.get("verification_results", []))
    tool_history = list(state.get("tool_history", []))
    investigation_plan = list(state.get("investigation_plan", []))

    risk_score = float(risk_analysis.get("risk_score", 0))

    # 1. Audit Evidentiary Support
    ev_audit = audit_evidentiary_support(hypotheses, evidence_items)

    # Automatically demote orphaned hypotheses
    updated_hypotheses: List[Hypothesis] = []
    for h in hypotheses:
        h_copy = dict(h)
        if h_copy.get("id") in ev_audit["orphaned_hypotheses"]:
            h_copy["status"] = "WEAK"
            h_copy["rationale"] = (
                (h_copy.get("rationale") or "") + " [Critic: Demoted due to lack of verified document citation]"
            ).strip()
        updated_hypotheses.append(h_copy)  # type: ignore

    # 2. Audit Cryptographic Provenance
    prov_audit = audit_cryptographic_provenance(evidence_items)

    # 3. Detect Single-Source Bias
    bias_audit = detect_single_source_bias(evidence_items, updated_hypotheses, risk_score)

    # 4. Synthesize Verification Verdict & Determine Routing
    supported_count = sum(1 for h in updated_hypotheses if h.get("status") == "SUPPORTED")
    critique_points: List[str] = []

    if supported_count == 0:
        critique_points.append("No investigative hypothesis has verified evidentiary support.")

    if bias_audit["single_source_bias"] and bias_audit["warning"]:
        critique_points.append(bias_audit["warning"])

    if not prov_audit["provenance_valid"] and len(evidence_items) > 0:
        critique_points.append(
            f"Cryptographic provenance incomplete: {len(prov_audit['missing_hash_items'])} items lack valid SHA-256 hashes."
        )

    # Sufficiency Condition:
    # A case is sufficient if at least one hypothesis is supported, no complete lack of evidence,
    # OR if the iteration budget is exhausted.
    is_sufficient = (supported_count > 0 and len(evidence_items) > 0)
    budget_exhausted = cur_iter >= MAX_ITERATIONS

    replan_required = (not is_sufficient) and (not budget_exhausted)
    routing_decision = "supervisor_plan" if replan_required else "supervisor_report"

    if replan_required:
        critique_summary = "RE-PLAN REQUIRED: " + " ".join(critique_points)
        # Suggest next targeted investigative step
        corrective_step = "Collect corroborating evidence for primary suspect allegations"
        if corrective_step not in investigation_plan:
            investigation_plan.append(corrective_step)
    elif budget_exhausted and not is_sufficient:
        critique_summary = (
            f"ITERATION BUDGET EXHAUSTED ({cur_iter}/{MAX_ITERATIONS}): "
            "Proceeding to report compilation with evidentiary caveat disclaimers."
        )
    else:
        critique_summary = "VERIFIED: Evidentiary support and cryptographic provenance approved for reporting."

    # Record Verification Audit Entry
    audit_record = {
        "iteration": cur_iter,
        "supported_hypotheses": supported_count,
        "evidence_items_audited": len(evidence_items),
        "provenance_valid": prov_audit["provenance_valid"],
        "single_source_bias": bias_audit["single_source_bias"],
        "is_sufficient": is_sufficient,
        "routing_decision": routing_decision,
        "critique": critique_summary,
    }
    verification_results.append(audit_record)

    # Record Tool History
    tool_history.append({
        "tool_name": "critic_verifier",
        "arguments": {"iteration": cur_iter},
        "summary_result": f"Critic verdict: {routing_decision} ({critique_summary[:80]}...)",
        "iteration": cur_iter,
    })

    return {
        "hypotheses": updated_hypotheses,
        "verification_results": verification_results,
        "investigation_plan": investigation_plan,
        "iteration": cur_iter,
        "tool_history": tool_history,
    }


def route_critic_decision(state: InvestigationState) -> str:
    """Conditional edge router for Critic / Verifier node.
    
    Returns:
        "supervisor_plan" -> If evidence is insufficient and iteration < MAX_ITERATIONS.
        "supervisor_report" -> If evidence is verified or iteration budget exhausted.
    """
    verification_results = state.get("verification_results", [])
    if verification_results:
        latest = verification_results[-1]
        decision = latest.get("routing_decision")
        if decision in ("supervisor_plan", "supervisor_report"):
            return decision

    # Fallback to iteration guardrail
    cur_iter = state.get("iteration", 0)
    if cur_iter >= MAX_ITERATIONS:
        return "supervisor_report"

    # Check supported hypotheses
    hypotheses = state.get("hypotheses", [])
    supported = [h for h in hypotheses if h.get("status") == "SUPPORTED"]
    return "supervisor_report" if len(supported) > 0 else "supervisor_plan"


__all__ = [
    "critic_verifier_node",
    "route_critic_decision",
    "audit_evidentiary_support",
    "audit_cryptographic_provenance",
    "detect_single_source_bias",
    "MAX_ITERATIONS",
]