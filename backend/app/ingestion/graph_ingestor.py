"""
Graph Ingestion Pipeline
------------------------
Receives structured JSON data (from NLP extraction of FIRs and CDRs),
runs Entity Resolution to deduplicate, and persists entities and
relationships into Neo4j.
"""

import uuid
from datetime import datetime, timezone

from backend.app.neo4j_driver import db
from backend.app.resolution.normalizer import normalize_name, normalize_phone
from backend.app.resolution.resolver import resolve_entity


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

def flag_for_review(id1: str, id2: str, confidence_score: float, reason: str):
    """Flags two potential duplicate entities for human review."""
    flagged_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cypher_query = """
    MATCH (p1:Person {id: $id1}), (p2:Person {id: $id2})
    MERGE (p1)-[r:POSSIBLE_DUPLICATE]->(p2)
    SET r.confidence_score = $confidence_score,
        r.reason = $reason,
        r.flagged_at = $flagged_at
    """

    db.query(cypher_query, {
        "id1": id1,
        "id2": id2,
        "flagged_at": flagged_at,
        "confidence_score": confidence_score,
        "reason": reason
    })

def ingest_phone(phone_number: str, person_id: str):
    """
    """
    norm_phone = normalize_phone(phone_number)

    cypher_query = """
    MATCH (p:Person {id: $person_id})
    MERGE (ph:Phone {number: $norm_phone})
    
    MERGE (p) - [r: OWNS_PHONE]->(ph)
    """

    db.query(cypher_query, {
        "person_id": person_id,
        "phone_number": phone_number,
        "norm_phone": norm_phone
    })

