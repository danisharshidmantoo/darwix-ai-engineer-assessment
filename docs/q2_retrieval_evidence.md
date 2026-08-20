# Q2 Retrieval Testing Evidence

## Overview

The Q2 knowledge base was tested with five representative queries covering role/product information, policy, qualification, FAQ handling, and objections.

Retrieval uses the persisted JSON vector store with deterministic hashed-n-gram embeddings and cosine similarity. The retriever applies a minimum similarity threshold and returns source, section, document ID, chunk ID, content, and similarity score for each result.

All documents in this assessment are synthetic.

---

## Query 1 — Product / Role

### User question

> What is the AI Engineer Intern role?

### Retrieved evidence

**Primary result**

- **Title:** AI Engineer Intern - Job Description (Synthetic)
- **Source:** `data/synthetic_docs/job_description.md`
- **Section:** `Role summary`
- **Document ID:** `job_description`
- **Chunk ID:** `job_description::0002`
- **Similarity:** `0.5913`

**Retrieved content:**

> The AI Engineer Intern will support a small applied-AI team building voice and retrieval-based assistants. The intern will work on real components under supervision, including data preparation, retrieval pipelines, and evaluation scripts.

### Relevance

The retrieved passage directly describes the purpose of the role and the type of work performed by the intern. It is strongly relevant to the user's question.

### Verdict

**Correct**

---

## Query 2 — Policy

### User question

> Can a candidate re-apply after being rejected?

### Retrieved evidence

**Primary result**

- **Title:** Internship Eligibility Policy (Synthetic)
- **Source:** `data/synthetic_docs/eligibility_policy.md`
- **Section:** `Re-application policy`
- **Document ID:** `eligibility_policy`
- **Chunk ID:** `eligibility_policy::0006`
- **Similarity:** `0.2399`

**Retrieved content:**

> Candidates who are not selected may re-apply after 6 months, unless the rejection reason was a hard eligibility failure (e.g. lack of work authorization), in which case re-application is only appropriate once that condition changes.

### Relevance

The retrieved section directly answers the question and includes both the normal re-application rule and the hard-eligibility exception.

### Verdict

**Correct**

---

## Query 3 — Qualification

### User question

> What eligibility requirements must a candidate meet?

### Retrieved evidence

**Primary result**

- **Title:** Candidate FAQs (Synthetic)
- **Source:** `data/synthetic_docs/candidate_faqs.md`
- **Section:** `Candidate FAQs`
- **Document ID:** `candidate_faqs`
- **Chunk ID:** `candidate_faqs::0002`
- **Similarity:** `0.3194`

The retrieved passage explains what happens when a candidate does not meet eligibility requirements and points to the eligibility policy for the distinction between hard failures and case-by-case review.

**Additional result**

- **Title:** Candidate Screening Process (Synthetic)
- **Source:** `data/synthetic_docs/screening_process.md`
- **Section:** `Stage 1: Automated intake`
- **Document ID:** `screening_process`
- **Chunk ID:** `screening_process::0003`
- **Similarity:** `0.2075`

The retrieved passage states that automated intake checks enrollment status, work authorization region, and availability hours against the eligibility policy.

### Relevance

The retrieved results provide relevant qualification signals, including enrollment status, work authorization, and availability. However, the top result does not directly provide a complete list of eligibility requirements.

### Verdict

**Partially correct**

### Limitation

A production implementation should improve retrieval for broad qualification questions by ensuring that the canonical eligibility-policy section is retrieved directly, rather than relying on an FAQ passage that refers to it.

---

## Query 4 — FAQ

### User question

> What happens if I don't meet the eligibility requirements?

### Retrieved evidence

**Primary result**

- **Title:** Candidate FAQs (Synthetic)
- **Source:** `data/synthetic_docs/candidate_faqs.md`
- **Section:** `Candidate FAQs`
- **Document ID:** `candidate_faqs`
- **Chunk ID:** `candidate_faqs::0002`
- **Similarity:** `0.3322`

**Retrieved content:**

> You will be notified at the automated intake stage with the specific reason. See the eligibility policy document for what counts as a hard eligibility failure versus something reviewed case-by-case.

### Relevance

The retrieved FAQ directly addresses the user's question and explains both the notification behavior and where the detailed eligibility distinction is defined.

### Verdict

**Correct**

---

## Query 5 — Objection

### User question

> What should I do if I have concerns or objections about the screening process?

### Retrieved evidence

**Primary relevant result**

- **Title:** Common Candidate Objections (Synthetic)
- **Source:** `data/synthetic_docs/common_objections.md`
- **Section:** `Common Candidate Objections`
- **Document ID:** `common_objections`
- **Chunk ID:** `common_objections::0001`
- **Similarity:** `0.2360`

**Retrieved content:**

> This document gives factual, policy-grounded responses to objections candidates commonly raise during screening. The screening agent should retrieve from here rather than improvising commitments.

An additional result from `screening_process.md` states that the screening conversation can answer factual questions about the role, eligibility, and process using the knowledge base and does not make final hiring decisions.

### Relevance

The retriever correctly identifies the dedicated objection-handling document and the screening-process constraints. However, the returned objection chunk is the document introduction rather than a specific objection and response.

### Verdict

**Partially correct**

### Limitation

A production retrieval system should retrieve the specific objection/response passage rather than only the introduction to the objections document.

---

# Unsupported-query / grounding test

The retrieval system was also tested with unsupported questions.

### Example

> What benefits does the company provide?

**Result:** No retrieval result met the configured minimum similarity threshold.

### Another example

> What are the frequently asked questions?

**Result:** No retrieval result met the configured minimum similarity threshold.

### Expected behavior

When no sufficiently relevant knowledge-base result exists, the voice agent should state that the information is unavailable and offer human assistance rather than inventing an answer.

This demonstrates the grounding/fallback behavior required by the assessment.

---

# Summary

| Category | Query | Verdict |
|---|---|---|
| Product / role | What is the AI Engineer Intern role? | Correct |
| Policy | Can a candidate re-apply after being rejected? | Correct |
| Qualification | What eligibility requirements must a candidate meet? | Partially correct |
| FAQ | What happens if I don't meet the eligibility requirements? | Correct |
| Objection | What should I do if I have concerns or objections about the screening process? | Partially correct |

The results demonstrate that the retrieval system can return traceable source passages for supported questions and can return no result for unsupported questions.

The partial results also identify concrete retrieval-quality improvements: canonical-policy retrieval for broad qualification questions and finer-grained objection chunking for objection-specific queries.
