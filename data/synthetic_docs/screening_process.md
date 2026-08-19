---
doc_id: screening_process
doc_type: screening_process
title: Candidate Screening Process (Synthetic)
version: "1.0"
is_synthetic: true
---

> **SYNTHETIC ASSESSMENT DATA.** This document was invented for the Darwix
> AI Engineer Assessment. It does not represent an actual Darwix screening
> process.

# Candidate Screening Process

## Overview

Screening for the AI Engineer Intern role happens in three stages before
any human interview is scheduled. The goal of automated screening is to
confirm eligibility and collect structured information, not to make a
final hiring decision.

## Stage 1: Automated intake

- Candidate submits an application (resume + short answers).
- System checks basic eligibility flags (enrollment status, work
  authorization region, availability hours) against the eligibility
  policy.
- Candidates who fail a hard eligibility check are notified immediately
  with the specific reason.

## Stage 2: Screening conversation

- A structured conversation (voice or chat) collects:
  - Confirmation of eligibility details from Stage 1.
  - Availability start date and weekly hour commitment.
  - Self-reported experience level with Python, and with any RAG or
    vector database tools.
  - Answers to 2-3 role-relevant questions used for initial technical
    signal (not a full technical interview).
- The screening conversation follows a deterministic checklist — it does
  not improvise eligibility rules; it only retrieves and explains policy
  when asked.

## Stage 3: Human review

- A recruiter reviews the Stage 2 transcript and structured answers.
- Candidates who pass are scheduled for a technical interview with an
  engineer.
- Candidates who do not pass receive a templated rejection with a
  general reason category (not a detailed critique).

## What the screening conversation will and will not do

- It WILL answer factual questions about the role, eligibility, and
  process by retrieving from the knowledge base.
- It WILL collect the required structured fields listed above.
- It WILL NOT make a final hiring decision.
- It WILL NOT promise compensation, start dates, or outcomes beyond what
  is stated in policy documents.
