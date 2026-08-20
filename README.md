# Darwix AI Engineer Assessment — Q1–Q4

> End-to-end AI systems for grounded voice interaction, production-oriented retrieval, multilingual voice agents, and real-time agent assistance.

## Overview

This repository contains my implementation for the **Darwix AI Engineer Assessment**.

The assessment focuses on building reliable AI systems from unstructured business data while addressing production-oriented concerns such as:

- grounded responses
- explicit business logic
- retrieval traceability
- multilingual and code-switched conversations
- safe fallbacks and escalation
- real-time signal detection
- actionable agent nudges
- latency measurement
- automated testing

The implementation covers all four assessment questions:

| Question | Solution | Primary Focus |
|---|---|---|
| **Q1** | Knowledge-Grounded Voice Agent | Voice interaction + qualification + RAG |
| **Q2** | Production-Ready Knowledge Base | Cleaning + chunking + embeddings + retrieval |
| **Q3** | Native-Language Voice Bots | Filipino/Taglish + Bahasa Indonesia |
| **Q4** | Real-Time Agent Assist | Streaming + signals + nudges + latency |

> **Assessment data is synthetic.** The documents and localized content in this repository are created specifically for the assessment and do not represent real Darwix policies, financial products, hiring criteria, or production business rules.

---

# System Architecture

The four questions form a broader AI application architecture.

```text
                         ┌──────────────────────────┐
                         │       User / Caller      │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │     Voice Interface      │
                         │   LiveKit / Voice Bots   │
                         └────────────┬─────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
          ┌──────────────────┐                ┌──────────────────┐
          │ Q1 Screening Flow│                │ Q3 Localization  │
          │ Qualification    │                │ PH / Indonesia   │
          └────────┬─────────┘                └──────────────────┘
                   │
                   │ knowledge queries
                   ▼
          ┌────────────────────────────┐
          │       Q2 Retrieval         │
          │                            │
          │ Cleaning → Chunking        │
          │ → Embeddings → Vector Store│
          │ → Retrieval / Ranking      │
          └────────────┬───────────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ Grounded Context │
              │ + Source Evidence│
              └──────────────────┘


              Real-Time Agent Assist — Q4

        Live Audio / Replay Stream
                    │
                    ▼
             Streaming ASR
                    │
                    ▼
          Transcript Chunks
                    │
                    ▼
            Signal Extraction
                    │
                    ▼
             Nudge Engine
                    │
                    ▼
          Dashboard / Delivery