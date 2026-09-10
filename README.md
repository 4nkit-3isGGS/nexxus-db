# 🌐 Nexxus DB — AI-Powered Criminal Network Analysis System

> **Smart India Hackathon (SIH 2026)** | Problem Statement: **SIH26189**  
> **Topic:** *AI-Powered Criminal Network Analysis & Autonomous Multi-Agent Investigation Platform*

---

## 📌 1. Project Mission & Overview

Law enforcement agencies frequently collect fragmented data across First Information Reports (FIRs), Call Detail Records (CDRs), financial transaction ledgers, vehicle registrations, and intelligence dossiers. Traditional investigation methods struggle with:
- **Identity Obfuscation**: Criminals operating under multiple aliases, misspelled names, forged Aadhaar/PAN cards, and burner SIMs.
- **Layered Financial Trails**: Rapid smurfing and circular fund dispersal through shell organizations and mule accounts.
- **Disconnected Jurisdictions**: Crime incidents scattered across police stations without automated linkage.
- **Legal Admissibility Barriers**: Presenting digital evidence without an immutable chain of custody compliant with Indian law.

**Nexxus DB** is the core **Knowledge Graph, Entity Resolution & Multi-Agent Investigation Engine** designed to solve SIH26189. It fuses multi-source intelligence into an interconnected Neo4j graph, automatically resolves duplicate and fraudulent entities, computes mathematical risk profiles, and deploys autonomous **LangGraph multi-agent investigators** to uncover syndicates, money laundering loops, and court-admissible evidence trails.

---

## 🏗️ 2. End-to-End Pipeline & Team Roles

> **Abhidha (NLP)** ➔ **Ankit (Neo4j + Ingestion + Resolution)** ➔ **Arnish (Risk/Analytics)** ➔ **Bishal & Jayanta (LangGraph/UI)**

```
┌──────────────────────────────┐       ┌─────────────────────────────────────────────────┐
│   1. NLP Extraction Pipeline │ ────> │ 2. Nexxus DB Core (Ankit)                       │
│   (Abhidha)                  │       │    - Multi-Layer Entity Resolution Engine       │
│   - Unstructured FIRs & CDRs │       │    - Neo4j Knowledge Graph & Cypher Services    │
│   - JSON Entity Extractor    │       │    - Cloned Vehicle Plate Fraud Detection       │
└──────────────────────────────┘       │    - Investigator Review Queue & Merge APIs     │
                                       └───────────────────────┬─────────────────────────┘
                                                               │
                                                               ▼
┌──────────────────────────────┐       ┌─────────────────────────────────────────────────┐
│   4. Multi-Agent Platform    │ <──── │ 3. Risk & Graph Analytics Engine                │
│   (Bishal, Jayanta & Ankit)  │       │    (Arnish & Ankit)                             │
│   - LangGraph Investigation  │       │    - PageRank & Betweenness Centrality          │
│   - Supervisor & Workers     │       │    - Louvain Community / Syndicate Detection    │
│   - BSA §65B Hash Custody    │       │    - Circular Transaction & Call Burst Scans    │
└──────────────────────────────┘       └─────────────────────────────────────────────────┘
```

---

## ⚡ 3. Key Subsystems & Capabilities

### 🔍 A. Multi-Stage Entity Resolution & Fraud Engine (`backend/app/resolution/`)
- **Person Matching**: Token sort & token set fuzzy matching via `RapidFuzz`, alias matching, Aadhaar/PAN cross-referencing, and phone ownership linking.
- **Organization Matching**: Corporate suffix normalization (`Pvt Ltd`, `LLC`, `Corp`) with fuzzy title matching.
- **Vehicle Fraud & Cloned Plate Detection**: Automatically flags cloned license plate fraud when identical registration numbers appear with conflicting make/model/color attributes.
- **Automated Thresholds**:
  - `AUTO_MERGE` (Score ≥ 0.85): Automatically consolidated.
  - `REVIEW_QUEUE` (0.60 ≤ Score < 0.85): Flagged with `:POSSIBLE_DUPLICATE` for manual investigator review (`GET /api/entities/review-queue`, `POST /api/entities/merge`).
  - `CREATE_NEW` (Score < 0.60): Ingested as distinct individual.

### 📊 B. Integrated Graph Analytics Engine (`backend/app/analytics/`)
- **Centrality Metrics**: Computes **PageRank** (identifying influential kingpins) and **Betweenness Centrality** (identifying communication brokers/bridges connecting criminal cells).
- **Syndicate Community Detection**: Uses Louvain modularity to cluster suspects into operational gangs.
- **Forensic Anomaly Detection**:
  - *Circular Transactions*: Detects round-tripping money laundering loops (`A → B → C → A`).
  - *Call Bursts*: Flags burner SIM activity (≥ 10 calls/day around incident dates).
  - *Cross-Case Entities*: Detects repeat offenders appearing across multiple separate FIRs.

### 🤖 C. LangGraph Multi-Agent Investigation Engine (`backend/app/agents/`)
- **Shared Case Blackboard**: Centralized [`InvestigationState`](backend/app/agents/state.py) tracking discoveries, working hypotheses, evidence citations, and tool history.
- **12 Production Tool Boundaries** (`backend/app/agents/tools/`):
  - **Graph Tools (5)**: `get_entity`, `get_neighbors`, `get_subgraph` (strictly bounded depth ≤ 3), `get_shortest_path`, `search_entities`.
  - **Risk Tools (4)**: `get_risk_score`, `get_network_centrality`, `get_communities`, `detect_anomalies`.
  - **Evidence Tools (3)**: `get_evidence`, `verify_evidence_integrity`, `generate_evidence_hash`.
