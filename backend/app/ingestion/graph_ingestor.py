"""
Graph Ingestion Pipeline
------------------------
Receives structured JSON data (from NLP extraction of FIRs and CDRs),
runs Entity Resolution to deduplicate, and persists entities and
relationships into Neo4j.
"""

import uuid
import json
import hashlib
from datetime import datetime, timezone

from backend.app.neo4j_driver import db
from backend.app.resolution.normalizer import normalize_name, normalize_phone
from backend.app.resolution.resolver import resolve_entity
from backend.app.ingestion.validator import validate_or_raise


def get_person_candidates() -> list:
    """Fetches all Person nodes from Neo4j with their phones and aliases.

    Returns a list of dicts matching the format resolve_entity() expects:
    [{"id": ..., "name": ..., "aliases": [...], "phones": [...]}, ...]
    """
    cypher_query = """
    MATCH (p:Person)
    OPTIONAL MATCH (p)-[:OWNS_PHONE]->(ph:Phone)
    RETURN p.id AS id, p.name AS name, p.aliases AS aliases, collect(ph.number) AS phones
    """
    return db.query(cypher_query)


def create_new_person(suspect: dict, source_doc: str) -> str:
    """Creates a new Person node in Neo4j with a generated UUID.

    Returns the generated person_id for use in linking relationships.
    """
    norm_name = normalize_name(suspect.get("name"))
    person_id = f"P-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher_query = """
    MERGE (p:Person {id: $id})
    SET p.name = $name,
        p.normalized_name = $normalized_name,
        p.aliases = $aliases,
        p.created_at = $timestamp,
        p.updated_at = $timestamp
    """
    db.query(cypher_query, {
        "id": person_id,
        "name": suspect.get("name"),
        "normalized_name": norm_name,
        "aliases": suspect.get("aliases", []),
        "timestamp": timestamp,
    })

    return person_id


def update_existing_person(person_id: str, suspect: dict, source_doc: str):
    """Merges new aliases into an existing Person node (used on AUTO_MERGE).

    Appends only aliases that don't already exist on the node,
    and updates the updated_at timestamp.
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher_query = """
    MATCH (p:Person {id: $id})
    SET p.aliases = COALESCE(p.aliases, []) + [x IN $new_aliases WHERE NOT x IN COALESCE(p.aliases, [])],
        p.updated_at = $timestamp
    """
    db.query(cypher_query, {
        "id": person_id,
        "new_aliases": suspect.get("aliases", []),
        "timestamp": timestamp,
    })

def flag_for_review(
    id1: str,
    id2: str,
    confidence_score: float,
    reason: str,
    entity_type: str | None = None,
):
    """Flags two potential duplicate entities (Person, Organization, Location, etc.) for human review."""
    flagged_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cypher_query = """
    MATCH (e1 {id: $id1}), (e2 {id: $id2})
    MERGE (e1)-[r:POSSIBLE_DUPLICATE]->(e2)
    SET r.confidence_score = $confidence_score,
        r.reason = $reason,
        r.entity_type = COALESCE($entity_type, labels(e1)[0]),
        r.flagged_at = $flagged_at
    """

    db.query(cypher_query, {
        "id1": id1,
        "id2": id2,
        "flagged_at": flagged_at,
        "confidence_score": confidence_score,
        "reason": reason,
        "entity_type": entity_type,
    })

def ingest_phone(phone_number: str, person_id: str):
    """Links a Person to a Phone node. Creates the Phone node if not present."""
    norm_phone = normalize_phone(phone_number)
    phone_id = f"PH-{uuid.uuid4()}"

    cypher_query = """
    MATCH (p:Person {id: $person_id})
    MERGE (ph:Phone {number: $norm_phone})
    ON CREATE SET ph.id = $phone_id, ph.normalized_number = $norm_phone
    MERGE (p)-[r:OWNS_PHONE]->(ph)
    """

    db.query(cypher_query, {
        "person_id": person_id,
        "phone_number": phone_number,
        "norm_phone": norm_phone,
        "phone_id": phone_id,
    })

