"""
Ingestion Payload Validator
---------------------------
Validates incoming NLP payloads before entity resolution and graph ingestion.
Guarantees schema correctness, referential integrity, and field boundaries.
"""

ALLOWED_ENTITY_TYPES = {"Person", "Phone", "Location", "Vehicle", "Organization","CryptoWallet", "IPAddress", "IMEI"}
ALLOWED_REL_TYPES = {
    "CALLED",
    "MEMBER_OF",
    "OWNS_PHONE",
    "PRESENT_AT",
    "OWNS_VEHICLE",
    "TRANSACTED_WITH",
    "CONTROLS_WALLET", 
    "TRANSFERRED_FUNDS",
     "BOUND_TO_IMEI", 
     "ACCESSED_VIA",
}


class PayloadValidationError(Exception):
    """Custom exception raised when payload validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Payload validation failed with {len(errors)} error(s): {'; '.join(errors)}")


def validate_nlp_payload(payload: dict) -> tuple[bool, list[str]]:
    """Validates an incoming NLP payload dict.

    Returns:
        (is_valid: bool, errors: list[str])
    """
    errors: list[str] = []

    # 1. Structural Check
    if not isinstance(payload, dict):
        return False, ["Payload must be a JSON object (dict)"]

    entities = payload.get("entities", [])
    relationships = payload.get("relationships", [])

    if not isinstance(entities, list):
        errors.append("'entities' field must be a list")
    if not isinstance(relationships, list):
        errors.append("'relationships' field must be a list")

    if errors:
        return False, errors

    #  Step 2 — Entity Validation
    seen_entity_ids = set()

    for idx, entity in enumerate(entities):
        if not isinstance(entity, dict):
            errors.append(f"Entity #{idx} must be a JSON object (dict)")
            continue

        entity_id = entity.get("id")
        entity_type = entity.get("type")

        if not entity_id or not isinstance(entity_id, str) or not entity_id.strip():
            errors.append(f"Entity #{idx}: missing or invalid 'id'")
        else:
            seen_entity_ids.add(entity_id)

        if not entity_type or entity_type not in ALLOWED_ENTITY_TYPES:
            errors.append(
                f"Entity '{entity_id or idx}': invalid 'type' '{entity_type}'. "
                f"Must be one of {sorted(ALLOWED_ENTITY_TYPES)}"
            )
        elif entity_type == "CryptoWallet":
            addr = entity.get("address") or entity.get("wallet_address")
            if not addr or not str(addr).strip():
                errors.append(f"CryptoWallet entity '{entity_id}': missing or empty 'address'")
            curr = entity.get("currency") or entity.get("network")
            if not curr or not str(curr).strip():
                errors.append(f"CryptoWallet entity '{entity_id}': missing or empty 'currency'")
        elif entity_type == "IPAddress":
            ip_val = entity.get("ip") or entity.get("ip_address")
            if not ip_val or not str(ip_val).strip():
                errors.append(f"IPAddress entity '{entity_id}': missing or empty 'ip'")
        elif entity_type == "IMEI":
            imei_val = str(entity.get("imei") or "").strip()
            if not imei_val:
                errors.append(f"IMEI entity '{entity_id}': missing or empty 'imei'")
            elif not imei_val.isdigit() or not (14 <= len(imei_val) <= 16):
                errors.append(f"IMEI entity '{entity_id}': invalid IMEI format '{imei_val}' (must be 14-16 digits)")


    # Step 3 — Relationship Validation & Referential Integrity
    for idx, rel in enumerate(relationships):
        if not isinstance(rel, dict):
            errors.append(f"Relationship #{idx} must be a JSON object (dict)")
            continue

        source = rel.get("source")
        target = rel.get("target")
        rel_type = rel.get("type")

        # 3a. Relationship Type Check
        if not rel_type or rel_type not in ALLOWED_REL_TYPES:
            errors.append(
                f"Relationship #{idx} ({source or '?'} -> {target or '?'}): "
                f"invalid 'type' '{rel_type}'. Must be one of {sorted(ALLOWED_REL_TYPES)}"
            )

        # 3b. Source & Target Presence
        if not source:
            errors.append(f"Relationship #{idx}: missing 'source' entity ID")
        elif source not in seen_entity_ids:
            errors.append(
                f"Relationship #{idx}: 'source' entity ID '{source}' was not declared in payload entities"
            )

        if not target:
            errors.append(f"Relationship #{idx}: missing 'target' entity ID")
        elif target not in seen_entity_ids:
            errors.append(
                f"Relationship #{idx}: 'target' entity ID '{target}' was not declared in payload entities"
            )

        # Step 4 — Property / Hygiene Checks
        confidence = rel.get("confidence")
        if confidence is not None:
            if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
                errors.append(
                    f"Relationship #{idx} ({source} -> {target}): "
                    f"confidence score '{confidence}' must be a float between 0.0 and 1.0"
                )

    return len(errors) == 0, errors


def validate_or_raise(payload: dict):
    """Convenience helper that validates payload and raises PayloadValidationError if invalid."""
    is_valid, errors = validate_nlp_payload(payload)
    if not is_valid:
        raise PayloadValidationError(errors)
