# Next Milestone: Advanced Multi-Entity Resolution & Fraud Detection

## 🎯 Executive Summary
While our V1 pipeline successfully resolves and deduplicates **Person** entities (`AUTO_MERGE`, `FLAG_FOR_REVIEW`, `CREATE_NEW`), real-world criminal intelligence relies on multi-modal entity disambiguation and anomaly detection across **Organizations, Vehicles, and Locations**.

This document outlines:
1. **New Engine Features** to be added to the Knowledge Graph & Ingestion Layer.
2. **Action Items / Requests for Abhidha (NLP Extraction)**.
3. **Action Items / Requests for Arnish (Graph Analytics & Risk Engine)**.
4. **Action Items for Bishal & Jayanta (API & UI Integration)**.

---

## 🚀 Part 1: New Features for the Graph & Resolution Engine

### 1. Universal Duplicate Flagging (`flag_for_review`)
* **Current Limitation:** `flag_for_review` has a hardcoded `MATCH (p1:Person), (p2:Person)` query, meaning non-human entities cannot be flagged for investigator review.
* **Upgrade:** Generalize the query to be label-agnostic:
  ```cypher
  MATCH (e1 {id: $id1}), (e2 {id: $id2})
  MERGE (e1)-[r:POSSIBLE_DUPLICATE]->(e2)
  SET r.confidence_score = $confidence_score,
      r.reason = $reason,
      r.entity_type = labels(e1)[0],
      r.flagged_at = $flagged_at
  ```

### 2. Organization Entity Resolution (Shell Companies & Fronts)
* **Real-World Problem:** Hawala operators and criminal syndicates register shell firms under slight variants (*"Shubh Laxmi Finance"*, *"Shubh Laxmi Financial Services Pvt Ltd"*, *"Subh Laxmi Traders"*). A naive exact string match treats them as disconnected companies.
* **Upgrade:**
  * Clean legal suffixes during normalization (`Pvt Ltd`, `LLP`, `Inc`, `Co.`, `Enterprises`).
  * Run fuzzy token matching (Levenshtein & Token Sort Ratio).
  * If similarity $\ge 85\%$, flag them with a `[:POSSIBLE_DUPLICATE]` relationship holding match reasons for human verification.
  * If corporate registration IDs (GSTIN/CIN) match, execute `AUTO_MERGE`.

### 3. Cloned / Fake Vehicle Plate Detection (Attribute Conflict Engine)
* **Real-World Problem:** Stolen cars and smuggling rings use counterfeit or cloned license plates. If FIR 1 records `DL-01-AB-1234` as a *"Bajaj Pulsar (Motorcycle)"* and FIR 2 records `DL-01-AB-1234` as a *"White Scorpio (SUV)"*, blindly merging the node loses the fraud signal.
* **Upgrade:**
  * When ingesting a vehicle plate that already exists in Neo4j, check if the incoming `vehicle_type` conflicts with the stored `vehicle_type`.
  * If a conflict exists:
    * Mark `v.is_cloned_suspicious = true`.
    * Append conflict history to `v.attribute_conflicts = [...]`.
    * Tag the relationship with `has_vehicle_conflict = true`.

### 4. Location Disambiguation & Geo-Hierarchy
* **Real-World Problem:** Identical road names (*"MG Road"*, *"Station Road"*) exist across dozens of cities. Merging solely on name merges Delhi and Kolkata into one point. Conversely, *"Salt Lake"* and *"Salt Lake Sector V"* remain disconnected.
* **Upgrade:**
  * Hierarchical location linking: `(:Location {name: "Sector V"})-[:LOCATED_IN]->(:City {name: "Kolkata"})`.
  * Spatial proximity threshold: If coordinates (`latitude`, `longitude`) are provided, check Haversine distance ($< 500\text{m}$) before creating duplicate location nodes.

### 5. Human-in-the-Loop Review Queue & Merge APIs
* **Endpoint:** `GET /api/entities/review-queue`
  * Fetches all `[:POSSIBLE_DUPLICATE]` pairs across Person, Organization, and Location with match scores and evidence spans.
* **Endpoint:** `POST /api/entities/merge`
  * Allows investigators to approve a merge, consolidating properties, transferring edges to the target node, and deleting the duplicate node cleanly.

---

## 🤝 Part 2: Required Changes from Teammates

### 📦 For Abhidha (Person 1 — Data Extraction & NLP)

To support these advanced fraud and resolution features, we need the following slight enhancements in the NLP extraction payload:

1. **Vehicle Extraction Details:**
   * **Request:** Whenever a vehicle is extracted from an FIR, always attempt to extract both the `registration_number` AND the `vehicle_type` / `model` / `color` (e.g., `{"registration_number": "DL01AB1234", "vehicle_type": "Motorcycle", "color": "Black"}`).
   * **Why:** Enables our engine to automatically detect cloned number plates when the same plate appears with different vehicle types.

2. **Organization Identifiers & Legal Names:**
   * **Request:** If mentioned in bank statements or FIR text, extract tax/registration IDs (GSTIN, PAN, CIN) or trade aliases:
     `{"name": "Shubh Laxmi Finance", "tax_id": "07AAAAA0000A1Z5", "aliases": ["SLF Pvt Ltd"]}`.
   * **Why:** Allows deterministic auto-merging of shell companies regardless of spelling differences.

