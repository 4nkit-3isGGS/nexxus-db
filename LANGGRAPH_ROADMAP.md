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

- [ ] **Phase 1: Tool Contracts & Service Boundary (Morning Day 1)**
  - [ ] Define Python tool functions wrapping existing FastAPI graph services (`get_entity`, `get_neighbors`, `get_subgraph`, `get_shortest_path`, `search_entities`).
  - [ ] Implement mock/stub for Arnish's Risk Analytics contract (`get_risk_score`, `get_centrality`, `get_communities`).
  - [ ] Implement Evidence Verification tools (`get_evidence`, `verify_evidence_integrity`).
  - [ ] Add tool unit tests verifying strict input validation and bounded query limits (e.g. depth $\le 3$).

- [ ] **Phase 2: Investigation State & Supervisor Core (Afternoon Day 1)**
  - [ ] Define `InvestigationState` TypedDict with typed schemas (plans, hypotheses, evidence items, iteration counter, tool history).
  - [ ] Implement `Supervisor Agent` node with planning prompts (analyzes user query, resolves target person, generates 3-5 step plan).
  - [ ] Implement agent routing logic / state transition dispatcher.

- [ ] **Phase 3: Specialized Worker Nodes (Evening Day 1)**
  - [ ] Implement `Graph Investigator` agent node.
  - [ ] Implement `Evidence Investigator` agent node.
  - [ ] Implement `Risk Analyst` agent node.
  - [ ] Verify state accumulation (entities, connections, and evidence stored in `InvestigationState`).

---

### 📅 Day 2: Reasoning, Verification Loop & End-to-End Delivery

- [ ] **Phase 4: Analysis & Hypothesis Engine (Morning Day 2)**
  - [ ] Implement `Analysis Agent` node that correlates graph + risk + evidence into structured hypotheses (`SUPPORTED`, `WEAK`, `REJECTED`).
  - [ ] Test bridge suspect scenario (e.g., detecting if a subject acts as a cut-out or connector between distinct communities).

- [ ] **Phase 5: Critic / Verifier & Conditional Loop (Afternoon Day 2)**
  - [ ] Implement `Critic / Verifier` agent node (evaluates evidentiary support, checks for single-source bias, verifies hash provenance).
  - [ ] Add conditional LangGraph edge:
    - If evidence is weak and `iteration < MAX_ITERATIONS` $\rightarrow$ Route back to `Supervisor` to re-plan.
    - If evidence is sufficient or budget exhausted $\rightarrow$ Route to `Report Agent`.
  - [ ] Implement iteration guardrail (`MAX_ITERATIONS = 6`).

- [ ] **Phase 6: Report Generation & API Exposure (Evening Day 2)**
  - [ ] Implement `Report Agent` node (formats grounded intelligence dossier with timeline, confidence scores, and source citations).
  - [ ] Expose FastAPI endpoint `POST /api/investigate` for Bishal & Jayanta's frontend UI.
  - [ ] Run full end-to-end integration test with mock and live graph scenarios.

---

## 🛡️ Non-Negotiable Guardrails (From PDF)
1. **No Unrestricted Cypher:** LLMs never generate raw Cypher against Neo4j. All graph access is mediated via parameterized tools.
2. **Deterministic vs. Agentic Separation:** Graph queries, SHA-256 hash checks, and math run as deterministic Python tools; LLMs only perform decision-making and synthesis.
3. **Loop Bound:** Hard ceiling on investigation cycles to prevent infinite autonomous loops.
4. **Auditability:** Complete tool invocation log preserved in state for investigator inspection.
