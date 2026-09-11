"""
Unit & Integration Tests for Law Enforcement RBAC and Tamper-Evident Audit Logging
----------------------------------------------------------------------------------
Verifies:
1. Role-based clearance enforcement (ADMIN, LEAD_INVESTIGATOR, INVESTIGATOR, ANALYST, AUDITOR).
2. Dynamic PII redaction (Aadhaar, PAN, phone) matching officer clearance levels.
3. Cryptographic hash-chain construction ($H_n = SHA256(H_{n-1} + payload)$).
4. Detection of retroactively tampered records and severed chain links.
5. FastAPI endpoints: GET /api/audit/logs, POST /api/audit/verify, and audited POST /api/investigate.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.auth.models import Role, Permission, UserSession
from backend.app.auth.rbac import (
    mask_aadhaar,
    mask_pan,
    mask_phone,
    mask_entity_pii,
)
from backend.app.audit.audit_logger import audit_ledger, compute_entry_hash, GENESIS_HASH
from backend.app.audit.models import AuditAction


@pytest.fixture(autouse=True)
def clean_audit_ledger():
    """Reset audit ledger before each test run for test isolation."""
    audit_ledger.reset_for_testing()
    yield
    audit_ledger.reset_for_testing()


# =========================================================================
# 1. RBAC & PII Redaction Tests
# =========================================================================

class TestRbacAndPiiRedaction:
    """Tests PII masking utilities and role permissions."""

    def test_mask_aadhaar_utility(self):
        assert mask_aadhaar("1234-5678-9012") == "XXXX-XXXX-9012"
        assert mask_aadhaar("998877665544") == "XXXX-XXXX-5544"
        assert mask_aadhaar(None) == "XXXX-XXXX-XXXX"

    def test_mask_pan_utility(self):
        assert mask_pan("ABCDE1234F") == "XXXXXX234F"
        assert mask_pan("BKZPS8821M") == "XXXXXX821M"
        assert mask_pan(None) == "XXXXXXXXXX"

    def test_mask_phone_utility(self):
        assert mask_phone("+91-9876543210") == "+91-XXXXX-XX210"
        assert mask_phone("9876543210") == "+91-XXXXX-XX210"
        assert mask_phone(None) == "+91-XXXXXXXXXX"

    def test_pii_unmasked_for_lead_investigator(self):
        lead_user = UserSession(
            user_id="OFF_001",
            badge_number="DL-IPS-01",
            role=Role.LEAD_INVESTIGATOR,
        )
        entity = {
            "id": "P001",
            "name": "Rahul Sharma",
            "aadhaar": "1234-5678-9012",
            "pan": "ABCDE1234F",
            "number": "+91-9876543210",
        }
        result = mask_entity_pii(entity, lead_user)
        # Full clearance: untouched
        assert result["aadhaar"] == "1234-5678-9012"
        assert result["pan"] == "ABCDE1234F"
        assert result["number"] == "+91-9876543210"

    def test_pii_partially_masked_for_field_investigator(self):
        field_user = UserSession(
            user_id="OFF_002",
            badge_number="DL-SI-02",
            role=Role.INVESTIGATOR,
        )
        entity = {
            "id": "P001",
            "name": "Rahul Sharma",
            "aadhaar": "1234-5678-9012",
            "pan": "ABCDE1234F",
            "number": "+91-9876543210",
        }
        result = mask_entity_pii(entity, field_user)
        # Aadhaar and PAN masked to last 4, phone left intact for telecommunications analysis
        assert result["aadhaar"] == "XXXX-XXXX-9012"
        assert result["pan"] == "XXXXXX234F"
        assert result["number"] == "+91-9876543210"

    def test_pii_strictly_masked_for_crime_analyst(self):
        analyst_user = UserSession(
            user_id="OFF_003",
            badge_number="INT-ANA-03",
            role=Role.ANALYST,
        )
        entity = {
            "id": "P001",
            "name": "Rahul Sharma",
            "aadhaar": "1234-5678-9012",
            "pan": "ABCDE1234F",
            "number": "+91-9876543210",
        }
        result = mask_entity_pii(entity, analyst_user)
        # All PII masked for aggregate analytics
        assert result["aadhaar"] == "XXXX-XXXX-9012"
        assert result["pan"] == "XXXXXX234F"
        assert result["number"] == "+91-XXXXX-XX210"


# =========================================================================
# 2. Cryptographic Tamper-Evident Audit Ledger Tests
# =========================================================================

class TestTamperEvidentAuditLedger:
    """Tests cryptographic hash-chaining and Section 65B tamper detection."""

    def test_audit_ledger_records_and_chains_events(self):
        entry1 = audit_ledger.log_event(
            user_id="OFF_001",
            badge_number="DL-01",
            role="LEAD_INVESTIGATOR",
            action=AuditAction.SEARCH_ENTITY.value,
            resource_type="Person",
            resource_id="Rahul Sharma",
        )
        assert entry1.prev_hash == GENESIS_HASH
        assert len(entry1.entry_hash) == 64

        entry2 = audit_ledger.log_event(
            user_id="OFF_002",
            badge_number="DL-02",
            role="INVESTIGATOR",
            action=AuditAction.GET_ENTITY.value,
            resource_type="Person",
            resource_id="P001",
        )
        # Entry 2 must be cryptographically chained to Entry 1
        assert entry2.prev_hash == entry1.entry_hash
        assert len(entry2.entry_hash) == 64

    def test_audit_ledger_verifies_intact_chain(self):
        for i in range(5):
            audit_ledger.log_event(
                user_id=f"OFF_00{i}",
                badge_number=f"DL-0{i}",
                role="INVESTIGATOR",
                action=AuditAction.VIEW_NEIGHBORS.value,
                resource_type="Person",
                resource_id=f"P00{i}",
            )

        verification = audit_ledger.verify_chain_integrity()
        assert verification["verified"] is True
        assert verification["record_count"] == 5
        assert "BSA §65B" in verification["message"]

    def test_audit_ledger_detects_content_tampering(self):
        # 1. Populate ledger with 3 valid records
        for i in range(3):
            audit_ledger.log_event(
                user_id=f"OFF_00{i}",
                badge_number=f"DL-0{i}",
                role="INVESTIGATOR",
                action=AuditAction.SEARCH_ENTITY.value,
                resource_type="Person",
                resource_id=f"P00{i}",
            )

        # 2. Malicious insider tampers with record #1 (e.g. changing searched target)
        audit_ledger._ledger[1].resource_id = "CLEANED_POLITICIAN_ID"

        # 3. Integrity verification must detect mathematical mismatch
        verification = audit_ledger.verify_chain_integrity()
        assert verification["verified"] is False
        assert verification["tampered_index"] == 1
        assert "Content tampering detected" in verification["reason"]

    def test_audit_ledger_detects_severed_link(self):
        # 1. Populate ledger
        for i in range(3):
            audit_ledger.log_event(
                user_id=f"OFF_00{i}",
                badge_number=f"DL-0{i}",
                role="INVESTIGATOR",
                action=AuditAction.GET_ENTITY.value,
                resource_type="Person",
                resource_id=f"P00{i}",
            )

        # 2. Rogue insider deletes middle record #1
        del audit_ledger._ledger[1]

        # 3. Integrity verification must catch broken backward hash pointer
        verification = audit_ledger.verify_chain_integrity()
        assert verification["verified"] is False
        assert "Severed hash-chain" in verification["reason"]


# =========================================================================
# 3. FastAPI Endpoint Integration Tests
# =========================================================================

class TestAuditAndRbacApiEndpoints:
    """Tests API authorization guards and audit verification routes."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_audit_logs_forbidden_for_analyst(self, client):
        headers = {
            "X-User-Id": "ANA_01",
            "X-Role": "ANALYST",
            "X-Badge-Number": "INT-01",
        }
        response = client.get("/api/audit/logs", headers=headers)
        assert response.status_code == 403
        assert "Access Denied" in response.json()["detail"]

    def test_get_audit_logs_permitted_for_auditor(self, client):
        # Log a dummy event first
        audit_ledger.log_event(
            user_id="OFF_LEAD",
            badge_number="DL-01",
            role="LEAD_INVESTIGATOR",
            action="TEST_ACTION",
            resource_type="Test",
            resource_id="T001",
        )

        headers = {
            "X-User-Id": "AUD_01",
            "X-Role": "AUDITOR",
            "X-Badge-Number": "VIG-01",
        }
        response = client.get("/api/audit/logs", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] >= 1
        assert len(data["entries"]) >= 1
        assert len(data["latest_hash"]) == 64

    def test_verify_audit_endpoint_certifies_integrity(self, client):
        audit_ledger.log_event(
            user_id="OFF_LEAD",
            badge_number="DL-01",
            role="LEAD_INVESTIGATOR",
            action="SEARCH_ENTITY",
            resource_type="Person",
            resource_id="P001",
        )

        headers = {
            "X-User-Id": "AUD_01",
            "X-Role": "AUDITOR",
            "X-Badge-Number": "VIG-01",
        }
        response = client.post("/api/audit/verify", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["record_count"] >= 1
        assert "BSA §65B" in data["message"]

    def test_investigation_endpoint_generates_audit_record(self, client):
        headers = {
            "X-User-Id": "INV_OFFICER_44",
            "X-Role": "INVESTIGATOR",
            "X-Badge-Number": "DL-IPS-44",
        }
        payload = {
            "query": "Investigate Rahul Sharma P001",
            "subject_id": "P001",
            "mock_mode": True,
        }

        # 1. Run investigation as Investigator
        response = client.post("/api/investigate", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"

        # 2. Check that the audit ledger has recorded this event
        entries, count = audit_ledger.get_entries(action="RUN_INVESTIGATION")
        assert count == 1
        audit_record = entries[0]
        assert audit_record.user_id == "INV_OFFICER_44"
        assert audit_record.role == "INVESTIGATOR"
        assert audit_record.action == "RUN_INVESTIGATION"
        assert audit_record.resource_id == "P001"
        assert len(audit_record.entry_hash) == 64

        # 3. Verify ledger integrity
        verification = audit_ledger.verify_chain_integrity()
        assert verification["verified"] is True

    def test_investigation_endpoint_denies_auditor(self, client):
        # An Auditor role only has read-only compliance rights, cannot run investigations
        headers = {
            "X-User-Id": "AUD_01",
            "X-Role": "AUDITOR",
            "X-Badge-Number": "VIG-01",
        }
        payload = {
            "query": "Investigate Rahul Sharma",
            "mock_mode": True,
        }
        response = client.post("/api/investigate", json=payload, headers=headers)
        assert response.status_code == 403
        assert "lacks required permission 'INVESTIGATE'" in response.json()["detail"]
