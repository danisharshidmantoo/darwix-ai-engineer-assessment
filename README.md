# Darwix AI Engineer Assessment — Q1–Q4

## Overview

This repository contains the implementation for the Darwix AI Engineer assessment.

The project is organized into four major areas:

- **Q1 — Candidate Screening Voice Agent**
- **Q2 — Knowledge Base / Retrieval System**
- **Q3 — Localized Voice Bots**
  - Philippines
  - Indonesia
- **Q4 — Real-Time Streaming Nudges**

Q1 and Q2 are designed to work together: the voice agent retrieves answers about the role, eligibility, and process from the Q2 knowledge base instead of hardcoding FAQs or policy text into an LLM prompt.

> **All data in this repository is synthetic assessment data.**
>
> The documents in `data/synthetic_docs/` and the localized Q3 knowledge bases are created for this assessment only. They do **not** represent real Darwix policy, process, hiring criteria, financial policy, or production business rules.

---

# Q1 — Candidate Screening Voice Agent

## Use case

**Candidate screening for an AI Engineer Intern role.**

Q1 is a minimal LiveKit Python voice agent backed by the Q2 retriever.

The agent keeps explicit Python state for:

- enrollment status
- work authorization
- weekly availability
- availability start date
- Python experience
- RAG/vector-database experience
- role-relevant technical signals
- unresolved conflicts
- human-escalation requests

This is collection state only. The agent does not make a final hiring decision or approve exceptions.

## Architecture

```mermaid
flowchart LR
    Candidate["Candidate"]
    LiveKit["LiveKit AgentSession<br/>STT → LLM → TTS"]
    Flow["Q1 ScreeningFlow<br/>explicit candidate state"]
    Tool["Q1 Knowledge Tool"]
    Retriever["Q2 Retriever"]
    Store["JSON Vector Store"]
    Escalation["Local Escalation Event"]

    Candidate --> LiveKit
    LiveKit --> Flow
    LiveKit --> Tool
    Tool --> Retriever
    Retriever --> Store
    Retriever --> Tool
    Tool --> LiveKit
    Flow --> Escalation