def ingest_relationship(
    source_phone: str,
    target_phone: str,
    rel_type: str,
    properties: dict,
    source_doc: str,
):
    """Creates a relationship between two Person nodes looked up by phone number.

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


    cypher_query = f"""
    MATCH (src:Person)-[:OWNS_PHONE]->(:Phone {{number: $src_phone}})
    MATCH (tgt:Person)-[:OWNS_PHONE]->(:Phone {{number: $tgt_phone}})
    MERGE (src)-[r:{rel_type}]->(tgt)
    SET r.source_doc_id = $source_doc{prop_set_clause}
    """

    params = {
        "src_phone": norm_src,
        "tgt_phone": norm_tgt,
        "source_doc": source_doc,
        **properties,       # spreads {"timestamp": "...", "duration_sec": 180} etc.
    }
    db.query(cypher_query, params)


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


def ingest_vehicle(registration_number: str, vehicle_type: str | None = None) -> str:
    """Creates or merges a Vehicle node by registration number. Returns the vehicle ID."""
    reg = registration_number.upper().replace(" ", "").replace("-", "")
    veh_id = f"VEH-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher_query = """
    MERGE (v:Vehicle {registration_number: $reg})
    ON CREATE SET v.id   = $id,
                  v.vehicle_type = $vtype,
                  v.created_at = $ts
    ON MATCH  SET v.updated_at = $ts
    RETURN v.id AS id
    """
    result = db.query(cypher_query, {
        "id": veh_id, "reg": reg, "vtype": vehicle_type, "ts": timestamp,
    })
    return result[0]["id"] if result else veh_id


def ingest_organization(name: str) -> str:
    """Creates or merges an Organization node. Returns the org ID."""
    from backend.app.resolution.normalizer import normalize_name as _nn

    norm = _nn(name)
    org_id = f"ORG-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cypher_query = """
    MERGE (o:Organization {normalized_name: $norm})
    ON CREATE SET o.id   = $id,
                  o.name = $name,
                  o.created_at = $ts
    ON MATCH  SET o.updated_at = $ts
    RETURN o.id AS id
    """
    result = db.query(cypher_query, {
        "id": org_id, "name": name, "norm": norm, "ts": timestamp,
    })
    return result[0]["id"] if result else org_id


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
    """Handles TRANSACTED_WITH: Person → Person (looked up via Phone IDs)."""
    src_entity = id_map.get(rel["source"], {})
    tgt_entity = id_map.get(rel["target"], {})

    src_phone = src_entity.get("number", "")
    tgt_phone = tgt_entity.get("number", "")

    if not src_phone or not tgt_phone:
        print(f"[Ingestion Warning] TRANSACTED_WITH: could not resolve phones for {rel['source']} → {rel['target']}")
        return

    props = {}
    if rel.get("timestamp"):
        props["timestamp"] = rel["timestamp"]
    if rel.get("amount") is not None:
        props["amount"] = rel["amount"]
    if rel.get("transaction_id"):
        props["transaction_id"] = rel["transaction_id"]
    if rel.get("confidence") is not None:
        props["confidence"] = rel["confidence"]
    if rel.get("evidence"):
        props["evidence"] = rel["evidence"]

    ingest_relationship(
        source_phone=src_phone,
        target_phone=tgt_phone,
        rel_type="TRANSACTED_WITH",
        properties=props,
        source_doc=rel.get("source_doc", "UNKNOWN"),
    )


# Relationship handler dispatch table
_REL_HANDLERS = {
    "CALLED": ingest_rel_called,
    "MEMBER_OF": ingest_rel_member_of,
    "OWNS_PHONE": ingest_rel_owns_phone,
    "PRESENT_AT": ingest_rel_present_at,
    "OWNS_VEHICLE": ingest_rel_owns_vehicle,
    "TRANSACTED_WITH": ingest_rel_transacted_with,
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
        {"id": "ORG001", "type": "Organization", "source_doc": "FIR_101", "name": "Shubh Laxmi Finance"}
      ],
      "relationships": [
        {"source": "PH002", "target": "PH003", "type": "CALLED", "confidence": 0.95, ...},
        {"source": "P004", "target": "ORG001", "type": "MEMBER_OF", ...}
      ]
    }

    Pipeline:
      1. Build entity ID → entity lookup map
      2. Ingest Person entities (with entity resolution)
      3. Ingest Phone, Location, Vehicle, Organization entities
      4. Process all relationships via type-specific handlers

    Returns a summary dict.
    """
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

    # ── 1. Ingest Person entities (with entity resolution) ──
    for person in persons:
        source_doc = person.get("source_doc", "UNKNOWN")
        resolved_id = ingest_suspect(person, source_doc)
        # Store the Neo4j ID back into id_map so relationship handlers can find it
        id_map[person["id"]]["_neo4j_id"] = resolved_id

    # ── 2. Ingest Phone entities ──
    for phone in phones:
        norm_phone = normalize_phone(phone.get("number", ""))
        cypher = """
        MERGE (ph:Phone {number: $norm})
        ON CREATE SET ph.id = $id
        """
        db.query(cypher, {"id": phone["id"], "norm": norm_phone})

    # ── 3. Ingest Location entities ──
    for loc in locations:
        loc_id = ingest_location(
            name=loc.get("name", ""),
            source_doc=loc.get("source_doc", "UNKNOWN"),
            lat=loc.get("latitude"),
            lon=loc.get("longitude"),
        )
        # Update id_map with the actual ID used in Neo4j
        id_map[loc["id"]]["_neo4j_id"] = loc_id

    # ── 4. Ingest Vehicle entities ──
    for veh in vehicles:
        veh_id = ingest_vehicle(
            registration_number=veh.get("registration_number", ""),
            vehicle_type=veh.get("vehicle_type"),
        )
        id_map[veh["id"]]["_neo4j_id"] = veh_id

    # ── 5. Ingest Organization entities ──
    for org in organizations:
        org_id = ingest_organization(name=org.get("name", ""))
        id_map[org["id"]]["_neo4j_id"] = org_id

    # ── 6. Process relationships ──
    rel_count = 0
    skipped = 0
    for rel in relationships:
        rel_type = rel.get("type", "")
        # Convert to dict if it's a Pydantic model
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

    return {
        "persons_ingested": len(persons),
        "phones_ingested": len(phones),
        "locations_ingested": len(locations),
        "vehicles_ingested": len(vehicles),
        "organizations_ingested": len(organizations),
        "relationships_ingested": rel_count,
        "relationships_skipped": skipped,
    }