3. **Location Context (Parent City / District):**
   * **Request:** Avoid extracting bare street names like `"MG Road"` alone. Include the parent city or district if present in the document header or text (e.g., `{"name": "MG Road", "city": "Kolkata", "state": "West Bengal"}`).
   * **Why:** Prevents accidental merging of locations in different cities that share common street names.

---

### 📊 For Arnish (Person 3 — Graph Analytics & Risk Engine)

To reflect these new intelligence signals in risk scoring and graph algorithms:

1. **Incorporate Vehicle Anomaly Signals into Risk Scoring:**
   * **Request:** In `risk_engine.py`, check for `v.is_cloned_suspicious == True` on vehicles.
   * **Impact:** Any suspect who owns, drives, or is spotted in a vehicle with a cloned-plate flag should receive a major risk score boost (e.g., `+25` Risk Points: *"Associated with counterfeit/cloned vehicle registration"*).

2. **Handle `POSSIBLE_DUPLICATE` Edges in NetworkX:**
   * **Request:** When `neo4j_loader.py` loads edges into NetworkX:
     * Exclude `POSSIBLE_DUPLICATE` from physical criminal relationship traversals (it is an investigative review link, not a physical crime connection).
     * OR treat it as a "probabilistic bridge" during community detection with a reduced edge weight.

3. **Multi-Entity Community Detection:**
   * **Request:** Ensure Louvain / label propagation handles clusters that center around suspicious Organizations (e.g., a money-laundering hub where 5 suspects are all `MEMBER_OF` or `TRANSACTED_WITH` the same resolved shell firm).

---

### 🖥️ For Bishal & Jayanta (Person 4 — FastAPI & Frontend UI)

1. **Review Queue Dashboard Widget:**
   * Display a table/card feed of `GET /api/entities/review-queue` showing side-by-side comparisons of flagged duplicates with match confidence and source documents.
2. **Merge Confirmation Action:**
   * Add a one-click button: *"Approve Merge"* $\rightarrow$ calls `POST /api/entities/merge` to resolve ambiguities live during demonstrations.

---

## 📅 Implementation Checklist for Next Sprint

- [x] Update `flag_for_review()` in [graph_ingestor.py](file:///c:/Users/biswa/Desktop/nexxus-db/backend/app/ingestion/graph_ingestor.py) to remove the `:Person` label restriction.
- [x] Implement `resolve_organization()` in [backend/app/resolution/](file:///c:/Users/biswa/Desktop/nexxus-db/backend/app/resolution/) using token-based fuzzy matching.
- [x] Add vehicle attribute mismatch detection in `ingest_vehicle()`.
- [x] Add `GET /api/entities/review-queue` endpoint in [backend/app/api/entity_routes.py](file:///c:/Users/biswa/Desktop/nexxus-db/backend/app/api/entity_routes.py).
- [x] Add `POST /api/entities/merge` endpoint in [backend/app/api/entity_routes.py](file:///c:/Users/biswa/Desktop/nexxus-db/backend/app/api/entity_routes.py).
- [x] Test end-to-end ingestion of [output_contract.JSON](file:///c:/Users/biswa/Desktop/nexxus-db/output_contract.JSON) with the updated engine (47 passing tests).

---

## 🔮 Part 3: Upcoming Roadmap — Blockchain, Cybersecurity & LangGraph Integration

### 1. 🛡️ Blockchain & Cybersecurity (SIH26189 Track Fulfillment)
To defend our solution against SIH theme scrutiny without bloating the architecture:
* **Evidence Chain of Custody (Cryptographic Ledger):**
  * Generate a SHA-256 state hash for every incoming FIR, extracted entity set, and investigator merge decision (`AUTO_MERGE` or manual merge).
  * Persist the evidence hash and block timestamp onto graph nodes (`evidence_hash`, `ledger_tx_id`) compliant with legal admissibility (Section 65B of Bharatiya Sakshya Adhiniyam).
  * Local verifiable hash-chain / lightweight tamper-evident ledger verifying that graph data has not been modified after ingestion.
* **Cybercrime Graph Entities:**
  * Extend schema to include `CryptoWallet` (Bitcoin, USDT), `IPAddress`, and `IMEI` hardware nodes.
  * Connect telecommunication fraud (SIM boxes) $\rightarrow$ mule bank accounts $\rightarrow$ crypto cash-out trails.

### 2. 🤖 LangGraph Agentic Integration (With Bishal & Jayanta)
* **Agentic Graph Tools:**
  * Expose dedicated structured tools for the LangGraph agent (`lookup_suspect`, `expand_network`, `find_money_trail`, `get_shortest_connection`).
* **Text-to-Cypher / Safe Cypher Engine:**
  * Provide templated parameterized Cypher queries so the LLM agent avoids hallucinated or destructive graph operations.
* **Sub-graph Serialization for Agent Context:**
  * Return trimmed graph summaries that fit cleanly into LLM context windows for investigative report generation.

