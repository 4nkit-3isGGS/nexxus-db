"""
Unit Tests for Cybercrime, Blockchain Entities, and Cryptographic Security
-------------------------------------------------------------------------
Covers:
1. Pydantic models for CryptoWallet, IPAddress, IMEI
2. Ingestion validation (schema checks, field checks, referential integrity)
3. Field-level AES-256 PII encryption & HMAC-SHA256 blind indexing
4. SECP256R1 ECDSA digital signatures for audit chain blocks
5. Ingestion handlers for cyber entities and edges
6. Section 65B BSA Cryptographic Audit Ledger automatic ingestion logging
7. Multi-Agent Financial & Cyber Forensics reasoning
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.app.models.entities import (
    CryptoWalletEntity,
    IPAddressEntity,
    IMEIEntity,
    RelationshipPayload,
)
from backend.app.ingestion.validator import (
    validate_nlp_payload,
    validate_or_raise,
    PayloadValidationError,
)
from backend.app.security.encryption import (
    encrypt_pii,
    decrypt_pii,
    generate_blind_index,
    generate_keypair,
    sign_audit_block,
    verify_audit_signature,
)
from backend.app.ingestion.graph_ingestor import (
    ingest_cryptowallet,
    ingest_ip_address,
    ingest_imei,
    ingest_rel_controls_wallet,
    ingest_rel_transferred_funds,
    ingest_rel_bound_to_imei,
    ingest_rel_accessed_via,
    ingest_nlp_payload,
)
from backend.app.audit.audit_logger import audit_ledger
from backend.app.agents.nodes.financial_analyst import financial_analyst_node


# =====================================================================
# 1. Pydantic Models & Field Validation
# =====================================================================

def test_crypto_wallet_entity_valid():
    wallet = CryptoWalletEntity(
        id="CW001",
        type="CryptoWallet",
        source_doc="FIR_101",
        address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        network="Bitcoin",
        currency="BTC",
        exchange_tag="Binance",
        risk_score=0.75,
    )
    assert wallet.address == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    assert wallet.network == "Bitcoin"
    assert wallet.currency == "BTC"
    assert wallet.risk_score == 0.75


def test_ip_address_entity_valid():
    ip = IPAddressEntity(
        id="IP001",
        type="IPAddress",
        source_doc="FIR_101",
        ip="103.212.14.88",
        is_vpn=True,
        vpn_provider="NordVPN",
        country="IN",
        isp="Airtel",
    )
    assert ip.ip == "103.212.14.88"
    assert ip.is_vpn is True
    assert ip.vpn_provider == "NordVPN"


def test_imei_entity_valid():
    imei = IMEIEntity(
        id="IM001",
        type="IMEI",
        source_doc="FIR_101",
        imei="864201048891234",
        tac="86420104",
        manufacturer="OnePlus",
        model_name="Nord CE",
        is_dual_sim=True,
    )
    assert imei.imei == "864201048891234"
    assert imei.tac == "86420104"
    assert imei.is_dual_sim is True


def test_relationship_payload_cyber_fields():
    rel = RelationshipPayload(
        source="P001",
        target="CW001",
        type="CONTROLS_WALLET",
        source_doc="FIR_101",
        confidence=0.95,
        amount=150000.0,
        tx_hash="0xabcd1234ef",
        network="TRC-20",
        service_accessed="Banking Portal",
    )
    assert rel.type == "CONTROLS_WALLET"
    assert rel.amount == 150000.0
    assert rel.tx_hash == "0xabcd1234ef"
    assert rel.service_accessed == "Banking Portal"


# =====================================================================
# 2. Ingestion Validation Tests
# =====================================================================

def test_validator_accepts_cyber_payload():
    payload = {
        "entities": [
            {"id": "P001", "type": "Person", "name": "Vikram Malhotra"},
            {"id": "CW001", "type": "CryptoWallet", "address": "TQzV8F4nm9Xy2LK884JkW1b7X88V99trc20", "currency": "USDT"},
            {"id": "CW002", "type": "CryptoWallet", "address": "TX_COLD_WALLET_99", "currency": "USDT"},
            {"id": "IP001", "type": "IPAddress", "ip": "185.220.101.5", "is_vpn_tor": True},
            {"id": "IM001", "type": "IMEI", "imei": "864201048891234"},
        ],
        "relationships": [
            {"source": "P001", "target": "CW001", "type": "CONTROLS_WALLET", "confidence": 0.95},
            {"source": "CW001", "target": "CW002", "type": "TRANSFERRED_FUNDS", "amount": 250000.0, "tx_hash": "0x5d91c784..."},
            {"source": "P001", "target": "IM001", "type": "BOUND_TO_IMEI"},
            {"source": "P001", "target": "IP001", "type": "ACCESSED_VIA", "service_accessed": "Banking Portal"},
        ],
    }
    is_valid, errors = validate_nlp_payload(payload)
    assert is_valid is True, f"Validation failed: {errors}"
    assert errors == []


def test_validator_rejects_invalid_cyber_fields():
    payload = {
        "entities": [
            {"id": "CW_BAD", "type": "CryptoWallet", "address": ""},  # empty address
            {"id": "IP_BAD", "type": "IPAddress", "ip": ""},  # empty IP
            {"id": "IM_BAD", "type": "IMEI", "imei": "12345"},  # not 14-16 digits
        ],
        "relationships": [],
    }
    is_valid, errors = validate_nlp_payload(payload)
    assert is_valid is False
    assert len(errors) >= 3


def test_validate_or_raise_raises_on_invalid():
    payload = {"entities": [{"id": "bad", "type": "UnknownType"}], "relationships": []}
    with pytest.raises(PayloadValidationError):
        validate_or_raise(payload)


# =====================================================================
# 3. Field-Level AES-256 Encryption & Blind Indexing
# =====================================================================

def test_aes256_pii_encryption_roundtrip():
    aadhaar = "9876-5432-1098"
    encrypted = encrypt_pii(aadhaar)
    assert encrypted != aadhaar
    assert len(encrypted) > len(aadhaar)

    decrypted = decrypt_pii(encrypted)
    assert decrypted == aadhaar


def test_encryption_handles_empty():
    assert encrypt_pii("") == ""
    assert decrypt_pii("") == ""
    assert encrypt_pii(None) is None


def test_hmac_blind_index_deterministic_and_one_way():
    phone = "+919876543210"
    b_idx1 = generate_blind_index(phone)
    b_idx2 = generate_blind_index(phone)

    # Deterministic: identical inputs produce identical hash indexes for DB searching
    assert b_idx1 == b_idx2
    assert b_idx1.startswith("idx:sha256:")
    assert len(b_idx1) == 75
    assert b_idx1 != phone

    # Different inputs produce different indexes
    b_idx_diff = generate_blind_index("+919876543211")
    assert b_idx1 != b_idx_diff


# =====================================================================
# 4. ECDSA SECP256R1 Digital Signatures
# =====================================================================

def test_ecdsa_signature_verification():
    priv_key, pub_key = generate_keypair()
    block_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    sig_hex = sign_audit_block(block_hash, priv_key)
    assert isinstance(sig_hex, str)
    assert len(sig_hex) > 60

    # Verification passes with correct hash and key
    assert verify_audit_signature(block_hash, sig_hex, pub_key) is True

    # Verification fails if hash is tampered
    tampered_hash = "0000000000fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert verify_audit_signature(tampered_hash, sig_hex, pub_key) is False

    # Verification fails if another key is used
    _, other_pub_key = generate_keypair()
    assert verify_audit_signature(block_hash, sig_hex, other_pub_key) is False


# =====================================================================
# 5. Cypher Ingestion Handlers (Mocked DB Driver)
# =====================================================================

def test_graph_ingestor_cyber_handlers():
    with patch("backend.app.ingestion.graph_ingestor.db") as mock_db:
        mock_db.query.return_value = [{"id": "CW-123"}]

        # 1. Ingest CryptoWallet
        wallet = {
            "wallet_address": "TQzV8F4nm9Xy2LK884JkW1b7X88V99trc20",
            "network": "TRC-20",
            "currency": "USDT",
            "risk_score": 0.82,
        }
        w_id = ingest_cryptowallet(wallet)
        assert w_id.startswith("CW-") or len(w_id) > 0
        assert mock_db.query.called

        # 2. Ingest IPAddress
        mock_db.query.return_value = [{"id": "IP-123"}]
        ip = {
            "ip": "185.220.101.5",
            "is_vpn_tor": True,
            "vpn_provider": "Tor",
            "country": "DE",
        }
        ip_id = ingest_ip_address(ip)
        assert ip_id.startswith("IP-") or len(ip_id) > 0

        # 3. Ingest IMEI
        mock_db.query.return_value = [{"id": "IMEI-123"}]
        imei = {
            "imei": "864201048891234",
            "manufacturer": "OnePlus",
            "is_dual_sim": True,
        }
        imei_id = ingest_imei(imei)
        assert imei_id.startswith("IMEI-") or len(imei_id) > 0

        # 4. Ingest Cyber Relationships
        id_map = {
            "P001": {"_neo4j_id": "P-UUID-01"},
            "CW001": {"_neo4j_id": "CW-UUID-01"},
            "CW002": {"_neo4j_id": "CW-UUID-02"},
            "IM001": {"_neo4j_id": "IMEI-UUID-01"},
            "IP001": {"_neo4j_id": "IP-UUID-01"},
        }
        ingest_rel_controls_wallet({"source": "P001", "target": "CW001", "confidence": 0.95}, id_map)
        ingest_rel_transferred_funds({"source": "CW001", "target": "CW002", "amount": 50000.0, "tx_hash": "0xABC"}, id_map)
        ingest_rel_bound_to_imei({"source": "P001", "target": "IM001"}, id_map)
        ingest_rel_accessed_via({"source": "P001", "target": "IP001", "service_accessed": "Admin Portal"}, id_map)

        assert mock_db.query.call_count >= 7


def test_full_payload_ingestion_registers_audit_block():
    with patch("backend.app.ingestion.graph_ingestor.db") as mock_db, \
         patch("backend.app.ingestion.graph_ingestor.ingest_suspect") as mock_suspect:
        
        mock_suspect.return_value = "P-MOCKED-01"
        mock_db.query.return_value = [{"id": "MOCK-ID"}]

        initial_chain_len = len(audit_ledger._ledger)

        payload = {
            "entities": [
                {"id": "P001", "type": "Person", "name": "Vikram Malhotra"},
                {"id": "CW001", "type": "CryptoWallet", "address": "1BoatSLRHtKNngkdXEeobR76b53LETtpyT", "currency": "BTC"},
                {"id": "CW002", "type": "CryptoWallet", "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "currency": "BTC"},
                {"id": "IP001", "type": "IPAddress", "ip": "45.118.60.12"},
                {"id": "IM001", "type": "IMEI", "imei": "358923091234567"},
            ],
            "relationships": [
                {
                    "source": "CW001",
                    "target": "CW002",
                    "type": "TRANSFERRED_FUNDS",
                    "amount": 1.25,
                    "network": "Bitcoin",
                }
            ]
        }

        results = ingest_nlp_payload(payload)
        assert results["persons_ingested"] == 1
        assert results["wallets_ingested"] == 2
        assert results["ip_addresses_ingested"] == 1
        assert results["imeis_ingested"] == 1
        assert results["relationships_ingested"] == 1

        # Verify audit ledger block was appended
        assert len(audit_ledger._ledger) == initial_chain_len + 1
        latest_block = audit_ledger._ledger[-1]
        assert latest_block.action == "INGEST_PAYLOAD"
        assert latest_block.details["cyber_entities"] == 4

        # Verify cryptographic ledger integrity
        verification = audit_ledger.verify_chain_integrity()
        assert verification["verified"] is True


# =====================================================================
# 6. Multi-Agent Financial & Cyber Forensics Reasoning Node
# =====================================================================

def test_financial_analyst_node_cyber_reasoning():
    state = {
        "subject_entity_id": "P_CYBER_MULE",
        "iteration": 1,
        "discovered_entities": [
            {
                "type": "CryptoWallet",
                "wallet_address": "TQzV8F4nm9Xy2LK884JkW1b7X88V99trc20",
                "network": "USDT (TRC-20)",
                "known_exchange": "Huobi P2P",
            },
            {
                "type": "IPAddress",
                "ip_address": "185.220.101.5",
                "is_vpn_tor": True,
            },
            {
                "type": "IMEI",
                "imei": "864201048891234",
            },
        ],
        "discovered_relationships": [
            {
                "type": "TRANSFERRED_FUNDS",
                "source": "TQzV8F4nm9Xy2LK884JkW1b7X88V99trc20",
                "target": "TARGET_COLD_WALLET",
                "amount": 750000.0,
                "tx_hash": "0xfe3b88...c1",
                "network": "TRC-20",
            },
            {
                "type": "BOUND_TO_IMEI",
                "source": "+919876543210",
                "target": "864201048891234",
            },
            {
                "type": "BOUND_TO_IMEI",
                "source": "+919876543211",  # Second phone on same IMEI -> SIM Box signature!
                "target": "864201048891234",
            },
        ],
        "risk_analysis": {
            "anomalies": ["Circular fund routing detected between P001 and mule accounts"]
        },
        "tool_history": [],
    }

    result = financial_analyst_node(state)
    dossier = result["financial_analysis"]

    assert dossier["subject_id"] == "P_CYBER_MULE"
    # Crypto off-ramp tracking
    assert dossier["crypto_off_ramp"]["wallet_protocol"] == "USDT (TRC-20)"
    assert dossier["crypto_off_ramp"]["flagged_address"] == "TQzV8F4nm9Xy2LK884JkW1b7X88V99trc20"
    assert dossier["crypto_off_ramp"]["transfers_tracked"] == 1
    assert dossier["crypto_off_ramp"]["total_crypto_volume"] == 750000.0

    # Hardware & SIM Box detection
    hardware = dossier["hardware_correlation"]
    assert "SIM Box signature" in hardware["shared_imei_cluster"]
    assert "185.220.101.5" in hardware["vpn_ip_endpoints"]
    assert hardware["total_imeis_tracked"] == 1
    assert hardware["total_ips_tracked"] == 1
