"""
Supervisor Agent (Orchestrator, Planner & Case Dispatcher)
----------------------------------------------------------
The Chief Intelligence Officer of the Nexxus DB multi-agent task force.

Responsibilities:
1. Deconstructs officer query and disambiguates the primary subject entity.
2. Formulates a structured 3-5 step investigative plan and initializes hypotheses.
3. Dynamically evaluates incoming discoveries and routes between specialized workers.
4. Enforces the strict loop guardrail (MAX_ITERATIONS = 5).
5. Compiles grounded criminal intelligence dossiers with BSA §65B hash certificates.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Literal
# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, START, END

from backend.app.agents.state import (
    InvestigationState,
    Hypothesis,
    ToolInvocation,
    initial_state,
)
from backend.app.agents.tools.graph_tools import search_entities_tool, get_entity_tool

# Non-negotiable system guardrail: hard ceiling on investigation cycles
MAX_ITERATIONS: int = 5


# =========================================================================
# 1. Subject Disambiguation & Entity Resolution Helpers
# =========================================================================

def extract_potential_names_or_ids(query: str) -> List[str]:
    """Extracts candidate names, entity IDs, registration numbers or phone numbers from query."""
    candidates: List[str] = []
    
    # 1. Check for standard entity IDs (e.g. P001, PH001, V001, ORG001, FIR-102)
    id_patterns = re.findall(r"\b(P\d{3,4}|PH\d{3,4}|V\d{3,4}|ORG\d{3,4}|FIR-\d{3,4})\b", query, re.IGNORECASE)
    candidates.extend(id_patterns)

    # 2. Check for vehicle numbers (e.g. DL01AB1234, MH-12-CD-5678)
    plate_patterns = re.findall(r"\b[A-Z]{2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,2}[-\s]?\d{4}\b", query, re.IGNORECASE)
    candidates.extend(plate_patterns)

    # 3. Check for capitalized 2-3 word full names (e.g. Rahul Sharma, Vikram Malhotra)
    name_patterns = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", query)
    # Filter out common false-positive capitalized phrases
    stop_phrases = {"Investigate Rahul", "Criminal Network", "Find Key", "Smart India", "Section Sixty", "FIR Number"}
    for name in name_patterns:
        if name not in stop_phrases and name not in candidates:
            candidates.append(name)

    return candidates


def resolve_subject_entity(
    query: str,
    explicit_id: Optional[str] = None
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Resolves the primary subject entity ID and metadata from query or explicit ID.
    
    Returns:
        (subject_entity_id, resolved_metadata_dict)
    """
    # If explicit subject ID is provided, verify it directly
    if explicit_id:
        clean_id = explicit_id.strip()
        lookup = get_entity_tool.invoke({"entity_id": clean_id})
        if lookup.get("found") and lookup.get("result"):
            return clean_id, lookup.get("result")
        return clean_id, {"id": clean_id, "name": f"Subject ({clean_id})"}

    # Search for candidates in query
    candidates = extract_potential_names_or_ids(query)
    for candidate in candidates:
        search_res = search_entities_tool.invoke({"query": candidate, "limit": 5})
        if search_res.get("count", 0) > 0:
            top_match = search_res["results"][0]
            return top_match.get("id"), top_match

    return None, None


# =========================================================================
# 2. Strategic Planning Node: supervisor_plan_node
# =========================================================================

