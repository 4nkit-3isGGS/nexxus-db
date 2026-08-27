# Nexxus DB — AI Criminal Network Intelligence & Knowledge Graph Engine

> **Smart India Hackathon (SIH 2026)** | Problem Statement: **SIH26189**  
> **Topic:** *AI-Powered Criminal Network Analysis System*

---

## 📌 Overview

Law enforcement agencies frequently collect fragmented data across First Information Reports (FIRs), Call Detail Records (CDRs), financial transaction ledgers, surveillance notes, and intelligence dossiers. Manual correlation of suspects across these heterogeneous sources leads to missed connections, duplicate suspect identities, and delayed investigations.

**Nexxus DB** serves as the **Knowledge Graph & Entity Resolution Engine** of the system. It ingests structured entities and relationships from NLP pipelines, deduplicates criminal identities through multi-layered fuzzy matching, and persists a connected Neo4j knowledge graph ready for investigative graph analytics and multi-hop network queries.

---

## 🏗️ System Architecture & Pipeline

```
┌─────────────────┐       ┌──────────────────────────────┐       ┌──────────────────────┐       ┌─────────────────────┐
│  NLP Extraction │ ────> │ Nexxus DB (Neo4j & Engine)   │ ────> │ Risk Analytics Engine│ ────> │ Interactive Agent & │
│  (Abhidha)      │       │ - Normalization & Fuzzy Match│       │ (Arnish)             │       │ Investigation UI    │
│  - FIRs & CDRs  │       │ - Entity Resolution Engine   │       │ - Centrality Scoring │       │ (Bishal & Jayanta)  │
│  - Entity Spans │       │ - Graph Ingestion & Cypher   │       │ - Community Detection│       │ - LangGraph Copilot │
└─────────────────┘       └──────────────────────────────┘       └──────────────────────┘       └─────────────────────┘
```

---

## ⚡ Key Features

### 1. Multi-Layer Entity Resolution
- **Text Normalization:** Strips honorifics (e.g., *Mr., Shri, Dr.*), normalizes special characters, whitespace, and formats phone numbers to standard 10-digit formats.
- **Fuzzy Name Matching:** Leverages `RapidFuzz` (`token_sort_ratio`, token sets) to handle token inversions (e.g. *"Sharma Rahul"* vs *"Rahul Sharma"*), typos, and name additions.
- **Alias & Phone Resolution:** Evaluates aliases and hardware identifiers across records.
- **Decision Engine:** Evaluates confidence scores and classifies resolution into:
  - `AUTO_MERGE` ($\ge 0.85$ + supporting evidence or matching phone)
  - `FLAG_FOR_REVIEW` ($0.60 \le \text{Score} < 0.85$ or high name match without identifiers)
  - `CREATE_NEW` ($\text{Score} < 0.60$)

### 2. Neo4j Knowledge Graph Schema
- **Nodes:**
  - `Person`: Suspects, aliases, normalized names, and metadata.
  - `Phone`: Normalized numbers and hardware identifiers.
  - `Location`: Coordinates and geographical locations.
  - `Organization`: Syndicates, shell companies, and gangs.
  - `Vehicle`: Registration details and vehicle types.
- **Relationships:**
  - `CALLED`: Call duration, timestamps, and call frequency.
  - `TRANSACTED_WITH`: Financial transactions and amounts.
  - `PRESENT_AT`: Co-location and incident sightings.
  - `OWNS_VEHICLE` & `MEMBER_OF`: Organizational roles and affiliations.
- **Evidence & Provenance:** Every node and relationship retains `source_doc_id`, timestamps, and extraction confidence.

---

## 📁 Repository Structure

```text
nexxus-db/
├── backend/
│   ├── app/
│   │   ├── neo4j_driver.py       # Connection lifecycle & query execution
│   │   └── resolution/
│   │       ├── normalizer.py     # Name & phone standardization
│   │       ├── matcher.py        # Fuzzy similarity scoring via RapidFuzz
│   │       └── resolver.py       # Decision Engine (AUTO_MERGE / REVIEW / CREATE)
│   ├── tests/
│   │   ├── test_normalizer.py    # Unit tests for text normalizer
│   │   ├── test_matcher.py       # Unit tests for fuzzy matcher
│   │   └── test_resolver.py      # Unit tests for decision engine
│   └── requirements.txt          # Backend dependencies
├── cypher/
│   ├── schema.cypher             # Constraints & indexes
│   ├── seed.cypher               # Sample criminal network data
│   └── queries.cypher            # Reusable investigative traversals
├── pytest.ini                    # Test runner configuration
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- [Neo4j Desktop](https://neo4j.com/download/) or Neo4j Community Edition (v5+)

### 1. Clone & Setup Virtual Environment
```powershell
git clone https://github.com/4nkit-3isGGS/nexxus-db.git
cd nexxus-db

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # On Windows (PowerShell)
# source .venv/bin/activate    # On Linux/macOS
```

### 2. Install Dependencies
```powershell
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your Neo4j credentials:
```ini
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j
```

### 4. Run Test Suite
Verify that all unit tests and resolution engines pass:
```powershell
pytest -v
```

---

## 👥 Team
- **Ankit** — *Knowledge Graph & Entity Resolution Master*
- **Abhidha** — *Data Pipeline & NLP Extraction*
- **Arnish** — *Risk Modeling & Network Analytics*
- **Bishal** — *Agentic Architecture & Backend Integration*
- **Jayanta** — *Frontend & UI/UX Experience*
- **Tanushree** — *Intelligence & Validation*
