"""
Law Enforcement Authentication & RBAC Models
--------------------------------------------
Defines tiered law-enforcement roles, permissions, and session context
for NexxusDB (SIH26189).
"""

from enum import Enum
from typing import Set, Optional
from pydantic import BaseModel, Field


class Role(str, Enum):
    """Tiered law enforcement access roles based on the 'Need-to-Know' principle."""
    ADMIN = "ADMIN"                     # IT administration, system provisioning, audit access
    LEAD_INVESTIGATOR = "LEAD_INVESTIGATOR" # DSP / ACP rank: approval of merges, unmasked PII, agent investigation
    INVESTIGATOR = "INVESTIGATOR"       # Inspector / SI: field investigations, graph search, agent queries
    ANALYST = "ANALYST"                 # Intelligence analyst: topology, risk metrics, masked PII
    AUDITOR = "AUDITOR"                 # Vigilance / judicial auditor: read-only immutable audit trail


class Permission(str, Enum):
    """Specific operational permissions."""
    VIEW_GRAPH = "VIEW_GRAPH"
    SEARCH_ENTITY = "SEARCH_ENTITY"
    INVESTIGATE = "INVESTIGATE"
    MERGE_ENTITIES = "MERGE_ENTITIES"
    UNMASK_PII = "UNMASK_PII"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"
    VERIFY_AUDIT_INTEGRITY = "VERIFY_AUDIT_INTEGRITY"
    MANAGE_USERS = "MANAGE_USERS"


# Role-to-Permissions Matrix
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        Permission.VIEW_GRAPH,
        Permission.SEARCH_ENTITY,
        Permission.VIEW_AUDIT_LOGS,
        Permission.VERIFY_AUDIT_INTEGRITY,
        Permission.MANAGE_USERS,
    },
    Role.LEAD_INVESTIGATOR: {
        Permission.VIEW_GRAPH,
        Permission.SEARCH_ENTITY,
        Permission.INVESTIGATE,
        Permission.MERGE_ENTITIES,
        Permission.UNMASK_PII,
        Permission.VIEW_AUDIT_LOGS,
    },
    Role.INVESTIGATOR: {
        Permission.VIEW_GRAPH,
        Permission.SEARCH_ENTITY,
        Permission.INVESTIGATE,
    },
    Role.ANALYST: {
        Permission.VIEW_GRAPH,
        Permission.SEARCH_ENTITY,
    },
    Role.AUDITOR: {
        Permission.VIEW_AUDIT_LOGS,
        Permission.VERIFY_AUDIT_INTEGRITY,
    },
}


class UserSession(BaseModel):
    """Active law enforcement officer session context."""
    user_id: str = Field(..., description="Unique officer ID, e.g. 'OFFICER_4401'")
    badge_number: str = Field(..., description="Official police badge number, e.g. 'DL-IPS-8821'")
    role: Role = Field(..., description="Assigned role")
    jurisdiction: str = Field("Delhi State", description="Police jurisdiction / department")

    def has_permission(self, permission: Permission) -> bool:
        """Checks if current user's role has the requested permission."""
        return permission in ROLE_PERMISSIONS.get(self.role, set())
