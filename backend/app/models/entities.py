"""
Pydantic Models — Entities & Payloads
--------------------------------------
Defines validation schemas matching Abhidha's NLP output contract.
All data from the NLP pipeline passes through these models
before touching Neo4j.
"""

from pydantic import BaseModel, Field
from typing import Literal


# ─── Entity Models (polymorphic, discriminated by `type`) ────────────────────


class PersonEntity(BaseModel):
    id: str
    type: Literal["Person"]
    source_doc: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class PhoneEntity(BaseModel):
    id: str
    type: Literal["Phone"]
    source_doc: str
    number: str


class LocationEntity(BaseModel):
    id: str
    type: Literal["Location"]
    source_doc: str
    name: str
    latitude: float | None = None
    longitude: float | None = None


class VehicleEntity(BaseModel):
    id: str
    type: Literal["Vehicle"]
    source_doc: str
    registration_number: str
    vehicle_type: str | None = None


class OrganizationEntity(BaseModel):
    id: str
    type: Literal["Organization"]
    source_doc: str
    name: str


# ─── Relationship Model ─────────────────────────────────────────────────────


class RelationshipPayload(BaseModel):
    """A single relationship extracted by the NLP pipeline.

    source/target are entity IDs (e.g. 'P001', 'PH002', 'ORG001').
    Extra fields (duration, role, amount, etc.) are type-dependent.
    """
    source: str = Field(..., description="Source entity ID")
    target: str = Field(..., description="Target entity ID")
    type: str = Field(..., description="CALLED, MEMBER_OF, OWNS_PHONE, PRESENT_AT, OWNS_VEHICLE, TRANSACTED_WITH")
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    source_doc: str = Field(..., description="Source document ID")
    evidence: str | None = Field(None, description="Original text span from FIR/CDR")
    timestamp: str | None = None

    # Type-specific optional fields
    duration: int | None = Field(None, description="Call duration in seconds (CALLED)")
    role: str | None = Field(None, description="Role in organization (MEMBER_OF)")
    amount: float | None = Field(None, description="Transaction amount (TRANSACTED_WITH)")
    transaction_id: str | None = Field(None, description="Transaction ID (TRANSACTED_WITH)")


# ─── Top-Level Payload ───────────────────────────────────────────────────────


class NLPOutputPayload(BaseModel):
    """Top-level payload matching Abhidha's output_contract.json.

    Flat structure: all entities in one array (discriminated by `type`),
    all relationships in another.
    """
    entities: list[dict] = Field(..., description="Mixed entity array with `type` discriminator")
    relationships: list[RelationshipPayload] = Field(default_factory=list)
