"""
Role-Based Access Control (RBAC) & PII Redaction Layer
------------------------------------------------------
Enforces law-enforcement authorization policies and dynamic PII masking
for compliance with data protection laws and the Bharatiya Sakshya Adhiniyam.
"""

from typing import List, Optional, Dict, Any, Callable
from fastapi import Header, HTTPException, Depends, status

from backend.app.auth.models import Role, Permission, UserSession


# =========================================================================
# 1. PII Redaction & Masking Utilities
# =========================================================================

def mask_aadhaar(aadhaar: Optional[str]) -> str:
    """Masks Aadhaar number preserving only the last 4 digits (e.g. 'XXXX-XXXX-1234')."""
    if not aadhaar or not isinstance(aadhaar, str):
        return "XXXX-XXXX-XXXX"
    digits = "".join(filter(str.isdigit, aadhaar))
    if len(digits) >= 4:
        return f"XXXX-XXXX-{digits[-4:]}"
    return "XXXX-XXXX-XXXX"


def mask_pan(pan: Optional[str]) -> str:
    """Masks PAN card identifier preserving only the last 4 characters (e.g. 'XXXXX1234F')."""
    if not pan or not isinstance(pan, str):
        return "XXXXXXXXXX"
    clean_pan = pan.strip()
    if len(clean_pan) >= 4:
        return f"{'X' * (len(clean_pan) - 4)}{clean_pan[-4:]}"
    return "XXXXXXXXXX"


def mask_phone(phone: Optional[str]) -> str:
    """Masks phone number preserving only the country prefix and last 3 digits."""
    if not phone or not isinstance(phone, str):
        return "+91-XXXXXXXXXX"
    clean_phone = phone.strip()
    if len(clean_phone) > 4:
        return f"+91-XXXXX-XX{clean_phone[-3:]}"
    return "+91-XXXXXXXXXX"


def mask_entity_pii(entity: Dict[str, Any], user: UserSession) -> Dict[str, Any]:
    """Dynamically redacts or unmasks PII based on officer clearance level.
    
    Rules:
    - LEAD_INVESTIGATOR / ADMIN (with UNMASK_PII): Full access to raw Aadhaar, PAN, and phone.
    - INVESTIGATOR: Phone visible for telecomm analysis, Aadhaar & PAN masked to last 4.
    - ANALYST / AUDITOR: All PII masked (Aadhaar, PAN, and phone masked).
    """
    masked = dict(entity)

    # Full clearance
    if user.has_permission(Permission.UNMASK_PII):
        return masked

    # Mid clearance: Field Investigator
    if user.role == Role.INVESTIGATOR:
        if "aadhaar" in masked and masked["aadhaar"]:
            masked["aadhaar"] = mask_aadhaar(masked["aadhaar"])
        if "pan" in masked and masked["pan"]:
            masked["pan"] = mask_pan(masked["pan"])
        return masked

    # Restricted clearance: Crime Analyst, Auditor, etc.
    if "aadhaar" in masked and masked["aadhaar"]:
        masked["aadhaar"] = mask_aadhaar(masked["aadhaar"])
    if "pan" in masked and masked["pan"]:
        masked["pan"] = mask_pan(masked["pan"])
    if "number" in masked and masked["number"]:
        masked["number"] = mask_phone(masked["number"])
    if "phone" in masked and masked["phone"]:
        masked["phone"] = mask_phone(masked["phone"])

    return masked


# =========================================================================
# 2. FastAPI Authorization Dependencies
# =========================================================================

def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_role: Optional[str] = Header(None, alias="X-Role"),
    x_badge: Optional[str] = Header(None, alias="X-Badge-Number"),
    x_jurisdiction: Optional[str] = Header(None, alias="X-Jurisdiction"),
) -> UserSession:
    """Resolves the active law enforcement officer session from request headers.
    
    Defaults to LEAD_INVESTIGATOR if headers are omitted (convenient for local dev).
    """
    user_id = x_user_id or "OFFICER_LEAD_01"
    badge_number = x_badge or "DL-IPS-2026"
    jurisdiction = x_jurisdiction or "Central Crime Branch"

    role_str = (x_role or "LEAD_INVESTIGATOR").upper().strip()
    try:
        role = Role(role_str)
    except ValueError:
        role = Role.INVESTIGATOR

    return UserSession(
        user_id=user_id,
        badge_number=badge_number,
        role=role,
        jurisdiction=jurisdiction,
    )


def require_role(allowed_roles: List[Role]) -> Callable:
    """FastAPI dependency factory to enforce specific allowed roles."""
    def role_checker(user: UserSession = Depends(get_current_user)) -> UserSession:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access Denied: Officer role '{user.role.value}' does not have sufficient clearance. "
                    f"Required: {[r.value for r in allowed_roles]}."
                ),
            )
        return user
    return role_checker


def require_permission(permission: Permission) -> Callable:
    """FastAPI dependency factory to enforce specific operational permissions."""
    def permission_checker(user: UserSession = Depends(get_current_user)) -> UserSession:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access Denied: Role '{user.role.value}' lacks required permission '{permission.value}'."
                ),
            )
        return user
    return permission_checker
