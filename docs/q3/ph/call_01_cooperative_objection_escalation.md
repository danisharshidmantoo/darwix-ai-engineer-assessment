# Philippines Call 1 — Cooperative Customer, Objection, Unsupported Query & Escalation

## Scenario

A cooperative bancassurance customer completes the qualification flow and raises:
- a policy coverage question,
- an affordability concern,
- an out-of-scope question about employee salary,
- and a request to speak with a human representative.

## Localization demonstrated

- Filipino/Tagalog
- English
- Natural Taglish
- Polite use of "po"
- Local insurance terminology such as policy, premium, coverage, sum assured, payment mode, and Financial Advisor.

## Key test cases

### 1. Cooperative qualification

The customer provides:
- Age: 25
- Philippines residency: Yes
- Government-issued ID: Yes
- Partner-bank account: Yes
- Pre-existing conditions / long-term medication: No

### 2. Coverage question

Customer asks whether the policy provides coverage.

The agent does not invent coverage details and states that the available information does not contain the required coverage details. It offers assistance from a Financial Advisor.

**Result:** Safe fallback.

### 3. Affordability objection

Customer states:

> "I am worried that I won't be able to afford it every month."

The agent acknowledges the concern and discusses available payment options and plan tiers.

**Result:** Objection handled in the customer's language/register.

### 4. Out-of-scope question

Customer asks about employee salaries at Darwix.

The agent states that it does not have access to internal employee salary information and returns to the bancassurance flow.

**Result:** Out-of-scope information is not fabricated.

### 5. Human escalation

Customer requests to speak with a human representative.

The agent routes the request to the Financial Advisor.

**Result:** Human escalation demonstrated.

## Recording

The corresponding recording is stored in the submitted Google Drive folder.

Recording label:

**Q3 Philippines — Call 1**

## Assessment

This call demonstrates cooperative qualification, localized Taglish interaction, objection handling, safe unsupported-question behavior, and human escalation.
