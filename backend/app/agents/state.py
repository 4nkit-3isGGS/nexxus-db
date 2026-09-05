"""
Investigation State Definition
-------------------------------
Structured state passed across all nodes in the LangGraph investigation flow.

"""
from typing import TypedDict, Optional, Literal, Any, List, Dict

HypothesisStatus = Literal["SUPPORTED", "WEAK", "REJECTED"]

class Hypothesis(TypedDict):
    """Represents a specific investigative theory being tested."""
    id: str
    claim: str
    status: HypothesisStatus
    rationale: str
    supported_evidence_id: List[str]


class ToolInvocation(TypedDict):
    """Audits records of a tool call made during the investigation."""
    tool_name: str
    arguments: Dict[str, Any]
    summary_result: str
    iteration: int


class InvestigationState(TypedDict):
    """The central case folder passed between agents."""
    user_query: str
    subject_entity_id: Optional[str]
    investigation_plan: List[str]
    current_step: str
    discovered_entities: List[Dict[str, Any]]
    discovered_relationships: List[Dict[str, Any]]
    hypotheses: List[Hypothesis]
    evidence_items: List[Dict[str, Any]]
    risk_analysis: Dict[str, Any]
    verification_results: List[Dict[str, Any]]
    tool_history: List[ToolInvocation]
    iteration: int
    final_answer: Optional[str] 

def initial_state(user_query: str, subject_entity_id: Optional[str] = None) -> InvestigationState:
    """Helper to start an investigation with a clean, empty state. """
    return {
        "user_query": user_query,
        "subject_entity_id": subject_entity_id,
        "investigation_plan": [],
        "current_step": "START",
        "discovered_entities": [],
        "discovered_relationships": [],
        "hypotheses": [],
        "evidence_items": [],
        "risk_analysis": {},
        "verification_results": [],
        "tool_history": [],
        "iteration": 0,
        "final_answer": None,
    }

