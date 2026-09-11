# CNIS LangGraph Investigation Layer — 2-Day Implementation Roadmap

**Objective:** Build an autonomous, hypothesis-driven criminal investigation engine powered by LangGraph, strictly calling Ankit's FastAPI Graph layer, Arnish's Risk service, and Cryptographic Evidence verification.

---

## 🧭 Multi-Agent Architecture Overview

```
                          [ Investigator Query ]
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Supervisor Agent   │◄──────────────┐
                         └──────────┬──────────┘               │
                                    │ Plan & Route             │
               ┌────────────────────┼────────────────────┐     │ Re-plan / Loop
               ▼                    ▼                    ▼     │ (if evidence weak)
       ┌───────────────┐    ┌───────────────┐    ┌───────────────┐│
       │  Graph Agent  │    │Evidence Agent │    │  Risk Agent   ││
       └───────┬───────┘    └───────┬───────┘    └───────┬───────┘│
               │                    │                    │        │
               │ Calls              │ Calls              │ Calls  │
               ▼                    ▼                    ▼        │
       ┌───────────────┐    ┌───────────────┐    ┌───────────────┐│
       │ FastAPI Graph │    │ Evidence API  │    │  Arnish Risk  ││
       │   Endpoints   │    │  (Hash / BSA) │    │   Analytics   ││
       └───────┬───────┘    └───────┬───────┘    └───────┬───────┘│
               └────────────────────┼────────────────────┘        │
                                    ▼                             │
                         ┌─────────────────────┐                  │
                         │   Analysis Agent    │                  │
                         │ (Hypothesis Engine) │                  │
                         └──────────┬──────────┘                  │
                                    ▼                             │
                         ┌─────────────────────┐                  │
                         │  Critic / Verifier  │──────────────────┘
                         └──────────┬──────────┘  Needs more evidence?
                                    │ YES (Sufficient & Verified)
                                    ▼
                         ┌─────────────────────┐
                         │    Report Agent     │
                         └──────────┬──────────┘
                                    ▼
                          [ Grounded Dossier ]
```

---

## ⏱️ 2-Day Sprint Plan & Progress Tracker

### 📅 Day 1: Foundations, State & Tool Boundary

- [x] **Phase 1: Tool Contracts & Service Boundary (Morning Day 1)**
  - [x] Define Python tool functions wrapping existing FastAPI graph services (`get_entity`, `get_neighbors`, `get_subgraph`, `get_shortest_path`, `search_entities`).
  - [x] Implement mock/stub for Arnish's Risk Analytics contract (`get_risk_score`, `get_centrality`, `get_communities`).
  - [x] Implement Evidence Verification tools (`get_evidence`, `verify_evidence_integrity`).
  - [x] Add tool unit tests verifying strict input validation and bounded query limits (e.g. depth $\le 3$).

- [x] **Phase 2: Investigation State & Supervisor Core (Afternoon Day 1)**
  - [x] Define `InvestigationState` TypedDict with typed schemas (`Hypothesis`, `ToolInvocation`, `InvestigationState`, `initial_state()`).
  - [x] Implement `Supervisor Agent` node with planning prompts (analyzes user query, resolves target person, generates 3-5 step plan).
  - [x] Implement agent routing logic / state transition dispatcher (`supervisor_evaluate_node`, `route_next_step`, `create_investigation_graph`).

- [x] **Phase 3: Specialized Worker Nodes (Evening Day 1)**
  - [x] Implement `Graph Investigator` agent node.
  - [x] Implement `Evidence Investigator` agent node.
  - [x] Implement `Risk Analyst` agent node.
  - [x] Implement `Financial & Cyber Analyst` agent node.
  - [x] Verify state accumulation (entities, connections, and evidence stored in `InvestigationState`).

---

### 📅 Day 2: Reasoning, Verification Loop & End-to-End Delivery

- [x] **Phase 4: Analysis & Hypothesis Engine (Morning Day 2)**
  - [x] Implement `Analysis Agent` node that correlates graph + risk + evidence into structured hypotheses (`SUPPORTED`, `WEAK`, `REJECTED`).
  - [x] Test bridge suspect scenario (e.g., detecting if a subject acts as a cut-out or connector between distinct communities).
  - [x] Test burner phone proliferation and financial layering / mule account detection.

- [x] **Phase 5: Critic / Verifier & Conditional Loop (Afternoon Day 2)**
  - [x] Implement `Critic / Verifier` agent node (evaluates evidentiary support, checks for single-source bias, verifies hash provenance).
  - [x] Add conditional LangGraph edge:
    - If evidence is weak and `iteration < MAX_ITERATIONS` $\rightarrow$ Route back to `Supervisor` to re-plan.
    - If evidence is sufficient or budget exhausted $\rightarrow$ Route to `Report Agent`.
  - [x] Implement iteration guardrail (`MAX_ITERATIONS = 10`).

- [x] **Phase 6: Report Generation & API Exposure (Evening Day 2)**
  - [x] Implement `Report Agent` node (formats grounded intelligence dossier with timeline, confidence scores, and source citations).
  - [x] Expose FastAPI endpoint `POST /api/investigate` for Bishal & Jayanta's frontend UI.
  - [x] Run full end-to-end integration test with mock and live graph scenarios (13/13 passing tests).

- [x] **Phase 7: Law Enforcement RBAC & Tamper-Evident Audit Logging (SIH PPT Requirement)**
  - [x] Multi-tier authorization matrix (`ADMIN`, `LEAD_INVESTIGATOR`, `INVESTIGATOR`, `ANALYST`, `AUDITOR`).
  - [x] Dynamic PII redaction (`Aadhaar`, `PAN`, `Phone`) preserving last 4 digits for field investigators and full masking for crime analysts.
  - [x] Section 65B Bharatiya Sakshya Adhiniyam (BSA) append-only SHA-256 cryptographic hash-chain ($H_n = \text{SHA-256}(H_{n-1} + \dots)$).
  - [x] Mathematical tampering and severed-link detection verification engine (`POST /api/audit/verify` and `GET /api/audit/logs`).

---

## 🛡️ Non-Negotiable Guardrails (From PDF)
1. **No Unrestricted Cypher:** LLMs never generate raw Cypher against Neo4j. All graph access is mediated via parameterized tools.
2. **Deterministic vs. Agentic Separation:** Graph queries, SHA-256 hash checks, and math run as deterministic Python tools; LLMs only perform decision-making and synthesis.
3. **Loop Bound:** Hard ceiling on investigation cycles to prevent infinite autonomous loops.
4. **Auditability:** Complete tool invocation log preserved in state for investigator inspection.
