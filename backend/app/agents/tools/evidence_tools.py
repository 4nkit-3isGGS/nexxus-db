"""
LangGraph Agent Tools: Evidence Verification & BSA §65B Chain of Custody
-------------------------------------------------------------------------
Provides verifiable provenance retrieval and cryptographic SHA-256 hash checks
compliant with Section 65B of the Bharatiya Sakshya Adhiniyam (BSA), 2023.

These tools allow investigative agents to:
1. Fetch source documents, FIR citations, and confidence scores backing any link.
2. Cryptographically verify raw text against recorded SHA-256 hashes to detect tampering.
3. Generate tamper-evident fingerprints for new investigative hypotheses and notes.
"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from backend.app.services.graph_service import get_evidence

class GetEvidenceInput(BaseModel):
    """Input schema for fetching evidentiary proof between two entities."""
    entity_id1: str = Field(
        ...,
        description="First entity ID in the relationship (e.g., suspect, phone, or vehicle).",
        min_length=1,
    )
    entity_id2: str = Field(
        ...,
        description="Second entity ID in the relationship (e.g., co-suspect, location, or account).",
        min_length=1,
    )


@tool("get_evidence", args_schema=GetEvidenceInput)
def get_relationship_evidence_tool(entity_id1: str, entity_id2: str) -> Dict[str, Any]:
    """Retrieves source documents, FIR numbers, excerpts, and confidence ratings for a connection.

    Use this tool when you need to justify an investigative finding to a magistrate or court
    under BSA §65B. Returns the exact document ID (e.g., FIR-102/2026, CDR-AIRTEL-4412),
    timestamp, extraction confidence, and raw properties backing the edge.

    Args:
        entity_id1: First connected entity ID.
        entity_id2: Second connected entity ID.

    Returns:
        Dictionary with list of evidence records, document IDs, and confidence levels.
    """
    e1 = entity_id1.strip()
    e2 = entity_id2.strip()

    if not e1 or not e2:
        return {
            "evidence_found": False,
            "count": 0,
            "error": "Both entity_id1 and entity_id2 must be non-empty.",
        }

    if e1 == e2:
        return {
            "evidence_found": False,
            "count": 0,
            "message": "Entity IDs are identical; no relational evidence exists for self-loop.",
        }

    records = get_evidence(e1, e2)

    if not records:
        return {
            "entity_id1": e1,
            "entity_id2": e2,
            "evidence_found": False,
            "count": 0,
            "message": f"No evidentiary relationships found linking '{e1}' and '{e2}'.",
        }

    formatted_evidence: List[Dict[str, Any]] = []
    for r in records:
        full_props = r.get("full_properties", {})
        formatted_evidence.append({
            "relationship_type": r.get("relationship"),
            "source_doc_id": r.get("source_doc") or full_props.get("source_doc_id", "UNKNOWN_DOC"),
            "confidence": r.get("confidence", 1.0),
            "timestamp": r.get("timestamp") or full_props.get("timestamp"),
            "evidence_hash": full_props.get("evidence_hash"),
            "source_excerpt": full_props.get("source_span") or full_props.get("excerpt"),
            "details": {k: v for k, v in full_props.items() if k not in ("evidence_hash", "source_span", "excerpt")}
        })

    return {
        "entity_id1": e1,
        "entity_id2": e2,
        "evidence_found": True,
        "count": len(formatted_evidence),
        "evidence": formatted_evidence,
    }


# --------------------------------------------------------------------------
# Tool: Cryptographic Integrity Verification (BSA §65B Audit)


class VerifyIntegrityInput(BaseModel):
    """Input schema for verifying cryptographic integrity of source evidence."""
    raw_content: str = Field(
        ...,
        description="Raw document text, transcript excerpt, or log row to verify.",
        min_length=1,
    )
    expected_hash: str = Field(
        ...,
        description="The recorded SHA-256 hash to test against (from graph edge or ledger).",
        min_length=16,
    )


@tool("verify_evidence_integrity", args_schema=VerifyIntegrityInput)
def verify_evidence_integrity_tool(raw_content: str, expected_hash: str) -> Dict[str, Any]:
    """Cryptographically verifies that raw evidence content matches its recorded SHA-256 hash.

    Use this tool to prove chain-of-custody integrity in compliance with Section 65B
    of the Bharatiya Sakshya Adhiniyam (BSA), 2023. If the computed hash matches the
    expected hash, the evidence is certified tamper-free and legally admissible.

    Args:
        raw_content: The exact string excerpt or serialized data.
        expected_hash: The SHA-256 hash stored at time of ingestion.

    Returns:
        Audit report containing verification status, computed hash, and BSA admissibility.
    """
    clean_content = raw_content.strip()
    clean_expected = expected_hash.strip().lower()

    if not clean_content:
        return {
            "is_valid": False,
            "integrity_status": "EMPTY_CONTENT",
            "error": "Raw content cannot be empty for hash verification."
        }

    computed_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()
    is_valid = (computed_hash == clean_expected)

    return {
        "is_valid": is_valid,
        "integrity_status": "VERIFIED_AUTHENTIC" if is_valid else "TAMPER_DETECTED",
        "bsa_65b_admissible": is_valid,
        "algorithm": "SHA-256",
        "computed_hash": computed_hash,
        "expected_hash": clean_expected,
        "audit_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "audit_message": (
            "Cryptographic check PASSED: Evidence content is untampered and certified under BSA §65B."
            if is_valid else
            "Cryptographic check FAILED: Computed hash does NOT match recorded hash. Evidence may have been altered!"
        )
    }


# -------------------------------------------------------------------------
#  Tool: Generate Evidence Hash Fingerprint

class GenerateHashInput(BaseModel):
    """Input schema for computing SHA-256 fingerprint for newly extracted evidence."""
    content: str = Field(
        ...,
        description="Content or note to generate a cryptographic SHA-256 fingerprint for.",
        min_length=1,
    )


@tool("generate_evidence_hash", args_schema=GenerateHashInput)
def generate_evidence_hash_tool(content: str) -> Dict[str, Any]:
    """Generates an immutable SHA-256 cryptographic hash for an evidence excerpt or note.

    Use this tool when creating a new investigative note, storing an extracted span,
    or recording a merge decision to establish an unbroken audit trail.

    Args:
        content: The text or JSON string to fingerprint.

    Returns:
        Dictionary with SHA-256 hash, byte length, and generation timestamp.
    """
    clean_content = content.strip()
    if not clean_content:
        return {"error": "Content cannot be empty."}

    content_bytes = clean_content.encode("utf-8")
    sha256_hash = hashlib.sha256(content_bytes).hexdigest()

    return {
        "algorithm": "SHA-256",
        "hash": sha256_hash,
        "length_characters": len(clean_content),
        "length_bytes": len(content_bytes),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }



# Exported Tool Registry

EVIDENCE_TOOLS = [
    get_relationship_evidence_tool,
    verify_evidence_integrity_tool,
    generate_evidence_hash_tool,
]