def ingest_relationship(
    source_phone: str,
    target_phone: str,
    rel_type: str,
    properties: dict,
    source_doc: str,
):
    """Creates a relationship between Phone nodes and between attributed Person nodes.

    Supported rel_types: CALLED, PRESENT_AT, TRANSACTED_WITH.
    Properties dict can carry timestamp, duration_sec, location, amount, etc.
    Every relationship is stamped with source_doc_id for provenance tracking.
    """

    allowed_types = {"CALLED", "PRESENT_AT", "TRANSACTED_WITH"}
    if rel_type not in allowed_types:
        raise ValueError(f"Unsupported relationship type: {rel_type}")

    norm_src = normalize_phone(source_phone)
    norm_tgt = normalize_phone(target_phone)

    # DYNAMIC PROPERTY BUILDING
    prop_assignments = ", ".join(f"r.{key} = ${key}" for key in properties)
    prop_set_clause = f", {prop_assignments}" if prop_assignments else ""

    params = {
        "src_phone": norm_src,
        "tgt_phone": norm_tgt,
        "source_doc": source_doc,
        **properties,       # spreads {"timestamp": "...", "duration_sec": 180} etc.
    }

    # 1. Connect Phone to Phone directly (ensures CDR edges are always preserved)
    cypher_phone_rel = f"""
    MATCH (ph1:Phone {{number: $src_phone}})
    MATCH (ph2:Phone {{number: $tgt_phone}})
    MERGE (ph1)-[r:{rel_type}]->(ph2)
    SET r.source_doc_id = $source_doc{prop_set_clause}
    """
    db.query(cypher_phone_rel, params)

    # 2. Also connect Person to Person if both phones are attributed to suspects
    cypher_person_rel = f"""
    MATCH (src:Person)-[:OWNS_PHONE]->(:Phone {{number: $src_phone}})
    MATCH (tgt:Person)-[:OWNS_PHONE]->(:Phone {{number: $tgt_phone}})
    MERGE (src)-[r:{rel_type}]->(tgt)
    SET r.source_doc_id = $source_doc{prop_set_clause}
    """
    db.query(cypher_person_rel, params)


