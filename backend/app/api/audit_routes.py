"""
Audit API Routes
----------------
Endpoints for inspecting the tamper-evident audit ledger and cryptographically
verifying chain integrity under Section 65B Bharatiya Sakshya Adhiniyam standards.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.app.audit.audit_logger import audit_ledger
from backend.app.audit.models import AuditLogEntry
from backend.app.auth.models import Role, Permission, UserSession
from backend.app.auth.rbac import require_role, require_permission

router = APIRouter(prefix="/api/audit", tags=["Audit & Governance"])


class AuditLogsResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    latest_hash: str
    entries: List[AuditLogEntry]


class IntegrityVerifyResponse(BaseModel):
    verified: bool
    record_count: int
    latest_hash: str
    message: str
    tampered_index: Optional[int] = None
    log_id: Optional[str] = None
    reason: Optional[str] = None


@router.get("/logs", response_model=AuditLogsResponse)
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    current_user: UserSession = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
):
    """Retrieves paginated audit events from the immutable ledger.
    
    Access Restricted: AUDITOR, ADMIN, LEAD_INVESTIGATOR.
    """
    entries, total = audit_ledger.get_entries(
        limit=limit,
        offset=offset,
        user_id=user_id,
        action=action,
    )
    return AuditLogsResponse(
        total_count=total,
        limit=limit,
        offset=offset,
        latest_hash=audit_ledger._latest_hash,
        entries=entries,
    )


@router.post("/verify", response_model=IntegrityVerifyResponse)
def verify_audit_chain_integrity(
    current_user: UserSession = Depends(require_permission(Permission.VERIFY_AUDIT_INTEGRITY)),
):
    """Cryptographically verifies the SHA-256 hash-chain across all recorded audit entries.
    
    Returns certification of non-tampering under Section 65B Bharatiya Sakshya Adhiniyam.
    Access Restricted: AUDITOR, ADMIN.
    """
    result = audit_ledger.verify_chain_integrity()
    return IntegrityVerifyResponse(**result)
