"""
Pydantic Models — Entities & Payloads
--------------------------------------
Defines validation schemas matching Abhidha's NLP output contract.
All data from the NLP pipeline passes through these models
before touching Neo4j.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional


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
    city: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class VehicleEntity(BaseModel):
    id: str
    type: Literal["Vehicle"]
    source_doc: str
    registration_number: str
    vehicle_type: str | None = None
    model: str | None = None
    color: str | None = None


class OrganizationEntity(BaseModel):
    id: str
    type: Literal["Organization"]
    source_doc: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    tax_id: str | None = None
    registration_id: str | None = None

class CryptoWalletEntity(BaseModel):
    id: str
    type: Literal["CryptoWallet"]
    source_doc: str
    address: str
    currency: str
    network: Optional[str] = None
    exchange_tag: Optional[str] = None
    risk_score: Optional[float] = None


class IPAddressEntity(BaseModel):
    id: str
    type: Literal["IPAddress"]
    source_doc: str
    ip: str
    isp: Optional[str] = None
    asn: Optional[str] = None
    is_vpn: Optional[bool] = False
    is_tor: Optional[bool] = False
    vpn_provider: Optional[str] = None
    country: Optional[str] = None


class IMEIEntity(BaseModel):
    id: str
    type: Literal["IMEI"]
    source_doc: str
    imei: str
    tac: Optional[str] = None
    manufacturer: Optional[str] = None
    device_model: Optional[str] = None
    is_sim_box: Optional[bool] = False
    is_dual_sim: Optional[bool] = False


# ─── Relationship Model ─────────────────────────────────────────────────────


class RelationshipPayload(BaseModel):
    """A single relationship extracted by the NLP pipeline.

    source/target are entity IDs (e.g. 'P001', 'PH002', 'ORG001', 'W001', 'IP001', 'IMEI001').
    Extra fields (duration, role, amount, tx_hash, etc.) are type-dependent.
    """
    source: str = Field(..., description="Source entity ID")
    target: str = Field(..., description="Target entity ID")
    type: str = Field(..., description="CALLED, MEMBER_OF, OWNS_PHONE, PRESENT_AT, OWNS_VEHICLE, TRANSACTED_WITH, CONTROLS_WALLET, TRANSFERRED_FUNDS, BOUND_TO_IMEI, ACCESSED_VIA")
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    source_doc: str = Field(..., description="Source document ID")
    evidence: str | None = Field(None, description="Original text span from FIR/CDR/forensics")
    timestamp: str | None = None

    # Type-specific optional fields
    duration: int | None = Field(None, description="Call duration in seconds (CALLED)")
    role: str | None = Field(None, description="Role in organization (MEMBER_OF)")
    amount: float | None = Field(None, description="Transaction amount (TRANSACTED_WITH, TRANSFERRED_FUNDS)")
    transaction_id: str | None = Field(None, description="Transaction ID (TRANSACTED_WITH)")
    tx_hash: str | None = Field(None, description="Blockchain transaction hash (TRANSFERRED_FUNDS)")
    network: str | None = Field(None, description="Blockchain network (e.g. BTC, ETH, TRC20)")
    service_accessed: str | None = Field(None, description="Service, port, or app accessed (ACCESSED_VIA)")


# ─── Top-Level Payload ───────────────────────────────────────────────────────


class NLPOutputPayload(BaseModel):
    """Top-level payload matching Abhidha's output_contract.json.

    Flat structure: all entities in one array (discriminated by `type`),
    all relationships in another.
    """
    entities: list[dict] = Field(..., description="Mixed entity array with `type` discriminator")
    relationships: list[RelationshipPayload] = Field(default_factory=list)
