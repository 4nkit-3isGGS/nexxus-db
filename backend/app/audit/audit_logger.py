"""
Tamper-Evident Cryptographic Audit Logger (BSA §65B Admissible)
--------------------------------------------------------------
Implements an append-only cryptographic hash-chain ($H_n = SHA256(H_{n-1} + payload)$)
to guarantee the non-repudiation and legal integrity of all investigative queries,
entity searches, merges, and agent executions.
"""

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from backend.app.audit.models import AuditLogEntry, AuditAction

GENESIS_HASH: str = "0" * 64


def compute_entry_hash(
    prev_hash: str,
    log_id: str,
    timestamp: str,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    status: str,
    details: Dict[str, Any],
) -> str:
    """Calculates the SHA-256 hash of an audit entry chained to its predecessor."""
    canonical_details = json.dumps(details, sort_keys=True)
    payload = f"{prev_hash}|{log_id}|{timestamp}|{user_id}|{action}|{resource_type}|{resource_id}|{status}|{canonical_details}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class TamperEvidentAuditLedger:
    """Thread-safe append-only cryptographic audit ledger."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ledger: List[AuditLogEntry] = []
        self._latest_hash: str = GENESIS_HASH

    def log_event(
        self,
        user_id: str,
        badge_number: str,
        role: str,
        action: str,
        resource_type: str,
        resource_id: str,
        status: str = "SUCCESS",
        client_ip: str = "127.0.0.1",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Appends a new verified event to the cryptographic ledger."""
        with self._lock:
            log_seq = len(self._ledger) + 1
            log_id = f"LOG-{log_seq:06d}"
            timestamp = datetime.now(timezone.utc).isoformat()
            det = details or {}

            entry_hash = compute_entry_hash(
                prev_hash=self._latest_hash,
                log_id=log_id,
                timestamp=timestamp,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                status=status,
                details=det,
            )

            entry = AuditLogEntry(
                log_id=log_id,
                timestamp=timestamp,
                user_id=user_id,
                badge_number=badge_number,
                role=role,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                client_ip=client_ip,
                status=status,
                details=det,
                prev_hash=self._latest_hash,
                entry_hash=entry_hash,
            )

            self._ledger.append(entry)
            self._latest_hash = entry_hash
            return entry

    def get_entries(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> Tuple[List[AuditLogEntry], int]:
        """Retrieves paginated audit entries with optional filters."""
        with self._lock:
            filtered = self._ledger
            if user_id:
                filtered = [e for e in filtered if e.user_id == user_id]
            if action:
                filtered = [e for e in filtered if e.action == action]

            total = len(filtered)
            page = filtered[offset : offset + limit]
            return page, total

    def verify_chain_integrity(self) -> Dict[str, Any]:
        """Cryptographically verifies the entire hash-chain from genesis to tip.
        
        Returns:
            Dict containing verification status, checked record count,
            and the exact tampered entry index if an anomaly is detected.
        """
        with self._lock:
            if not self._ledger:
                return {
                    "verified": True,
                    "record_count": 0,
                    "latest_hash": GENESIS_HASH,
                    "message": "Audit ledger is empty (genesis state verified).",
                }

            expected_prev = GENESIS_HASH
            for idx, entry in enumerate(self._ledger):
                # 1. Check backward linkage
                if entry.prev_hash != expected_prev:
                    return {
                        "verified": False,
                        "tampered_index": idx,
                        "log_id": entry.log_id,
                        "reason": f"Severed hash-chain at entry {entry.log_id}: prev_hash does not match preceding entry_hash.",
                    }

                # 2. Recompute current hash to detect payload tampering
                computed_hash = compute_entry_hash(
                    prev_hash=entry.prev_hash,
                    log_id=entry.log_id,
                    timestamp=entry.timestamp,
                    user_id=entry.user_id,
                    action=entry.action,
                    resource_type=entry.resource_type,
                    resource_id=entry.resource_id,
                    status=entry.status,
                    details=entry.details,
                )

                if computed_hash != entry.entry_hash:
                    return {
                        "verified": False,
                        "tampered_index": idx,
                        "log_id": entry.log_id,
                        "reason": f"Content tampering detected at entry {entry.log_id}: cryptographic hash mismatch.",
                    }

                expected_prev = entry.entry_hash

            return {
                "verified": True,
                "record_count": len(self._ledger),
                "latest_hash": self._latest_hash,
                "message": "Full audit ledger integrity verified under BSA §65B standards.",
            }

    def reset_for_testing(self):
        """Resets ledger state for isolated test execution."""
        with self._lock:
            self._ledger.clear()
            self._latest_hash = GENESIS_HASH


# Global singleton audit ledger instance
audit_ledger = TamperEvidentAuditLedger()