def supervisor_plan_node(state: InvestigationState) -> Dict[str, Any]:
    """Deconstructs the officer's query, extracts subject entity, creates a 3-5 step plan,
    and initializes working hypotheses.
    
    Mutates:
        - subject_entity_id
        - investigation_plan
        - hypotheses
        - current_step
        - iteration
        - tool_history
    """
    user_query = state.get("user_query", "").strip()
    current_iter = state.get("iteration", 0) + 1
    existing_subject_id = state.get("subject_entity_id")

    # 1. Resolve subject entity
    resolved_id, resolved_meta = resolve_subject_entity(user_query, existing_subject_id)
    subject_id = resolved_id or existing_subject_id or "P001"
    target_name = (
        resolved_meta.get("name")
        if resolved_meta and "name" in resolved_meta
        else f"Subject ({subject_id})"
    )

    # 2. Deconstruct query keywords for tailored plan & hypotheses
    q_lower = user_query.lower()
    has_phone_focus = any(w in q_lower for w in ["phone", "burner", "cdr", "imei", "sim"])
    has_fin_focus = any(w in q_lower for w in ["money", "laundering", "mule", "transaction", "hawala", "financial", "crypto"])
    has_vehicle_focus = any(w in q_lower for w in ["vehicle", "car", "plate", "cloned", "bike"])

    # If re-planning cycle triggered by Critic / Verifier, preserve progress and append critique adjustments
    existing_plan = state.get("investigation_plan", [])
    existing_hypotheses = state.get("hypotheses", [])
    if existing_plan and current_iter > 1:
        plan = list(existing_plan)
        hypotheses = list(existing_hypotheses)
        verification_results = state.get("verification_results", [])
        critique = verification_results[-1].get("critique", "") if verification_results else ""
        plan.append(f"Re-plan: Address Quality Gatekeeper feedback - {critique[:60]}...")

        next_worker = "evidence_verifier" if ("evidence" in critique.lower() or "provenance" in critique.lower()) else "graph_investigator"
        new_history = list(state.get("tool_history", []))
        new_history.append({
            "tool_name": "supervisor_plan",
            "arguments": {"replan": True, "critique": critique[:80]},
            "summary_result": f"Re-planned based on Critic feedback. Next dispatch: {next_worker}.",
            "iteration": current_iter,
        })
        return {
            "subject_entity_id": subject_id,
            "investigation_plan": plan,
            "hypotheses": hypotheses,
            "current_step": next_worker,
            "iteration": current_iter,
            "tool_history": new_history,
        }

    # 3. Formulate 3-5 step investigation plan
    plan: List[str] = [
        f"Step 1: Map 2-hop criminal network perimeter around {target_name} ({subject_id}) using Graph Investigator.",
        f"Step 2: Profile behavioral threat and network centrality (PageRank kingpin, Betweenness broker) with Risk Analyst.",
        f"Step 3: Retrieve FIR records, CDR logs, and audit cryptographic SHA-256 custody under BSA §65B with Evidence Verifier.",
    ]

    if has_fin_focus:
        plan.append(f"Step 4: Trace circular fund routing and mule accounts with Financial & Cyber Analyst.")
    elif has_phone_focus or has_vehicle_focus:
        plan.append(f"Step 4: Correlate burner phone bursts and cloned vehicle registration flags.")
    
    plan.append(f"Step {len(plan) + 1}: Synthesize cross-source intelligence dossier with grounded legal proofs.")

    # 4. Formulate testable initial hypotheses
    hypotheses: List[Hypothesis] = [
        {
            "id": "H-001",
            "claim": f"{target_name} ({subject_id}) operates as a central coordinating node or syndicate affiliate in criminal operations.",
            "status": "WEAK",
            "rationale": "Initial query allegation pending structural topological and risk validation.",
            "supported_evidence_id": [],
        }
    ]

    if has_phone_focus:
        hypotheses.append({
            "id": "H-002",
            "claim": f"{target_name} utilizes burner communication devices or rotating SIM cards to coordinate clandestine activities.",
            "status": "WEAK",
            "rationale": "Telecommunication query flags require CDR burst and IMEI association checks.",
            "supported_evidence_id": [],
        })
    elif has_fin_focus:
        hypotheses.append({
            "id": "H-002",
            "claim": f"{target_name} acts as a conduit for circular money laundering or mule account funneling.",
            "status": "WEAK",
            "rationale": "Financial query flags require transaction cycle and shell organization audit.",
            "supported_evidence_id": [],
        })
    else:
        hypotheses.append({
            "id": "H-002",
            "claim": f"{target_name} functions as a bridge or cut-out between distinct criminal subgroups.",
            "status": "WEAK",
            "rationale": "Multi-group connectivity theory to be evaluated against betweenness centrality.",
            "supported_evidence_id": [],
        })

    # 5. Log planning action in tool history
    new_history = list(state.get("tool_history", []))
    new_history.append({
        "tool_name": "supervisor_plan",
        "arguments": {"resolved_subject_id": subject_id, "query_excerpt": user_query[:60]},
        "summary_result": f"Generated {len(plan)}-step plan and {len(hypotheses)} hypotheses. First dispatch: graph_investigator.",
        "iteration": current_iter,
    })

    return {
        "subject_entity_id": subject_id,
        "investigation_plan": plan,
        "hypotheses": hypotheses,
        "current_step": "graph_investigator",
        "iteration": current_iter,
        "tool_history": new_history,
    }


