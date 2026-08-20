# Q3 Localization Evidence

## Philippines — English, Filipino/Tagalog, and Taglish

### Example 1 — Financial terminology

The Philippines flow uses terms such as premium, policy, beneficiary, rider, lapse, coverage, and bank referral.

These terms are treated as domain terminology rather than translated word-for-word.

### Example 2 — Taglish interaction

The Philippines flow supports natural Taglish interactions where English financial terminology can appear inside Filipino conversational speech.

Example:

> “Pwede po ba akong mag-add ng beneficiary sa policy ko?”

The response remains appropriate to the candidate's language/register instead of forcing an English-only response.

### Example 3 — Localized objection and escalation

The flow supports objections related to premium affordability, coverage, beneficiaries, and policy concerns.

When human assistance is requested, the fallback remains in the active language/register.

---

## Indonesia — Formal and Colloquial Bahasa Indonesia

### Example 1 — Financial terminology

The Indonesia flow uses local financial terms including cicilan, tenor, denda, DP, jatuh tempo, angsuran, and pembiayaan.

### Example 2 — Colloquial Indonesian

The flow supports colloquial Indonesian rather than requiring formal Jakarta-style phrasing.

Example:

> “Gak kuat cicilan nih, bisa minta tenor panjang?”

This represents natural conversational language rather than a literal translation of a formal financial question.

### Example 3 — Mixed English/Indonesian terminology

The flow supports finance-related English loanwords used naturally with Indonesian.

Examples include terms such as DP and finance-related product terminology.

The implementation preserves the intended language/register instead of automatically switching to English.

---

## Localization Summary

The Q3 implementation is designed around market-specific conversation behavior rather than direct translation.

### Philippines

- English
- Filipino/Tagalog
- Natural Taglish
- Local insurance terminology
- Localized objection handling
- Language-preserving fallback

### Indonesia

- Formal Bahasa Indonesia
- Colloquial Bahasa Indonesia
- Mixed English/Indonesian financial terminology
- Local finance terminology
- Localized objection handling
- Language-preserving fallback

Automated tests verify the application-level localization and fallback behavior. Actual recorded-call observations are documented separately.