- **BSA §65B Cryptographic Evidence Custody**: Computes and audits SHA-256 cryptographic hashes for every evidence excerpt to guarantee legal admissibility in Indian courts under **Section 65B of the Bharatiya Sakshya Adhiniyam, 2023**.
- **Detailed Agent Specifications**: Full architectural documentation suite available in [`backend/app/agents/docs/`](backend/app/agents/docs/).

---

## 🗄️ 4. Knowledge Graph Schema

### Node Labels
- `:Person` (`id`, `name`, `normalized_name`, `aliases`, `aadhaar`, `pan`, `father_name`, `age`, `gender`, `risk_score`)
- `:Phone` (`id`, `number`, `carrier`, `imei`)
- `:Location` (`id`, `name`, `address`, `city`, `coordinates`, `location_type`)
- `:Organization` (`id`, `name`, `normalized_name`, `org_type`, `reg_number`)
- `:Vehicle` (`id`, `registration_number`, `make`, `model`, `color`, `vehicle_type`)
- `:CrimeIncident` / `:FIR` (`id`, `fir_number`, `incident_type`, `description`, `timestamp`, `ipc_sections`)
- *Planned Cyber Nodes*: `:CryptoWallet`, `:IPAddress`, `:IMEI`

### Relationship Types
- `:CALLED` (`duration`, `timestamp`, `tower_id`, `evidence_hash`)
- `:TRANSACTED_WITH` (`amount`, `timestamp`, `transaction_id`, `type`)
- `:PRESENT_AT` (`timestamp`, `confidence`)
- `:OWNS_VEHICLE`, `:ASSOCIATED_WITH`, `:INVOLVED_IN`, `:OPERATES_FROM`, `:OWNS_PHONE`, `:MEMBER_OF`
- `:POSSIBLE_DUPLICATE` (`confidence_score`, `reason`, `flagged_at`)

---

## 📁 5. Repository Structure

```text
nexxus-db/
├── backend/
│   ├── app/
│   │   ├── neo4j_driver.py           # Neo4j connection lifecycle & query pooling
│   │   ├── main.py                   # FastAPI application entrypoint
│   │   ├── api/                      # REST endpoints (entities, review-queue, merge)
│   │   ├── services/                 # Graph query service layer (Cypher wrappers)
│   │   ├── models/                   # Pydantic v2 schemas & request/response contracts
│   │   ├── ingestion/                # Graph ingestor & relationship builders
│   │   ├── resolution/               # Multi-stage entity resolution engine
│   │   ├── analytics/                # Arnish's Risk & Graph Analytics Engine
│   │   └── agents/                   # LangGraph Multi-Agent Investigation Platform
│   │       ├── state.py              # InvestigationState & Hypothesis TypedDict schemas
│   │       ├── tools/                # 12 Bounded, validated LangChain tools
│   │       │   ├── graph_tools.py    # Neo4j traversal tools (depth <= 3)
│   │       │   ├── risk_tools.py     # Centrality & anomaly detection tools
│   │       │   ├── evidence_tools.py # BSA §65B SHA-256 verification tools
│   │       │   └── __init__.py       # Exported tool registries
│   │       ├── nodes/                # Agent nodes (Supervisor, Investigator, Analyst)
│   │       └── docs/                 # Detailed 6-agent technical manuals
│   ├── tests/                        # 98 unit & integration tests
│   │   ├── test_agent_tools.py       # Full tool boundary & BSA 65B tests (27 tests)
│   │   ├── test_matcher.py           # RapidFuzz similarity tests
│   │   ├── test_normalizer.py        # Text & phone standardization tests
│   │   ├── test_resolver.py          # Auto-merge & review queue decision tests
│   │   ├── test_fraud_detection.py   # Cloned vehicle plate fraud tests
│   │   └── test_graph_queries.py     # Live Neo4j Cypher query tests
│   └── requirements.txt              # Production dependencies
├── cypher/
│   ├── schema.cypher                 # Constraints, indexes & uniqueness rules
│   ├── seed.cypher                   # Synthetic criminal network seed data
│   └── queries.cypher                # Pre-built investigative Cypher queries
├── LANGGRAPH_ROADMAP.md              # Multi-agent sprint roadmap & milestones
├── AGENTS.md                         # Project memory & developer guidelines
├── GEMINI.md                         # Workspace context & quick status
├── pytest.ini                        # Pytest runner configuration
└── README.md                         # Root project documentation
```

---

## 🚀 6. Getting Started

### Prerequisites
- Python 3.10+ (Recommended: Python 3.12)
- [Neo4j Desktop](https://neo4j.com/download/) or Neo4j Community Edition (v5+)

### 1. Setup Virtual Environment
```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the project root:
```ini
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
NEO4J_DATABASE=neo4j
GRAPH_DATA_SOURCE=neo4j  # or 'mock' for standalone offline mode
```

### 4. Run Test Suite
Execute the comprehensive test suite:
```powershell
pytest backend/tests -v
```
*(Currently: **98 passing unit tests**, with 12 live Neo4j tests safely skipped when the database container is offline).*

---

## 👥 7. Task Force Team (SIH 2026 — Team Nexxus)

- **Ankit (User)** — *Graph Database, Ingestion Engine, Entity Resolution & Multi-Agent Lead*
- **Abhidha** — *Data Pipeline, NLP & Information Extraction*
- **Arnish** — *Risk Analytics, Centrality Modeling & Community Detection*
- **Bishal** — *Agentic Architecture, UI Integration & LangGraph Copilot*
- **Jayanta** — *Investigation Workspace & Graph Visualization*
- **Tanushree** — *Intelligence Reporting & Legal Validation*