# =========================================================================
# 3. Dynamic Evaluation & Dispatch Node: supervisor_evaluate_node
# =========================================================================

def supervisor_evaluate_node(state: InvestigationState) -> Dict[str, Any]:
    """Reviews accumulated worker discoveries, updates hypothesis confidence,
    enforces loop limits (MAX_ITERATIONS = 5), and decides next worker or report stage.
    
    Mutates:
        - hypotheses
        - current_step
        - iteration
        - tool_history
    """
    current_iter = state.get("iteration", 0) + 1
    discovered_entities = state.get("discovered_entities", [])
    discovered_relationships = state.get("discovered_relationships", [])
    risk_analysis = state.get("risk_analysis", {})
    evidence_items = state.get("evidence_items", [])
    hypotheses = list(state.get("hypotheses", []))

    # Guardrail Check 1: Exceeded maximum iterations
    if current_iter > MAX_ITERATIONS:
        new_history = list(state.get("tool_history", []))
        new_history.append({
            "tool_name": "supervisor_evaluate",
            "arguments": {"iteration": current_iter},
            "summary_result": f"MAX_ITERATIONS ({MAX_ITERATIONS}) reached. Halting loop and routing to report generation.",
            "iteration": current_iter,
        })
        return {
            "current_step": "supervisor_report",
            "hypotheses": hypotheses,
            "iteration": current_iter,
            "tool_history": new_history,
        }

    # 1. Update Hypotheses based on accumulated evidence
    updated_hypotheses: List[Hypothesis] = []
    for hyp in hypotheses:
        hyp_copy = dict(hyp)
        # Check if we have verified evidence items
        if evidence_items and not hyp_copy.get("supported_evidence_id"):
            evidence_ids = [str(item.get("id") or item.get("doc_id") or "EVID-001") for item in evidence_items]
            hyp_copy["supported_evidence_id"] = evidence_ids[:3]

        # Check if risk profile corroborates criminal role
        risk_score = risk_analysis.get("risk_score", 0)
        has_anomalies = bool(risk_analysis.get("anomalies"))
        has_associates = len(discovered_entities) > 1
        if (has_associates or len(evidence_items) > 0) and (risk_score >= 40 or has_anomalies or len(evidence_items) > 0):
            hyp_copy["status"] = "SUPPORTED"
            hyp_copy["rationale"] = (
                f"Corroborated by {len(discovered_entities)} connected network nodes, "
                f"risk score {risk_score}, and {len(evidence_items)} documentary evidence records."
            )
        else:
            hyp_copy["status"] = "WEAK"
            hyp_copy["rationale"] = "Evidence gathered so far is insufficient to confirm hypothesis conclusively."

        updated_hypotheses.append(hyp_copy)  # type: ignore

    # 2. Determine Next Stage based on missing case components
    user_query = state.get("user_query", "").lower()
    plan_text = " ".join(state.get("investigation_plan", [])).lower()
    has_fin_intent = any(w in user_query or w in plan_text for w in ["money", "laundering", "mule", "transaction", "hawala", "financial", "crypto"])
    has_circ_anomalies = any("circular" in str(a).lower() or "loop" in str(a).lower() for a in risk_analysis.get("anomalies", []))
    has_run_fin = any(entry.get("tool_name") == "financial_analyst" for entry in state.get("tool_history", []))

    next_step: str
    if not discovered_entities and not discovered_relationships:
        # Step A: Graph topology exploration still needed
        next_step = "graph_investigator"
    elif not risk_analysis:
        # Step B: Behavioral & mathematical risk analytics needed
        next_step = "risk_analyst"
    elif not evidence_items:
        # Step C: Legal evidence & BSA §65B hash verification needed
        next_step = "evidence_verifier"
    elif (has_fin_intent or has_circ_anomalies) and not has_run_fin:
        # Step D: Financial & Cyber Forensics needed for mule/laundering trails
        next_step = "financial_analyst"
    else:
        # Step E: All primary stages completed -> check if full pipeline (Analysis -> Critic) is active
        has_run_analysis = any(entry.get("tool_name") == "analysis_agent" for entry in state.get("tool_history", []))
        if state.get("full_pipeline", False) and not has_run_analysis:
            next_step = "analysis_agent"
        else:
            next_step = "supervisor_report"

    new_history = list(state.get("tool_history", []))
    new_history.append({
        "tool_name": "supervisor_evaluate",
        "arguments": {
            "entities_found": len(discovered_entities),
            "edges_found": len(discovered_relationships),
            "has_risk": bool(risk_analysis),
            "evidence_count": len(evidence_items),
        },
        "summary_result": f"Evaluation complete. Next assigned stage: {next_step}.",
        "iteration": current_iter,
    })

    return {
        "hypotheses": updated_hypotheses,
        "current_step": next_step,
        "iteration": current_iter,
        "tool_history": new_history,
    }


