# Ankit --- Criminal Network Intelligence System

## Complete Neo4j / Knowledge Graph Role & Implementation Plan

**Project:** AI Crime Knowledge Graph & Agentic Investigation Platform\
**Role:** Graph Database / Knowledge Graph Master\
**Stack:** Neo4j Community Edition, Cypher, Python, FastAPI

------------------------------------------------------------------------

## 1. Mission

Own the **Knowledge Graph layer** of the Criminal Network Intelligence
System.

Your layer converts structured entities and relationships from the Data
& NLP pipeline into a clean, deduplicated, queryable Neo4j graph.

Pipeline:

`Abhidha (NLP) → Ankit (Neo4j + Entity Resolution) → Arnish (Risk/Analytics) → Bishal & Jayanta (LangGraph/FastAPI/UI)`

The team plan assigns you: - Neo4j schema and ingestion - Entity
resolution / deduplication - Cypher query layer - CRUD/API endpoints for
the NLP pipeline

------------------------------------------------------------------------

## 2. Your Workstreams

### A. Graph Data Model

Design and document: - Node labels - Relationship types - Node
properties - Relationship properties - Stable IDs -
Evidence/provenance - Timestamps - Confidence values - Constraints and
indexes

### B. Neo4j Database

Build: - Local Neo4j setup - Database initialization - Schema creation -
Constraints - Indexes - Seed/sample data - Reset/cleanup scripts -
Health checks

### C. Entity Resolution

Prevent duplicate entities.

Example:

`Rahul Sharma`, `R. Sharma`, `Rahul S.`, and `Rahul Kumar Sharma` may
refer to one person.

Pipeline:

`Normalization → Exact match → Alias match → Fuzzy match → Supporting attributes → Confidence → AUTO-MERGE / REVIEW / CREATE`

The team plan specifically calls for normalization and fuzzy matching
such as Levenshtein/Jaro-Winkler.

### D. Graph Ingestion

Accept Abhidha's JSON and: 1. Validate it 2. Normalize entities 3.
Resolve duplicates 4. Create/update nodes 5. Create/update relationships
6. Preserve source-document metadata 7. Preserve timestamps 8. Preserve
extraction confidence

### E. Cypher Query Layer

Implement reusable queries for: - Entity lookup - Direct neighbors -
Multi-hop traversal - Relationship inspection - Shortest paths - Shared
locations - Shared identifiers where supported - Cross-case
connections - Subgraph retrieval - Evidence retrieval

### F. FastAPI Integration

Expose graph operations for the rest of the team.

The team plan mentions: - `/api/fir` - `/api/cdr` - `/api/entity/{id}` -
`/api/graph` - `/api/risk`

Coordinate the exact final API contract with Bishal/Jayanta.

------------------------------------------------------------------------

## 3. Baseline Graph Schema

The team PDF explicitly specifies these node labels:

-   `Person`
-   `Phone`
-   `Location`
-   `Organization`
-   `Vehicle`

And these relationship types:

-   `CALLED`
-   `TRANSACTED_WITH`
-   `PRESENT_AT`
-   `OWNS_VEHICLE`
-   `MEMBER_OF`

Implement this baseline first.

Do not add large numbers of extra node/relationship types until the real
synthetic data proves they are needed.

------------------------------------------------------------------------

## 4. Recommended V1 Node Properties

These are engineering recommendations built around the team schema; they
are not all explicitly specified in the PDF.

### Person

``` text
id
name
normalized_name
aliases
created_at
updated_at
```

### Phone

``` text
id
number
normalized_number
```

### Location

``` text
id
name
normalized_name
latitude
longitude
```

### Vehicle

``` text
id
registration_number
vehicle_type
```

### Organization

``` text
id
name
normalized_name
```

------------------------------------------------------------------------

## 5. Recommended V1 Relationship Properties

### CALLED

`(Person)-[:CALLED]->(Person)`

Properties:

``` text
timestamp
duration
confidence
source_doc
```

