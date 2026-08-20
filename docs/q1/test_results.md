# Q1 Voice Agent — Test Results

## Overview

The Q1 voice agent was tested through the LiveKit voice interface against the required screening behaviors. The agent uses the Q2 knowledge base for factual role, eligibility, process, and objection questions and maintains explicit screening state for candidate details, conflicts, technical signals, and human escalation.

All assessment data is synthetic.

## Test Coverage

| Test | Expected behavior | Result | Verdict |
|---|---|---|---|
| Cooperative customer | Collect required screening fields and technical signals, then mark ready for human review | Required details collected and two technical answers recorded | PASS |
| Objection | Retrieve a grounded response from Q2 rather than improvise | Objection about vector-database experience was answered using `common_objections.md` | PASS |
| Incomplete details | Do not invent missing information; keep screening incomplete | Candidate stopped after enrollment; remaining fields stayed missing | PASS |
| Conflicting details | Detect conflicting values and request confirmation | Weekly availability changed 20 → 10 → 20; conflict was detected and resolved | PASS |
| Out-of-scope question | State that information is unavailable and avoid hallucination | Weather question received a safe screening-scope fallback | PASS |
| Human assistance | Escalate when the candidate requests a person | Human assistance request changed the flow to escalated state | PASS |

## Cooperative Call

The cooperative scenario completed the required qualification fields:

- enrollment status
- work authorization
- weekly availability
- preferred start date
- Python experience
- RAG/vector-database experience

Two role-relevant technical-signal answers were also recorded. The flow reached `ready_for_human_review` without making a final hiring decision.

**Recording:** Google Drive — `Q1_Call_01_Cooperative`

**Transcript:** `transcripts/call_01_cooperative.md`

## Objection Call

The candidate questioned whether lack of vector-database experience affected eligibility. The agent retrieved the objection from the Q2 knowledge base instead of hardcoding the response.

Source used:

`data/synthetic_docs/common_objections.md`

The response stated that vector-database experience was preferred rather than mandatory according to the synthetic job description, and encouraged the candidate to continue.

**Recording:** Google Drive — `Q1_Call_02_Objection`

**Transcript:** `transcripts/call_02_objection.md`

## Conflict + Escalation Call

The candidate first stated 20 hours/week, changed the answer to 10 hours/week, confirmed 10, then changed it again to 20. The agent detected the conflicting values and explicitly requested confirmation before proceeding.

The candidate subsequently requested a human recruiter and chose to stop. The agent recorded the escalation rather than continuing to force the screening flow.

**Recording:** Google Drive — `Q1_Call_03_Conflict_Escalation`

**Transcript:** `transcripts/call_03_conflict_escalation.md`

## Additional Grounding Tests

Offline Q1/Q2 testing also covered:

- unsupported/out-of-scope questions
- incomplete candidate responses
- conflicting candidate details
- human assistance requests
- grounded objection handling

When the retriever returns no sufficiently relevant result, the agent is instructed to state that the information is unavailable and offer human assistance.

## Safety / Reliability Behavior

The agent instructions explicitly prohibit:

- inventing factual answers
- making final hiring decisions
- approving exceptions
- promising outcomes
- claiming a technical or recording failure unless an actual tool error occurs
- asking for successfully recorded information again unless the state reports it as missing or conflicting

## Limitations

The recordings are browser/desktop test recordings rather than production telephone calls. The escalation implementation records a local escalation event; a production deployment would connect this event to a recruiter/CRM workflow or escalation webhook.

The Q1 technical questions are intended to collect technical signal, not make an automated hiring decision.