# =========================================================================
# 4. Final Intelligence Briefing Node: supervisor_report_node
# =========================================================================

def supervisor_report_node(state: InvestigationState) -> Dict[str, Any]:
    """Compiles a grounded, court-admissible criminal intelligence dossier
    with timeline, topology metrics, risk assessment, and BSA §65B hash audit.
    Delegates to report_agent_node.
    """
    from backend.app.agents.nodes.report_agent import report_agent_node
    return report_agent_node(state)


# =========================================================================
# 5. Routing Logic: route_next_step
# =========================================================================

def route_next_step(state: InvestigationState) -> str:
    """LangGraph conditional edge router.
    
    Inspects state["current_step"] and returns the node key to transition to.
    """
    step = state.get("current_step", "supervisor_report").strip()
    
    if step in ("COMPLETED", "COMPLETE", "__end__", END):
        return END

    # Allow routing to recognized worker nodes or supervisor nodes
    recognized_nodes = {
        "graph_investigator",
        "risk_analyst",
        "evidence_verifier",
        "financial_analyst",
        "analysis_agent",
        "critic_verifier",
        "supervisor_plan",
        "supervisor_evaluate",
        "supervisor_report",
    }

    if step in recognized_nodes:
        return step

    # Fallback to supervisor_evaluate if unknown
    return "supervisor_evaluate"


# =========================================================================
# 6. Worker Stub Nodes (For Phase 2 State Machine Execution)
# =========================================================================

def stub_graph_investigator_node(state: InvestigationState) -> Dict[str, Any]:
    """Stub node for Graph Investigator worker during Phase 2.
    Queries 1-2 hop neighbors of subject using get_entity and get_neighbors tools.
    """
    subject_id = state.get("subject_entity_id") or "P001"
    cur_iter = state.get("iteration", 0) or 1
    
    entities: List[Dict[str, Any]] = list(state.get("discovered_entities", []))
    relationships: List[Dict[str, Any]] = list(state.get("discovered_relationships", []))
    
    # Run tools to populate state with real or mock data
    ent_res = get_entity_tool.invoke({"entity_id": subject_id})
    if ent_res.get("found") and ent_res.get("result"):
        node = ent_res["result"]
        if not any(e.get("id") == subject_id for e in entities):
            entities.append(node)
    else:
        if not any(e.get("id") == subject_id for e in entities):
            entities.append({"id": subject_id, "name": f"Suspect {subject_id}", "label": "Person", "risk_score": 65})

    # Add mock associate for testing if none found
    if len(entities) == 1:
        entities.append({"id": "PH001", "number": "+91-9876543210", "label": "Phone"})
        relationships.append({"source": subject_id, "target": "PH001", "type": "USES_PHONE"})

    new_history = list(state.get("tool_history", []))
    new_history.append({
        "tool_name": "graph_investigator",
        "arguments": {"subject_id": subject_id},
        "summary_result": f"Discovered {len(entities)} entities and {len(relationships)} relationships.",
        "iteration": cur_iter,
    })

    return {
        "discovered_entities": entities,
        "discovered_relationships": relationships,
        "iteration": cur_iter,
        "tool_history": new_history,
    }


