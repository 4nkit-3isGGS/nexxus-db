"""
Investigation API Routes (LangGraph Multi-Agent Investigation Layer)
--------------------------------------------------------------------
Exposes the autonomous multi-agent criminal network intelligence engine
for Bishal & Jayanta's frontend UI and automated investigation workflows.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from backend.app.agents.state import initial_state
from backend.app.agents.nodes.supervisor import create_full_investigation_graph
from backend.app.auth.models import Permission, UserSession
from backend.app.auth.rbac import require_permission, mask_entity_pii
from backend.app.audit.audit_logger import audit_ledger
from backend.app.audit.models import AuditAction

router = APIRouter(prefix="/api", tags=["Investigation"])


class InvestigateRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Investigative query or hypothesis (e.g. 'Investigate Rahul Sharma')")
    subject_id: Optional[str] = Field(None, description="Explicit primary suspect entity ID (e.g. 'P001')")
    mock_mode: bool = Field(False, description="Whether to use mock worker stubs (for offline testing or rapid UI demos)")


class InvestigateResponse(BaseModel):
    subject_id: Optional[str]
    query: str
    status: str
    iterations: int
    dossier: str
    hypotheses: List[Dict[str, Any]]
    discovered_entities: List[Dict[str, Any]]
    discovered_relationships: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    verification_audit: List[Dict[str, Any]]
    tool_history: List[Dict[str, Any]]


@router.post("/investigate", response_model=InvestigateResponse)
def run_investigation(
    request: InvestigateRequest,
    current_user: UserSession = Depends(require_permission(Permission.INVESTIGATE)),
):
    """Executes an autonomous multi-agent criminal network investigation.
    
    Orchestrates the 7-agent pipeline:
    Supervisor -> Graph Investigator -> Risk Analyst -> Evidence Verifier ->
    Financial & Cyber Analyst -> Analysis Agent -> Critic / Verifier -> Report Agent.
    
    Access Restricted: INVESTIGATOR, LEAD_INVESTIGATOR.
    Every query is audited in the tamper-evident cryptographic hash ledger.
    """
    try:
        # Initialize state with full pipeline flag
        state = initial_state(
            user_query=request.query,
            subject_entity_id=request.subject_id,
            full_pipeline=True,
        )

        # Build and invoke compiled StateGraph
        graph = create_full_investigation_graph(worker_stubs=request.mock_mode)
        final_state = graph.invoke(state)

        # Apply RBAC PII redaction according to officer clearance level
        masked_entities = [
            mask_entity_pii(entity, current_user)
            for entity in final_state.get("discovered_entities", [])
        ]

        # Record tamper-evident audit event
        audit_ledger.log_event(
            user_id=current_user.user_id,
            badge_number=current_user.badge_number,
            role=current_user.role.value,
            action=AuditAction.RUN_INVESTIGATION.value,
            resource_type="CriminalInvestigation",
            resource_id=final_state.get("subject_entity_id") or "UNSPECIFIED",
            details={
                "query": request.query,
                "iterations": final_state.get("iteration", 0),
                "entities_mapped": len(masked_entities),
            },
        )

        return InvestigateResponse(
            subject_id=final_state.get("subject_entity_id"),
            query=final_state.get("user_query", request.query),
            status=final_state.get("current_step", "COMPLETED"),
            iterations=final_state.get("iteration", 0),
            dossier=final_state.get("final_answer") or "No dossier generated.",
            hypotheses=final_state.get("hypotheses", []),
            discovered_entities=masked_entities,
            discovered_relationships=final_state.get("discovered_relationships", []),
            evidence_items=final_state.get("evidence_items", []),
            verification_audit=final_state.get("verification_results", []),
            tool_history=final_state.get("tool_history", []),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Investigation engine error: {str(exc)}")
