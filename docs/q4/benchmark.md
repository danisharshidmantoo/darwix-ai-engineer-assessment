# Q4 — Real-Time Agent Assist Benchmark

## Overview

Q4 implements a deterministic streaming agent-assist pipeline:

Audio stream → Streaming ASR → Signal extraction → Nudge generation → Dashboard delivery

The implementation is designed to process transcript events incrementally and surface actionable customer signals to an agent-assist dashboard.

## Test Results

The Q4 test suite passes completely:

- 57 tests passed
- 0 failures

## Benchmark Configuration

The benchmark was executed with:

- 100 measured iterations
- 10 warm-up iterations
- local deterministic components
- transcript-to-signal
- signal-to-nudge
- nudge-to-dashboard
- end-to-end pipeline

## Results

| Stage | Mean | Median | P95 | Max |
|---|---:|---:|---:|---:|
| Transcript → Signal | 0.0142 ms | 0.0141 ms | 0.0147 ms | 0.0150 ms |
| Signal → Nudge | 0.00149 ms | 0.00150 ms | 0.00158 ms | 0.00175 ms |
| Nudge → Dashboard | 0.1121 ms | 0.1111 ms | 0.1165 ms | 0.1610 ms |
| End-to-End | 0.1247 ms | 0.1241 ms | 0.1286 ms | 0.1327 ms |

## Interpretation

The local deterministic processing pipeline completes in approximately 0.125 ms on average from transcript event through dashboard delivery.

The largest measured component is dashboard delivery, while signal extraction and nudge generation are comparatively small.

These measurements represent the local application pipeline only. They do not represent production network latency, external ASR latency, model inference latency, or browser rendering latency.

## Signal Detection

The signal extractor currently supports:

- CUSTOMER_CONFUSION
- CUSTOMER_HESITATION
- PAYMENT_CONCERN
- OBJECTION
- HUMAN_ASSISTANCE_REQUEST
- PURCHASE_INTENT

Signals are generated only from customer transcript events.

## Nudge Prioritization

Nudges are prioritized according to signal urgency.

Human assistance requests receive the highest priority, followed by payment concerns and objections.

Nudge generation also includes cooldown/suppression behavior and basic PII redaction.

## Evidence

The benchmark was executed locally from the repository using the Q4 benchmark module.

The final repository test result was:

`57 passed in 0.15s`