def stub_risk_analyst_node(state: InvestigationState) -> Dict[str, Any]:
    """Stub node for Risk Analyst worker during Phase 2."""
    subject_id = state.get("subject_entity_id") or "P001"
    cur_iter = state.get("iteration", 0) or 1

    risk_data = {
        "subject_id": subject_id,
        "risk_score": 75,
        "centrality": {
            "degree": 4,
            "pagerank": 0.385,
            "betweenness": 0.620,
        },
        "anomalies": ["High-frequency night call bursts", "Burner device rotation"],
        "community_id": 1,
    }

    new_history = list(state.get("tool_history", []))
    new_history.append({
        "tool_name": "risk_analyst",
        "arguments": {"subject_id": subject_id},
        "summary_result": f"Assigned composite risk score 75/100 and flagged 2 anomalies.",
        "iteration": cur_iter,
    })

    return {
        "risk_analysis": risk_data,
        "iteration": cur_iter,
        "tool_history": new_history,
    }


def stub_evidence_verifier_node(state: InvestigationState) -> Dict[str, Any]:
    """Stub node for Evidence Verifier worker during Phase 2."""
    subject_id = state.get("subject_entity_id") or "P001"
    cur_iter = state.get("iteration", 0) or 1

    evidence_items = [
        {
            "doc_id": "FIR-102/2026",
            "entity_id": subject_id,
            "incident_type": "Telecommunications Fraud",
            "evidence_hash": "e50fd6c89283fbc3d4924823485723948572093845bca1283948572394857239",
            "bsa_65b_admissible": True,
        }
    ]

    new_history = list(state.get("tool_history", []))
    new_history.append({
        "tool_name": "evidence_verifier",
        "arguments": {"subject_id": subject_id},
        "summary_result": "Verified FIR-102/2026 under BSA §65B with valid SHA-256 hash.",
        "iteration": cur_iter,
    })

    return {
        "evidence_items": evidence_items,
        "iteration": cur_iter,
        "tool_history": new_history,
    }


def stub_financial_analyst_node(state: InvestigationState) -> Dict[str, Any]:
    """Stub node for Financial Analyst worker during Phase 2."""
    subject_id = state.get("subject_entity_id") or "P001"
    cur_iter = state.get("iteration", 0) or 1

    new_history = list(state.get("tool_history", []))
    new_history.append({
        "tool_name": "financial_analyst",
        "arguments": {"subject_id": subject_id},
        "summary_result": "No direct cryptocurrency addresses linked; 1 mule bank account flagged.",
        "iteration": cur_iter,
    })

    return {
        "financial_analysis": {
            "flagged_mule_transactions": 1,
            "total_tracked_flow_inr": 49500.0,
            "circular_round_trips": 1,
        },
        "iteration": cur_iter,
        "tool_history": new_history,
    }


# =========================================================================
# 7. Workflow Graph Factory: create_investigation_graph
# =========================================================================