### TRANSACTED_WITH

`(Person)-[:TRANSACTED_WITH]->(Person)`

Properties:

``` text
timestamp
amount
transaction_id
confidence
source_doc
```

### PRESENT_AT

`(Person)-[:PRESENT_AT]->(Location)`

Properties:

``` text
timestamp
confidence
source_doc
```

### OWNS_VEHICLE

`(Person)-[:OWNS_VEHICLE]->(Vehicle)`

Properties:

``` text
confidence
source_doc
timestamp
```

### MEMBER_OF

`(Person)-[:MEMBER_OF]->(Organization)`

Properties:

``` text
role
confidence
source_doc
timestamp
```

------------------------------------------------------------------------

## 6. Evidence & Provenance

The graph must be able to answer:

> Why does the system believe this relationship exists?

Preserve, where available:

-   Source document ID
-   Source type
-   Timestamp
-   Confidence
-   Original evidence text/span
-   Record ID

This is important because the team's UI specification includes an
evidence drawer showing source FIR ID, timestamps and confidence.

------------------------------------------------------------------------

## 7. Contract With Abhidha

**Do not wait for Abhidha to finish.**

Design the schema and JSON contract now, then have both sides develop
against it.

The team PDF gives this baseline:

``` json
{
  "entities": [
    {
      "id": "P001",
      "name": "Rahul Sharma",
      "type": "PERSON"
    }
  ],
  "relationships": [
    {
      "source": "P001",
      "type": "CALLED",
      "target": "P002",
      "confidence": 0.94,
      "doc_id": "FIR_102"
    }
  ]
}
```

Recommended V1 extension:

``` json
{
  "entities": [
    {
      "id": "P001",
      "name": "Rahul Sharma",
      "type": "PERSON",
      "aliases": ["R. Sharma"],
      "source_doc": "FIR_102"
    }
  ],
  "relationships": [
    {
      "source": "P001",
      "type": "CALLED",
      "target": "P002",
      "confidence": 0.94,
      "doc_id": "FIR_102",
      "timestamp": "2026-08-20T14:32:00",
      "evidence": "..."
    }
  ]
}
```

The exact final contract should be agreed with Abhidha and the backend
team.

------------------------------------------------------------------------

## 8. Entity Resolution Architecture

``` text
Raw Entity
    ↓
Normalization
    ↓
Exact Identifier Match
    ↓
Alias Match
    ↓
Fuzzy Match
    ↓
Supporting Attribute Comparison
    ↓
Confidence Score
    ↓
┌──────────────┬──────────────┬──────────────┐
│ High         │ Medium       │ Low          │
│ AUTO-MERGE   │ REVIEW       │ CREATE NEW   │
└──────────────┴──────────────┴──────────────┘
```

Potential signals: - Normalized name - Phone number - Vehicle
registration - Organization - Location - Aliases - Other identifiers
present in the synthetic dataset

Never merge solely because two names look similar.

------------------------------------------------------------------------

## 9. Neo4j Constraints & Indexes

Create uniqueness constraints for stable IDs.

Example:

``` cypher
CREATE CONSTRAINT person_id_unique IF NOT EXISTS
FOR (p:Person)
REQUIRE p.id IS UNIQUE;
```

Consider equivalent constraints for Phone, Location, Vehicle and
Organization.

Add indexes for fields used frequently in lookups, such as normalized
names and phone numbers.

------------------------------------------------------------------------

## 10. Core Cypher Queries

### Get entity

``` cypher
MATCH (p:Person {id: $person_id})
RETURN p;
```

### Direct neighbors

``` cypher
MATCH (p:Person {id: $person_id})-[r]-(other)
RETURN p, r, other;
```

### Multi-hop network

``` cypher
MATCH path =
  (p:Person {id: $person_id})-[*1..3]-(other)
RETURN path;
```

### People sharing a location

``` cypher
MATCH (p:Person {id: $person_id})-[:PRESENT_AT]->(l:Location)
MATCH (other:Person)-[:PRESENT_AT]->(l)
RETURN l, other;
```

