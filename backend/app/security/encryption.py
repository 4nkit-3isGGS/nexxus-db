"""
Field-Level Encryption & Cryptographic Signatures
-------------------------------------------------
Enforces defense-in-depth security for law enforcement records:
1. Two-Way Field Encryption (AES-256 via Fernet): Encrypts sensitive citizen PII
   (Aadhaar, PAN, informant identities) so they are stored encrypted at rest in Neo4j.
2. Blind Indexing (HMAC-SHA256): Generates deterministic, irreversible search hashes
   allowing exact-match search on encrypted records without decrypting the whole database.
3. Asymmetric Digital Signatures (ECDSA SECP256R1): Investigating officers cryptographically
   sign evidence hashes and audit blocks under the Information Technology Act, 2000 and BSA §65B.
"""

import os
import hmac
import hashlib
import base64
from typing import Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend


# Master Data Encryption Key (Derived from env or default secure development secret)
_ENV_MASTER_KEY = os.getenv("NEXXUS_MASTER_ENCRYPTION_KEY")
if _ENV_MASTER_KEY:
    try:
        # Validate or pad to valid url-safe base64 32 bytes
        _MASTER_KEY = _ENV_MASTER_KEY.encode("utf-8")
        Fernet(_MASTER_KEY)
    except Exception:
        # Generate deterministic key from provided string
        derived = hashlib.sha256(_ENV_MASTER_KEY.encode("utf-8")).digest()
        _MASTER_KEY = base64.urlsafe_b64encode(derived)
else:
    # Deterministic default key for local/testing
    derived = hashlib.sha256(b"NEXXUS_DB_SIH2026_MASTER_SECRET_KEY_PROD_DEFENSE").digest()
    _MASTER_KEY = base64.urlsafe_b64encode(derived)

_BLIND_INDEX_SALT = os.getenv("NEXXUS_BLIND_INDEX_SALT", "NEXXUS_INDIAN_LAW_ENFORCEMENT_SALT_2026").encode("utf-8")

_CIPHER_PREFIX = "enc:v1:"
_INDEX_PREFIX = "idx:sha256:"


# =========================================================================
# 1. Two-Way Field Encryption (AES-256)
# =========================================================================

def encrypt_pii(plaintext: Optional[str], custom_key: Optional[bytes] = None) -> Optional[str]:
    """Encrypts plaintext string (Aadhaar, PAN, informant note) to AES-256 ciphertext.
    
    Returns string prefixed with 'enc:v1:' for clear data-at-rest demarcation.
    """
    if plaintext is None or not str(plaintext).strip():
        return plaintext

    val_str = str(plaintext).strip()
    if val_str.startswith(_CIPHER_PREFIX):
        return val_str  # Already encrypted

    key = custom_key or _MASTER_KEY
    fernet = Fernet(key)
    encrypted_bytes = fernet.encrypt(val_str.encode("utf-8"))
    return f"{_CIPHER_PREFIX}{encrypted_bytes.decode('utf-8')}"


def decrypt_pii(ciphertext: Optional[str], custom_key: Optional[bytes] = None) -> Optional[str]:
    """Decrypts ciphertext string back to raw plaintext if encrypted.
    
    If not encrypted, returns original value safely.
    """
    if ciphertext is None or not str(ciphertext).strip():
        return ciphertext

    val_str = str(ciphertext).strip()
    if not val_str.startswith(_CIPHER_PREFIX):
        return val_str  # Not encrypted, return as-is

    token = val_str[len(_CIPHER_PREFIX):].encode("utf-8")
    key = custom_key or _MASTER_KEY
    fernet = Fernet(key)
    try:
        decrypted_bytes = fernet.decrypt(token)
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        raise ValueError("Decryption failed: Invalid cryptographic key or corrupted ciphertext.")


# =========================================================================
# 2. Blind Indexing for Encrypted Search
# =========================================================================

def generate_blind_index(raw_value: Optional[str]) -> Optional[str]:
    """Generates an irreversible, deterministic HMAC-SHA256 blind index.
    
    Allows exact search in Neo4j (e.g., matching suspect Aadhaar) without
    storing the Aadhaar number in plaintext or decrypting all nodes.
    """
    if raw_value is None or not str(raw_value).strip():
        return None

    clean = "".join(c.upper() for c in str(raw_value) if c.isalnum())
    h = hmac.new(_BLIND_INDEX_SALT, clean.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{_INDEX_PREFIX}{h}"


# =========================================================================
# 3. Asymmetric Digital Signatures (ECDSA SECP256R1)
# =========================================================================

def generate_keypair() -> Tuple[bytes, bytes]:
    """Generates an elliptic curve (SECP256R1) keypair for an investigating officer.
    
    Returns:
        (private_key_pem: bytes, public_key_pem: bytes)
    """
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()

    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv_pem, pub_pem


def sign_audit_block(block_hash: str, private_key_pem: bytes) -> str:
    """Officer digital signature on a cryptographic audit block hash under BSA §65B.
    
    Returns signature in hex encoding.
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=None,
        backend=default_backend(),
    )
    signature = private_key.sign(
        block_hash.encode("utf-8"),
        ec.ECDSA(hashes.SHA256()),
    )
    return signature.hex()


def verify_audit_signature(block_hash: str, signature_hex: str, public_key_pem: bytes) -> bool:
    """Verifies an officer's ECDSA signature over an audit block or evidence record."""
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem,
            backend=default_backend(),
        )
        sig_bytes = bytes.fromhex(signature_hex)
        public_key.verify(
            sig_bytes,
            block_hash.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )
        return True
    except Exception:
        return False
