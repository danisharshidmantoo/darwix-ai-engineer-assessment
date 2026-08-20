# Q3 Native-Language Voice Bots — Test Results

## Automated Tests

The Q3 implementation was tested across both localized voice-bot flows:

- Philippines
- Indonesia

Command:

    pytest -q tests/test_ph_*.py tests/test_id_*.py

Result:

    39 passed, 2 warnings in 2.07s

The two warnings are Pydantic warnings concerning the protected `model_` namespace and did not cause test failures.

## Coverage

### Philippines

- Localized knowledge-base retrieval
- English, Filipino/Tagalog, and Taglish handling
- Qualification flow
- Missing information
- Eligibility failures
- Conflicting information
- Conflict resolution
- Language-specific fallback
- Human escalation
- LiveKit tool execution
- Grounded knowledge-base responses

### Indonesia

- Localized knowledge-base retrieval
- Formal Indonesian
- Colloquial Indonesian
- Mixed English/Indonesian financial terminology
- Qualification flow
- Missing information
- Eligibility failures
- Conflicting information
- Conflict resolution
- Language-specific fallback
- Human escalation
- LiveKit tool execution
- Grounded knowledge-base responses

## Result

**39/39 Q3 automated tests passed.**

Automated tests demonstrate application-level behavior. Recorded-call evidence is documented separately for the required live voice scenarios.