### Transactions

``` cypher
MATCH (a:Person)-[r:TRANSACTED_WITH]->(b:Person)
RETURN a, r, b;
```

All application queries should use parameters rather than
string-concatenating user values into Cypher.

------------------------------------------------------------------------

## 11. What Arnish Needs From You

Arnish owns: - Degree centrality - PageRank - Betweenness centrality -
Community detection - Anomaly detection - Risk scoring

Your responsibility is to make the graph data available for those
computations.

Provide: - Nodes - Edges - IDs - Relationship types - Relevant weights -
Timestamps - Metadata

Do not duplicate Arnish's algorithmic work unless the team explicitly
asks.

------------------------------------------------------------------------

## 12. FastAPI Layer

Proposed V1 endpoints:

``` text
POST /api/graph/entities
POST /api/graph/relationships
POST /api/graph/ingest

GET /api/entity/{id}
GET /api/entity/{id}/neighbors
GET /api/entity/{id}/subgraph

GET /api/graph/path
GET /api/graph/search
GET /api/graph/stats
```

These are proposed engineering endpoints. The final routes must be
coordinated with the team.

------------------------------------------------------------------------

## 13. Suggested Project Structure

``` text
criminal-network-intelligence/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── entity_routes.py
│   │   │   ├── graph_routes.py
│   │   │   ├── ingestion_routes.py
│   │   │   └── health_routes.py
│   │   ├── neo4j/
│   │   │   ├── driver.py
│   │   │   ├── schema.py
│   │   │   ├── constraints.py
│   │   │   └── queries.py
│   │   ├── ingestion/
│   │   │   ├── validator.py
│   │   │   ├── normalizer.py
│   │   │   ├── entity_resolver.py
│   │   │   └── graph_ingestor.py
│   │   ├── models/
│   │   │   ├── entities.py
│   │   │   └── relationships.py
│   │   └── services/
│   │       └── graph_service.py
│   ├── tests/
│   │   ├── test_entity_resolution.py
│   │   ├── test_ingestion.py
│   │   └── test_graph_queries.py
│   └── requirements.txt
├── data/
│   └── sample/
├── cypher/
│   ├── schema.cypher
│   ├── seed.cypher
│   └── queries.cypher
└── docs/
    └── graph-schema.md
```

This structure is a proposed implementation structure, not a requirement
from the team PDF.

------------------------------------------------------------------------

## 14. Learning Roadmap

### Level 1 --- Neo4j fundamentals

Learn: - Node - Relationship - Property - Label - Direction - Pattern
matching

### Level 2 --- Cypher

Learn: - CREATE - MATCH - MERGE - RETURN - WHERE - WITH - OPTIONAL
MATCH - DELETE - SET - REMOVE - UNWIND

### Level 3 --- Database engineering

Learn: - Constraints - Indexes - Transactions - Parameterized queries -
Python Neo4j driver

### Level 4 --- Graph data modeling

Learn: - Entity modeling - Relationship modeling - Normalization -
Provenance

### Level 5 --- Entity resolution

Learn: - Exact matching - Alias matching - Levenshtein distance -
Jaro-Winkler similarity - Confidence thresholds

### Level 6 --- Integration

Learn: - FastAPI - Pydantic - Neo4j Python driver - REST/JSON contracts

------------------------------------------------------------------------

# 15. 8-Day Sprint

## Days 1--2: Research, Specs & Setup

Your tasks: - Install Neo4j - Learn basic Cypher - Create local
database - Design V1 schema - Create constraints/indexes - Create sample
graph - Define JSON contract with Abhidha - Define API requirements with
Bishal/Jayanta

**Deliverable:** Working Neo4j database containing synthetic
criminal-network data.

## Days 3--5: Core Intelligence Pipeline

Your tasks: - Connect Abhidha's NER output - Validate payloads -
Normalize entities - Implement entity resolution - Implement Neo4j
ingestion - Implement graph queries - Test deduplication - Provide graph
extraction to Arnish

