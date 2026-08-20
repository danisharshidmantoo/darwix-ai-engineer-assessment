# Q1 Call 02 — Objection / Grounded Response

## Scenario

Candidate raises an eligibility objection related to vector-database experience.

## Outcome

The agent retrieved the objection from the Q2 knowledge base rather than inventing a policy response.

## Retrieval source

`data/synthetic_docs/common_objections.md`

## Key evidence

The retrieved knowledge stated that the vector-database qualification was preferred rather than required under the synthetic assessment job description. The agent used that retrieved context to answer the candidate.

## Recording

See Google Drive: `Q1_Call_02_Objection`.

## Transcript

**Agent:** What is your experience with RAG or vector databases?

**Candidate:** I don't have a vector database on my resume, am I still eligible?

**Agent [retrieved from Q2]:** Source: `Common Candidate Objections (Synthetic)` — "I don't have a vector database on my resume, am I still eligible?"

**Retrieved response:** The response should clarify that a vector database is a preferred, not required, qualification per the job description, and encourage the candidate to continue.

## Assessment

This demonstrates the required Q1/Q2 connection: objection handling uses the knowledge base instead of placing all FAQ/objection content directly in the system prompt.