def ingest_location(name: str, source_doc: str, lat: float | None = None, lon: float | None = None) -> str:
    """Creates or merges a Location node. Returns the location ID."""
    from backend.app.resolution.normalizer import normalize_name as _nn

    norm = _nn(name)
    loc_id = f"LOC-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher_query = """
    MERGE (l:Location {normalized_name: $norm})
    ON CREATE SET l.id   = $id,
                  l.name = $name,
                  l.latitude  = $lat,
                  l.longitude = $lon,
                  l.created_at = $ts
    ON MATCH  SET l.updated_at = $ts
    RETURN l.id AS id
    """
    result = db.query(cypher_query, {
        "id": loc_id, "name": name, "norm": norm,
        "lat": lat, "lon": lon, "ts": timestamp,
    })
    return result[0]["id"] if result else loc_id


def ingest_vehicle(
    registration_number: str,
    vehicle_type: str | None = None,
    source_doc: str = "UNKNOWN",
) -> str:
    """Creates or merges a Vehicle node by registration number.
    Detects vehicle_type conflicts (e.g. Motorcycle vs SUV on same plate)
    to flag suspected cloned/stolen plates.
    """
    reg = registration_number.upper().replace(" ", "").replace("-", "")
    veh_id = f"VEH-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Check if vehicle registration already exists in graph
    try:
        existing = db.query(
            "MATCH (v:Vehicle {registration_number: $reg}) RETURN v.id AS id, v.vehicle_type AS vehicle_type",
            {"reg": reg},
        )
    except Exception as e:
        print(f"[Neo4j Warning] Failed to check existing vehicle: {e}")
        existing = []

    if existing:
        curr_id = existing[0]["id"]
        stored_type = existing[0].get("vehicle_type")

        if (
            stored_type
            and vehicle_type
            and stored_type.strip().lower() != vehicle_type.strip().lower()
        ):
            conflict_msg = f"Type conflict: recorded as '{stored_type}', reported as '{vehicle_type}' in {source_doc}"
            cypher_conflict = """
            MATCH (v:Vehicle {id: $id})
            SET v.is_cloned_suspicious = true,
                v.attribute_conflicts = COALESCE(v.attribute_conflicts, []) + [$conflict_msg],
                v.updated_at = $ts
            """
            db.query(cypher_conflict, {
                "id": curr_id,
                "conflict_msg": conflict_msg,
                "ts": timestamp,
            })
        else:
            cypher_update = """
            MATCH (v:Vehicle {id: $id})
            SET v.updated_at = $ts,
                v.vehicle_type = COALESCE(v.vehicle_type, $vtype)
            """
            db.query(cypher_update, {
                "id": curr_id,
                "vtype": vehicle_type,
                "ts": timestamp,
            })
        return curr_id


    cypher_create = """
    MERGE (v:Vehicle {registration_number: $reg})
    ON CREATE SET v.id = $id,
                  v.vehicle_type = $vtype,
                  v.is_cloned_suspicious = false,
                  v.attribute_conflicts = [],
                  v.created_at = $ts,
                  v.updated_at = $ts
    RETURN v.id AS id
    """
    result = db.query(cypher_create, {
        "id": veh_id,
        "reg": reg,
        "vtype": vehicle_type,
        "ts": timestamp,
    })
    return result[0]["id"] if result else veh_id


def get_organization_candidates() -> list:
    """Fetches all Organization nodes from Neo4j with their names, aliases, and tax IDs."""
    cypher_query = """
    MATCH (o:Organization)
    RETURN o.id AS id,
           o.name AS name,
           o.normalized_name AS normalized_name,
           o.aliases AS aliases,
           o.tax_id AS tax_id
    """
    try:
        return db.query(cypher_query)
    except Exception as e:
        print(f"[Neo4j Warning] Failed to fetch organization candidates: {e}")
        return []


def create_new_organization(org: dict, source_doc: str) -> str:
    """Creates a new Organization node in Neo4j with a generated UUID."""
    from backend.app.resolution.normalizer import normalize_org_name

    name = org.get("name", "")
    norm_name = normalize_org_name(name)
    org_id = f"ORG-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher_query = """
    MERGE (o:Organization {id: $id})
    SET o.name = $name,
        o.normalized_name = $normalized_name,
        o.aliases = $aliases,
        o.tax_id = $tax_id,
        o.created_at = $timestamp,
        o.updated_at = $timestamp
    """
    db.query(cypher_query, {
        "id": org_id,
        "name": name,
        "normalized_name": norm_name,
        "aliases": org.get("aliases", []),
        "tax_id": org.get("tax_id") or org.get("registration_id"),
        "timestamp": timestamp,
    })
    return org_id


def update_existing_organization(org_id: str, org: dict, source_doc: str):
    """Merges new aliases into an existing Organization node."""
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cypher_query = """
    MATCH (o:Organization {id: $id})
    SET o.aliases = COALESCE(o.aliases, []) + [x IN $new_aliases WHERE NOT x IN COALESCE(o.aliases, [])],
        o.updated_at = $timestamp
    """
    db.query(cypher_query, {
        "id": org_id,
        "new_aliases": org.get("aliases", []),
        "timestamp": timestamp,
    })


def ingest_organization(org: dict | str, source_doc: str = "UNKNOWN") -> str:
    """Ingests an Organization entity using the Resolution Engine.
    Handles AUTO_MERGE, FLAG_FOR_REVIEW, and CREATE_NEW.
    """
    from backend.app.resolution.resolver import ResolutionDecision, resolve_organization

    if isinstance(org, str):
        org = {"name": org}

    candidates = get_organization_candidates()
    result = resolve_organization(org, candidates)

    if result.decision == ResolutionDecision.AUTO_MERGE:
        org_id = result.matched_entity_id
        update_existing_organization(org_id, org, source_doc)
        return org_id

    elif result.decision == ResolutionDecision.FLAG_FOR_REVIEW:
        org_id = create_new_organization(org, source_doc)
        flag_for_review(
            id1=org_id,
            id2=result.matched_entity_id,
            confidence_score=result.confidence_score,
            reason="; ".join(result.match_reasons),
            entity_type="Organization",
        )
        return org_id

    else:  # CREATE_NEW
        return create_new_organization(org, source_doc)


def ingest_cryptowallet(wallet: dict, source_doc: str = "UNKNOWN") -> str:
    """Creates or updates a CryptoWallet node in Neo4j.
    Dedupes on address. Attaches exchange tag, risk score, and currency.
    """
    address = wallet.get("address", "").strip()
    currency = str(wallet.get("currency", "UNKNOWN")).upper().strip()
    wallet_id = f"CW-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher = """
    MERGE (cw:CryptoWallet {address: $address})
    ON CREATE SET cw.id = $id,
                  cw.currency = $currency,
                  cw.exchange_tag = $exchange_tag,
                  cw.risk_score = $risk_score,
                  cw.source_doc_id = $src,
                  cw.created_at = $ts,
                  cw.updated_at = $ts
    ON MATCH SET cw.currency = COALESCE(cw.currency, $currency),
                 cw.exchange_tag = COALESCE($exchange_tag, cw.exchange_tag),
                 cw.risk_score = COALESCE($risk_score, cw.risk_score),
                 cw.updated_at = $ts
    RETURN cw.id AS id
    """
    res = db.query(cypher, {
        "id": wallet_id,
        "address": address,
        "currency": currency,
        "exchange_tag": wallet.get("exchange_tag"),
        "risk_score": float(wallet.get("risk_score", 0.0)) if wallet.get("risk_score") is not None else 0.0,
        "src": source_doc,
        "ts": timestamp,
    })
    return res[0]["id"] if res else wallet_id


def ingest_ip_address(ip_entity: dict, source_doc: str = "UNKNOWN") -> str:
    """Creates or updates an IPAddress node in Neo4j.
    Tags infrastructure attributes (ISP, ASN, VPN, Tor).
    """
    ip = ip_entity.get("ip", "").strip()
    ip_id = f"IP-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher = """
    MERGE (ip:IPAddress {ip: $ip})
    ON CREATE SET ip.id = $id,
                  ip.isp = $isp,
                  ip.asn = $asn,
                  ip.is_vpn = $is_vpn,
                  ip.is_tor = $is_tor,
                  ip.country = $country,
                  ip.source_doc_id = $src,
                  ip.created_at = $ts,
                  ip.updated_at = $ts
    ON MATCH SET ip.isp = COALESCE($isp, ip.isp),
                 ip.asn = COALESCE($asn, ip.asn),
                 ip.is_vpn = COALESCE($is_vpn, ip.is_vpn),
                 ip.is_tor = COALESCE($is_tor, ip.is_tor),
                 ip.country = COALESCE($country, ip.country),
                 ip.updated_at = $ts
    RETURN ip.id AS id
    """
    res = db.query(cypher, {
        "id": ip_id,
        "ip": ip,
        "isp": ip_entity.get("isp"),
        "asn": ip_entity.get("asn"),
        "is_vpn": bool(ip_entity.get("is_vpn", False)),
        "is_tor": bool(ip_entity.get("is_tor", False)),
        "country": ip_entity.get("country"),
        "src": source_doc,
        "ts": timestamp,
    })
    return res[0]["id"] if res else ip_id


def ingest_imei(imei_entity: dict, source_doc: str = "UNKNOWN") -> str:
    """Creates or updates an IMEI device node in Neo4j.
    Tracks device models and SIM box flags.
    """
    imei = str(imei_entity.get("imei", "")).strip()
    imei_id = f"IMEI-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher = """
    MERGE (im:IMEI {imei: $imei})
    ON CREATE SET im.id = $id,
                  im.device_model = $device_model,
                  im.is_sim_box = $is_sim_box,
                  im.source_doc_id = $src,
                  im.created_at = $ts,
                  im.updated_at = $ts
    ON MATCH SET im.device_model = COALESCE($device_model, im.device_model),
                 im.is_sim_box = COALESCE($is_sim_box, im.is_sim_box),
                 im.updated_at = $ts
    RETURN im.id AS id
    """
    res = db.query(cypher, {
        "id": imei_id,
        "imei": imei,
        "device_model": imei_entity.get("device_model"),
        "is_sim_box": bool(imei_entity.get("is_sim_box", False)),
        "src": source_doc,
        "ts": timestamp,
    })
    return res[0]["id"] if res else imei_id


# ─── Orchestrator Functions ──────────────────────────────────────────────────


def ingest_suspect(suspect: dict, source_doc: str) -> str:
    """Orchestrates the full ingestion of a single Person entity.

    Pipeline:
      1. Fetch all existing Person candidates from Neo4j
      2. Run resolve_entity() from the Resolution Engine
      3. Branch on the decision:
         - AUTO_MERGE  → update existing Person, append aliases
         - FLAG_FOR_REVIEW → create new Person + POSSIBLE_DUPLICATE edge
         - CREATE_NEW  → create new Person

    Returns the person_id (new or matched).
    """
    from backend.app.resolution.resolver import ResolutionDecision

    # 1. Fetch candidates
    candidates = get_person_candidates()

    # 2. Resolve
    result = resolve_entity(suspect, candidates)

    # 3. Handle decision
    if result.decision == ResolutionDecision.AUTO_MERGE:
        person_id = result.matched_entity_id
        update_existing_person(person_id, suspect, source_doc)

    elif result.decision == ResolutionDecision.FLAG_FOR_REVIEW:
        person_id = create_new_person(suspect, source_doc)
        flag_for_review(
            id1=person_id,
            id2=result.matched_entity_id,
            confidence_score=result.confidence_score,
            reason="; ".join(result.match_reasons),
        )

    else:  # CREATE_NEW
        person_id = create_new_person(suspect, source_doc)

    return person_id


def ingest_rel_called(rel: dict, id_map: dict):
    """Handles CALLED relationship: Phone → Phone, resolved to Person → Person."""
    src_entity = id_map.get(rel["source"], {})
    tgt_entity = id_map.get(rel["target"], {})

    src_phone = src_entity.get("number", "")
    tgt_phone = tgt_entity.get("number", "")
    

    if not src_phone or not tgt_phone:
        print(f"[Ingestion Warning] CALLED: could not resolve phones for {rel['source']} → {rel['target']}")
        return

    props = {}
    if rel.get("timestamp"):
        props["timestamp"] = rel["timestamp"]
    if rel.get("duration") is not None:
        props["duration_sec"] = rel["duration"]
    if rel.get("confidence") is not None:
        props["confidence"] = rel["confidence"]
    if rel.get("evidence"):
        props["evidence"] = rel["evidence"]

    ingest_relationship(
        source_phone=src_phone,
        target_phone=tgt_phone,
        rel_type="CALLED",
        properties=props,
        source_doc=rel.get("source_doc", "UNKNOWN"),
    )


def ingest_rel_member_of(rel: dict, id_map: dict):
    """Handles MEMBER_OF: Person → Organization."""
    source_doc = rel.get("source_doc", "UNKNOWN")
    timestamp = rel.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Resolve Abhidha's IDs → our Neo4j IDs
    person_neo4j_id = id_map.get(rel["source"], {}).get("_neo4j_id", rel["source"])
    org_neo4j_id = id_map.get(rel["target"], {}).get("_neo4j_id", rel["target"])

    prop_parts = ["r.source_doc_id = $src"]
    params = {"pid": person_neo4j_id, "oid": org_neo4j_id, "src": source_doc}

    if rel.get("confidence") is not None:
        prop_parts.append("r.confidence = $conf")
        params["conf"] = rel["confidence"]
    if rel.get("role"):
        prop_parts.append("r.role = $role")
        params["role"] = rel["role"]
    if rel.get("evidence"):
        prop_parts.append("r.evidence = $evidence")
        params["evidence"] = rel["evidence"]
    if timestamp:
        prop_parts.append("r.timestamp = $ts")
        params["ts"] = timestamp

    prop_set = ", ".join(prop_parts)

    cypher = f"""
    MATCH (p:Person {{id: $pid}}), (o:Organization {{id: $oid}})
    MERGE (p)-[r:MEMBER_OF]->(o)
    SET {prop_set}
    """
    db.query(cypher, params)


def ingest_rel_owns_phone(rel: dict, id_map: dict):
    """Handles OWNS_PHONE: Person → Phone."""
    person_neo4j_id = id_map.get(rel["source"], {}).get("_neo4j_id", rel["source"])
    phone_entity = id_map.get(rel["target"], {})
    phone_number = phone_entity.get("number", "")
    if phone_number:
        ingest_phone(phone_number, person_neo4j_id)


def ingest_rel_present_at(rel: dict, id_map: dict):
    """Handles PRESENT_AT: Person → Location."""
    source_doc = rel.get("source_doc", "UNKNOWN")
    timestamp = rel.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Resolve Abhidha's IDs → our Neo4j IDs
    person_neo4j_id = id_map.get(rel["source"], {}).get("_neo4j_id", rel["source"])
    loc_neo4j_id = id_map.get(rel["target"], {}).get("_neo4j_id", rel["target"])

    prop_parts = ["r.source_doc_id = $src"]
    params = {"pid": person_neo4j_id, "lid": loc_neo4j_id, "src": source_doc}

    if rel.get("confidence") is not None:
        prop_parts.append("r.confidence = $conf")
        params["conf"] = rel["confidence"]
    if rel.get("evidence"):
        prop_parts.append("r.evidence = $evidence")
        params["evidence"] = rel["evidence"]
    if timestamp:
        prop_parts.append("r.timestamp = $ts")
        params["ts"] = timestamp

    prop_set = ", ".join(prop_parts)
    cypher = f"""
    MATCH (p:Person {{id: $pid}}), (l:Location {{id: $lid}})
    MERGE (p)-[r:PRESENT_AT]->(l)
    SET {prop_set}
    """
    db.query(cypher, params)


def ingest_rel_owns_vehicle(rel: dict, id_map: dict):
    """Handles OWNS_VEHICLE: Person → Vehicle."""
    source_doc = rel.get("source_doc", "UNKNOWN")
    timestamp = rel.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Resolve Abhidha's IDs → our Neo4j IDs
    person_neo4j_id = id_map.get(rel["source"], {}).get("_neo4j_id", rel["source"])
    veh_neo4j_id = id_map.get(rel["target"], {}).get("_neo4j_id", rel["target"])

    prop_parts = ["r.source_doc_id = $src"]
    params = {"pid": person_neo4j_id, "vid": veh_neo4j_id, "src": source_doc}

    if rel.get("confidence") is not None:
        prop_parts.append("r.confidence = $conf")
        params["conf"] = rel["confidence"]
    if rel.get("evidence"):
        prop_parts.append("r.evidence = $evidence")
        params["evidence"] = rel["evidence"]
    if timestamp:
        prop_parts.append("r.timestamp = $ts")
        params["ts"] = timestamp

    prop_set = ", ".join(prop_parts)
    cypher = f"""
    MATCH (p:Person {{id: $pid}}), (v:Vehicle {{id: $vid}})
    MERGE (p)-[r:OWNS_VEHICLE]->(v)
    SET {prop_set}
    """
    db.query(cypher, params)


def ingest_rel_transacted_with(rel: dict, id_map: dict):
    """Handles TRANSACTED_WITH: Person → Person (or Phone → Phone)."""
    source_id = rel.get("source", "")
    target_id = rel.get("target", "")

    src_entity = id_map.get(source_id, {})
    tgt_entity = id_map.get(target_id, {})

    src_phone = src_entity.get("number", "")
    tgt_phone = tgt_entity.get("number", "")

    props = {}
    if rel.get("timestamp"):
        props["timestamp"] = rel["timestamp"]
    if rel.get("amount") is not None:
        props["amount"] = float(rel["amount"])
    if rel.get("transaction_id"):
        props["transaction_id"] = rel["transaction_id"]
    if rel.get("confidence") is not None:
        props["confidence"] = rel["confid
        ence"]
    if rel.get("evidence"):
        props["evidence"] = rel["evidence"]

    if src_phone and tgt_phone:
        ingest_relationship(
            source_phone=src_phone,
            target_phone=tgt_phone,
            rel_type="TRANSACTED_WITH",
            properties=props,
            source_doc=rel.get("source_doc", "UNKNOWN"),
        )
    else:
        # Fallback to direct entity link (e.g. Person -> Person)
        src_neo4j = src_entity.get("_neo4j_id", source_id)
        tgt_neo4j = tgt_entity.get("_neo4j_id", target_id)
        source_doc = rel.get("source_doc", "UNKNOWN")
        timestamp = rel.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        prop_parts = ["r.source_doc_id = $src", "r.timestamp = $ts"]
        params = {"src_id": src_neo4j, "tgt_id": tgt_neo4j, "src": source_doc, "ts": timestamp}
        if "amount" in props:
            prop_parts.append("r.amount = $amount")
            params["amount"] = props["amount"]
        if "transaction_id" in props:
            prop_parts.append("r.transaction_id = $tx_id")
            params["tx_id"] = props["transaction_id"]
        if "confidence" in props:
            prop_parts.append("r.confidence = $conf")
            params["conf"] = props["confidence"]
        if "evidence" in props:
            prop_parts.append("r.evidence = $evidence")
            params["evidence"] = props["evidence"]

        prop_set = ", ".join(prop_parts)
        cypher = f"""
        MATCH (p1 {{id: $src_id}}), (p2 {{id: $tgt_id}})
        MERGE (p1)-[r:TRANSACTED_WITH]->(p2)
        SET {prop_set}
        """
        db.query(cypher, params)


def ingest_rel_controls_wallet(rel: dict, id_map: dict):
    """Handles CONTROLS_WALLET: Person → CryptoWallet."""
    source_doc = rel.get("source_doc", "UNKNOWN")
    timestamp = rel.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    person_neo4j_id = id_map.get(rel["source"], {}).get("_neo4j_id", rel["source"])
    wallet_neo4j_id = id_map.get(rel["target"], {}).get("_neo4j_id", rel["target"])

    prop_parts = ["r.source_doc_id = $src", "r.timestamp = $ts"]
    params = {"pid": person_neo4j_id, "wid": wallet_neo4j_id, "src": source_doc, "ts": timestamp}

    if rel.get("confidence") is not None:
        prop_parts.append("r.confidence = $conf")
        params["conf"] = rel["confidence"]
    if rel.get("evidence"):
        prop_parts.append("r.evidence = $evidence")
        params["evidence"] = rel["evidence"]

    prop_set = ", ".join(prop_parts)
    cypher = f"""
    MATCH (p:Person {{id: $pid}}), (cw:CryptoWallet {{id: $wid}})
    MERGE (p)-[r:CONTROLS_WALLET]->(cw)
    SET {prop_set}
    """
    db.query(cypher, params)


def ingest_rel_transferred_funds(rel: dict, id_map: dict):
    """Handles TRANSFERRED_FUNDS: CryptoWallet → CryptoWallet (or Person/Entity via wallets)."""
    source_doc = rel.get("source_doc", "UNKNOWN")
    timestamp = rel.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    src_id = id_map.get(rel["source"], {}).get("_neo4j_id", rel["source"])
    tgt_id = id_map.get(rel["target"], {}).get("_neo4j_id", rel["target"])

    prop_parts = ["r.source_doc_id = $src", "r.timestamp = $ts"]
    params = {"src_id": src_id, "tgt_id": tgt_id, "src": source_doc, "ts": timestamp}

    if rel.get("amount") is not None:
        prop_parts.append("r.amount = $amount")
        params["amount"] = float(rel["amount"])
    if rel.get("tx_hash"):
        prop_parts.append("r.tx_hash = $tx_hash")
        params["tx_hash"] = rel["tx_hash"]
    if rel.get("network"):
        prop_parts.append("r.network = $network")
        params["network"] = rel["network"]
    if rel.get("confidence") is not None:
        prop_parts.append("r.confidence = $conf")
        params["conf"] = rel["confidence"]
    if rel.get("evidence"):
        prop_parts.append("r.evidence = $evidence")
        params["evidence"] = rel["evidence"]

    prop_set = ", ".join(prop_parts)
    cypher = f"""
    MATCH (s {{id: $src_id}}), (t {{id: $tgt_id}})
    MERGE (s)-[r:TRANSFERRED_FUNDS]->(t)
    SET {prop_set}
    """
    db.query(cypher, params)


def ingest_rel_bound_to_imei(rel: dict, id_map: dict):
    """Handles BOUND_TO_IMEI: Phone → IMEI (detects SIM-box proliferation)."""
    source_doc = rel.get("source_doc", "UNKNOWN")
    timestamp = rel.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    phone_neo4j_id = id_map.get(rel["source"], {}).get("_neo4j_id", rel["source"])
    imei_neo4j_id = id_map.get(rel["target"], {}).get("_neo4j_id", rel["target"])

    prop_parts = ["r.source_doc_id = $src", "r.timestamp = $ts"]
    params = {"ph_id": phone_neo4j_id, "im_id": imei_neo4j_id, "src": source_doc, "ts": timestamp}

    if rel.get("confidence") is not None:
        prop_parts.append("r.confidence = $conf")
        params["conf"] = rel["confidence"]
    if rel.get("evidence"):
        prop_parts.append("r.evidence = $evidence")
        params["evidence"] = rel["evidence"]

    prop_set = ", ".join(prop_parts)
    cypher = f"""
    MATCH (ph:Phone {{id: $ph_id}}), (im:IMEI {{id: $im_id}})
    MERGE (ph)-[r:BOUND_TO_IMEI]->(im)
    SET {prop_set}
    """
    db.query(cypher, params)


def ingest_rel_accessed_via(rel: dict, id_map: dict):
    """Handles ACCESSED_VIA: Person or Phone → IPAddress."""
    source_doc = rel.get("source_doc", "UNKNOWN")
    timestamp = rel.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    src_id = id_map.get(rel["source"], {}).get("_neo4j_id", rel["source"])
    ip_neo4j_id = id_map.get(rel["target"], {}).get("_neo4j_id", rel["target"])

    prop_parts = ["r.source_doc_id = $src", "r.timestamp = $ts"]
    params = {"src_id": src_id, "ip_id": ip_neo4j_id, "src": source_doc, "ts": timestamp}

    if rel.get("service_accessed"):
        prop_parts.append("r.service_accessed = $service")
        params["service"] = rel["service_accessed"]
    if rel.get("confidence") is not None:
        prop_parts.append("r.confidence = $conf")
        params["conf"] = rel["confidence"]
    if rel.get("evidence"):
        prop_parts.append("r.evidence = $evidence")
        params["evidence"] = rel["evidence"]

    prop_set = ", ".join(prop_parts)
    cypher = f"""
    MATCH (s {{id: $src_id}}), (ip:IPAddress {{id: $ip_id}})
    MERGE (s)-[r:ACCESSED_VIA]->(ip)
    SET {prop_set}
    """
    db.query(cypher, params)


# Relationship handler dispatch table
_REL_HANDLERS = {
    "CALLED": ingest_rel_called,
    "MEMBER_OF": ingest_rel_member_of,
    "OWNS_PHONE": ingest_rel_owns_phone,
    "PRESENT_AT": ingest_rel_present_at,
    "OWNS_VEHICLE": ingest_rel_owns_vehicle,
    "TRANSACTED_WITH": ingest_rel_transacted_with,
    "CONTROLS_WALLET": ingest_rel_controls_wallet,
    "TRANSFERRED_FUNDS": ingest_rel_transferred_funds,
    "BOUND_TO_IMEI": ingest_rel_bound_to_imei,
    "ACCESSED_VIA": ingest_rel_accessed_via,
}


def ingest_nlp_payload(payload: dict) -> dict:
    """Top-level entry point: accepts Abhidha's NLP output contract and ingests everything.

    Expected payload shape (flat, multi-document):
    {
      "entities": [
        {"id": "P001", "type": "Person", "source_doc": "FIR_101", "name": "Manoj Tiwari", "aliases": []},
        {"id": "PH001", "type": "Phone", "source_doc": "FIR_101", "number": "9434567123"},
        {"id": "LOC001", "type": "Location", "source_doc": "FIR_101", "name": "Bidhannagar", ...},
        {"id": "VEH001", "type": "Vehicle", "source_doc": "FIR_101", "registration_number": "WB02CD5678", ...},
        {"id": "ORG001", "type": "Organization", "source_doc": "FIR_101", "name": "Shubh Laxmi Finance"},
        {"id": "CW001", "type": "CryptoWallet", "source_doc": "FIR_101", "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "currency": "BTC"},
        {"id": "IP001", "type": "IPAddress", "source_doc": "FIR_101", "ip": "185.220.101.5", "is_tor": true},
        {"id": "IM001", "type": "IMEI", "source_doc": "FIR_101", "imei": "860123456789012", "is_sim_box": true}
      ],
      "relationships": [
        {"source": "PH002", "target": "PH003", "type": "CALLED", "confidence": 0.95, ...},
        {"source": "P004", "target": "ORG001", "type": "MEMBER_OF", ...},
        {"source": "P001", "target": "CW001", "type": "CONTROLS_WALLET", ...}
      ]
    }

    Pipeline:
      1. Build entity ID → entity lookup map
      2. Ingest Person entities (with entity resolution)
      3. Ingest Phone, Location, Vehicle, Organization entities
      4. Ingest Cyber entities: CryptoWallet, IPAddress, IMEI
      5. Process all relationships via type-specific handlers
      6. Append-only cryptographic hash-chain audit logging under BSA §65B

    Returns a summary dict.
    """

    # ── 0. Validate Payload Schema & Referential Integrity ──
    validate_or_raise(payload)

    entities = payload.get("entities", [])
    relationships = payload.get("relationships", [])

    # ── Build ID → entity lookup ──
    id_map: dict[str, dict] = {}
    for entity in entities:
        id_map[entity["id"]] = entity

    # ── Split entities by type ──
    persons = [e for e in entities if e.get("type") == "Person"]
    phones = [e for e in entities if e.get("type") == "Phone"]
    locations = [e for e in entities if e.get("type") == "Location"]
    vehicles = [e for e in entities if e.get("type") == "Vehicle"]
    organizations = [e for e in entities if e.get("type") == "Organization"]
    wallets = [e for e in entities if e.get("type") == "CryptoWallet"]
    ips = [e for e in entities if e.get("type") == "IPAddress"]
    imeis = [e for e in entities if e.get("type") == "IMEI"]

    # ── 1. Ingest Person entities (with entity resolution) ──
    for person in persons:
        source_doc = person.get("source_doc", "UNKNOWN")
        resolved_id = ingest_suspect(person, source_doc)
        id_map[person["id"]]["_neo4j_id"] = resolved_id

    # ── 2. Ingest Phone entities ──
    for phone in phones:
        norm_phone = normalize_phone(phone.get("number", ""))
        phone_id = f"PH-{uuid.uuid4()}"
        cypher = """
        MERGE (ph:Phone {number: $norm})
        ON CREATE SET ph.id = $new_id, ph.normalized_number = $norm
        ON MATCH SET ph.normalized_number = COALESCE(ph.normalized_number, $norm)
        RETURN ph.id AS id
        """
        res = db.query(cypher, {"new_id": phone_id, "norm": norm_phone})
        actual_id = res[0]["id"] if res else phone_id
        id_map[phone["id"]]["_neo4j_id"] = actual_id

    # ── 3. Ingest Location entities ──
    for loc in locations:
        loc_id = ingest_location(
            name=loc.get("name", ""),
            source_doc=loc.get("source_doc", "UNKNOWN"),
            lat=loc.get("latitude"),
            lon=loc.get("longitude"),
        )
        id_map[loc["id"]]["_neo4j_id"] = loc_id

    # ── 4. Ingest Vehicle entities ──
    for veh in vehicles:
        veh_id = ingest_vehicle(
            registration_number=veh.get("registration_number", ""),
            vehicle_type=veh.get("vehicle_type"),
            source_doc=veh.get("source_doc", "UNKNOWN"),
        )
        id_map[veh["id"]]["_neo4j_id"] = veh_id

    # ── 5. Ingest Organization entities ──
    for org in organizations:
        org_id = ingest_organization(
            org=org,
            source_doc=org.get("source_doc", "UNKNOWN"),
        )
        id_map[org["id"]]["_neo4j_id"] = org_id

    # ── 6. Ingest Cybercrime & Blockchain Entities ──
    for wallet in wallets:
        cw_id = ingest_cryptowallet(
            wallet=wallet,
            source_doc=wallet.get("source_doc", "UNKNOWN"),
        )
        id_map[wallet["id"]]["_neo4j_id"] = cw_id

    for ip_item in ips:
        ip_id = ingest_ip_address(
            ip_entity=ip_item,
            source_doc=ip_item.get("source_doc", "UNKNOWN"),
        )
        id_map[ip_item["id"]]["_neo4j_id"] = ip_id

    for imei_item in imeis:
        im_id = ingest_imei(
            imei_entity=imei_item,
            source_doc=imei_item.get("source_doc", "UNKNOWN"),
        )
        id_map[imei_item["id"]]["_neo4j_id"] = im_id

    # ── 7. Process relationships ──
    rel_count = 0
    skipped = 0
    for rel in relationships:
        rel_type = rel.get("type", "")
        rel_data = rel if isinstance(rel, dict) else rel.dict()

        handler = _REL_HANDLERS.get(rel_type)
        if handler:
            try:
                handler(rel_data, id_map)
                rel_count += 1
            except Exception as e:
                print(f"[Ingestion Warning] Failed {rel_type} ({rel_data.get('source')} → {rel_data.get('target')}): {e}")
                skipped += 1
        else:
            print(f"[Ingestion Warning] Unknown relationship type: {rel_type}")
            skipped += 1

    # ── 8. Cryptographic Hash-Chain Audit Logging (Section 65B BSA) ──
    try:
        from backend.app.audit.audit_logger import audit_ledger
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()
        audit_ledger.log_event(
            user_id="INGESTION_ENGINE",
            badge_number="SYSTEM-AUTO",
            role="SYSTEM",
            action="INGEST_PAYLOAD",
            resource_type="GRAPH_PAYLOAD",
            resource_id=payload_hash[:16],
            details={
                "payload_sha256": payload_hash,
                "entities_count": len(entities),
                "relationships_count": rel_count,
                "cyber_entities": len(wallets) + len(ips) + len(imeis),
            },
        )
    except Exception as e:
        print(f"[Audit Warning] Could not record ingestion block: {e}")

    return {
        "persons_ingested": len(persons),
        "phones_ingested": len(phones),
        "locations_ingested": len(locations),
        "vehicles_ingested": len(vehicles),
        "organizations_ingested": len(organizations),
        "wallets_ingested": len(wallets),
        "ip_addresses_ingested": len(ips),
        "imeis_ingested": len(imeis),
        "relationships_ingested": rel_count,
        "relationships_skipped": skipped,
    }