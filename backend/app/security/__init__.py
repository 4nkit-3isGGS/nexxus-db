"""
Nexxus DB Security & Cryptography Package
-----------------------------------------
Provides AES-256 field-level data encryption, HMAC blind indexing for searchable encryption,
and ECDSA digital signatures for BSA §65B court evidence non-repudiation.
"""

from backend.app.security.encryption import (
    encrypt_pii,
    decrypt_pii,
    generate_blind_index,
    generate_keypair,
    sign_audit_block,
    verify_audit_signature,
)

__all__ = [
    "encrypt_pii",
    "decrypt_pii",
    "generate_blind_index",
    "generate_keypair",
    "sign_audit_block",
    "verify_audit_signature",
]
