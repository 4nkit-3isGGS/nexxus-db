"""
Audit Logging Models (Section 65B BSA & IT Act Tamper-Evident Ledger)
---------------------------------------------------------------------
Pydantic schemas for the cryptographic hash-chained audit log records.
"""

from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    """Audited operational actions in the criminal network intelligence system."""
    SEARCH_ENTITY = "SEARCH_ENTITY"
    GET_ENTITY = "GET_ENTITY"
    VIEW_NEIGHBORS = "VIEW_NEIGHBORS"
    INGEST_FIR = "INGEST_FIR"
    INGEST_CDR = "INGEST_CDR"
    MERGE_ENTITIES = "MERGE_ENTITIES"
    FLAG_REVIEW = "FLAG_REVIEW"
    RUN_INVESTIGATION = "RUN_INVESTIGATION"
    UNMASK_PII = "UNMASK_PII"
    VERIFY_AUDIT = "VERIFY_AUDIT"


class AuditLogEntry(BaseModel):
    """An immutable, cryptographically chained audit log entry."""
    log_id: str = Field(..., description="Sequential unique identifier (e.g. 'LOG-00001')")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    user_id: str = Field(..., description="Identifier of the accessing officer")
    badge_number: str = Field(..., description="Officer badge / credentials")
    role: str = Field(..., description="Officer role at access time")
    action: str = Field(..., description="Audited operational action")
    resource_type: str = Field(..., description="Target resource (e.g. 'Person', 'CaseFIR')")
    resource_id: str = Field(..., description="Resource identifier (e.g. 'P001')")
    client_ip: str = Field("127.0.0.1", description="Client IP address")
    status: str = Field("SUCCESS", description="Outcome: SUCCESS, FAILED, FORBIDDEN")
    details: Dict[str, Any] = Field(default_factory=dict, description="Structured contextual metadata")
    prev_hash: str = Field(..., description="SHA-256 hash of the preceding entry in the ledger")
    entry_hash: str = Field(..., description="SHA-256 hash of this entry (H_n = SHA256(H_{n-1} + payload))")