def create_investigation_graph(worker_stubs: bool = False, full_pipeline: bool = False):
    """Builds and compiles the LangGraph investigation StateGraph.
    
    If worker_stubs=False (default), binds production worker agent implementations.
    If worker_stubs=True, binds isolated stubs for fast unit test isolation.
    If full_pipeline=True, wires the complete intelligence cycle:
        supervisor_plan -> workers -> supervisor_evaluate -> analysis_agent -> critic_verifier -> supervisor_report.
    """
    workflow = StateGraph(InvestigationState)

    # 1. Add Supervisor Core Nodes
    workflow.add_node("supervisor_plan", supervisor_plan_node)
    workflow.add_node("supervisor_evaluate", supervisor_evaluate_node)
    workflow.add_node("supervisor_report", supervisor_report_node)

    # 2. Add Worker Nodes
    if worker_stubs:
        workflow.add_node("graph_investigator", stub_graph_investigator_node)
        workflow.add_node("risk_analyst", stub_risk_analyst_node)
        workflow.add_node("evidence_verifier", stub_evidence_verifier_node)
        workflow.add_node("financial_analyst", stub_financial_analyst_node)
    else:
        from backend.app.agents.nodes.graph_investigator import graph_investigator_node
        from backend.app.agents.nodes.risk_analyst import risk_analyst_node
        from backend.app.agents.nodes.evidence_verifier import evidence_verifier_node
        from backend.app.agents.nodes.financial_analyst import financial_analyst_node

        workflow.add_node("graph_investigator", graph_investigator_node)
        workflow.add_node("risk_analyst", risk_analyst_node)
        workflow.add_node("evidence_verifier", evidence_verifier_node)
        workflow.add_node("financial_analyst", financial_analyst_node)

    # 3. Add Analysis & Critic Nodes if full_pipeline is True
    if full_pipeline:
        from backend.app.agents.nodes.analysis_agent import analysis_agent_node
        from backend.app.agents.nodes.critic_verifier import critic_verifier_node, route_critic_decision

        workflow.add_node("analysis_agent", analysis_agent_node)
        workflow.add_node("critic_verifier", critic_verifier_node)

    # 4. Add Edges & Transitions
    workflow.add_edge(START, "supervisor_plan")

    plan_edges = {
        "graph_investigator": "graph_investigator",
        "risk_analyst": "risk_analyst",
        "evidence_verifier": "evidence_verifier",
        "financial_analyst": "financial_analyst",
        "supervisor_evaluate": "supervisor_evaluate",
        "supervisor_report": "supervisor_report",
        END: END,
    }
    if full_pipeline:
        plan_edges["analysis_agent"] = "analysis_agent"
        plan_edges["critic_verifier"] = "critic_verifier"

    workflow.add_conditional_edges("supervisor_plan", route_next_step, plan_edges)

    # All Workers route into Supervisor Evaluate
    workflow.add_edge("graph_investigator", "supervisor_evaluate")
    workflow.add_edge("risk_analyst", "supervisor_evaluate")
    workflow.add_edge("evidence_verifier", "supervisor_evaluate")
    workflow.add_edge("financial_analyst", "supervisor_evaluate")

    eval_edges = {
        "graph_investigator": "graph_investigator",
        "risk_analyst": "risk_analyst",
        "evidence_verifier": "evidence_verifier",
        "financial_analyst": "financial_analyst",
        "supervisor_report": "supervisor_report",
        END: END,
    }
    if full_pipeline:
        eval_edges["analysis_agent"] = "analysis_agent"
        eval_edges["critic_verifier"] = "critic_verifier"

    workflow.add_conditional_edges("supervisor_evaluate", route_next_step, eval_edges)

    if full_pipeline:
        # analysis_agent routes directly to critic_verifier
        workflow.add_edge("analysis_agent", "critic_verifier")

        # critic_verifier conditionally routes to supervisor_plan (re-plan loop) or supervisor_report
        workflow.add_conditional_edges(
            "critic_verifier",
            route_critic_decision,
            {
                "supervisor_plan": "supervisor_plan",
                "supervisor_report": "supervisor_report",
            }
        )

    # Supervisor Report -> END
    workflow.add_edge("supervisor_report", END)

    return workflow.compile()


def create_full_investigation_graph(worker_stubs: bool = False):
    """Builds and compiles the complete end-to-end multi-agent investigation StateGraph.
    
    Includes all 7 agent nodes with the Critic/Verifier feedback loop.
    """
    return create_investigation_graph(worker_stubs=worker_stubs, full_pipeline=True)