**Deliverable:** NLP JSON → entity resolution → Neo4j → graph queries.

## Days 6--8: Agentic Integration & Demo

Your tasks: - Stabilize APIs - Support LangGraph query requirements -
Optimize important queries - Support subgraph retrieval - Preserve
evidence/provenance - Fix integration bugs - Test investigation
scenarios

**Deliverable:** Natural-language investigation → LangGraph → Cypher →
Neo4j → risk/evidence → UI.

------------------------------------------------------------------------

# 16. Definition of Done

Your role is complete when another teammate can send:

``` json
{
  "entities": [...],
  "relationships": [...]
}
```

and your system can:

1.  Validate the payload
2.  Normalize entities
3.  Resolve duplicates
4.  Create/update Neo4j nodes
5.  Create/update relationships
6.  Preserve provenance
7.  Query the graph
8.  Return useful subgraphs
9.  Support multi-hop traversal
10. Provide data required by the risk engine
11. Provide data required by LangGraph agents
12. Expose agreed functionality through FastAPI

------------------------------------------------------------------------

# 17. Team Interfaces

### Abhidha → Ankit

She provides: - Entities - Relationships - Confidence - Source
document - Timestamps

You provide: - Validated graph representation - Resolved entity IDs -
Neo4j ingestion

### Ankit → Arnish

You provide: - Graph structure - Nodes - Edges - Subgraphs -
Timestamps - Relationship metadata

Arnish provides: - Centrality - Community detection - Anomaly signals -
Risk score

### Ankit → Bishal/Jayanta

You provide: - Graph APIs - Entity lookup - Subgraph retrieval -
Cypher-backed query services - Evidence/provenance

They provide: - LangGraph orchestration - Natural-language query
translation - UI integration

------------------------------------------------------------------------

# 18. What NOT To Do

Do not: - Wait for Abhidha to finish before designing the schema - Build
the whole system yourself - Put everything into one giant node - Allow
duplicate entities without resolution - Hard-code user-specific Cypher -
Expose database credentials to the frontend - Let the LLM execute
unrestricted Cypher - Remove evidence/provenance - Make risk scores
depend on unexplained LLM reasoning - Prematurely optimize before you
have working queries

------------------------------------------------------------------------

# 19. First Milestone

Before entity resolution or LangGraph, achieve:

``` text
Rahul Sharma
      │
      ├── CALLED ──────→ Sameer Khan
      ├── PRESENT_AT ──→ Delhi
      └── OWNS_VEHICLE → DL01AB1234
```

Then successfully query:

> Show everything connected to Rahul Sharma.

Once this works, proceed to:

**Schema → Ingestion → Entity Resolution → API → LangGraph Integration**

------------------------------------------------------------------------

# 20. Mental Model

``` text
             RAW AI EXTRACTION
                    │
                    ▼
           ┌─────────────────┐
           │ Entity Resolver │
           └────────┬────────┘
                    │
                    ▼
           ┌─────────────────┐
           │      NEO4J      │
           │ Criminal Graph  │
           └────────┬────────┘
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
       Queries   Analytics  Evidence
          │         │         │
          ▼         ▼         ▼
      LangGraph    Risk   Investigator
       Agents      Engine     UI
```

**Your role is the trusted structured graph layer underneath the agentic
system.**

------------------------------------------------------------------------

## Immediate Next Action

Do not start with LangGraph, React, complex graph algorithms, or
LLM-generated Cypher.

Start with:

1.  Install Neo4j
2.  Open Neo4j Browser
3.  Create a local database
4.  Learn nodes, relationships and properties
5.  Create 5--10 fictional nodes
6.  Connect them
7.  Run basic Cypher queries
8.  Design the V1 schema
9.  Send the JSON contract to Abhidha

Your first goal is:

> **"I can take fictional criminal-network data, store it in Neo4j, and
> query the relationships confidently."**
