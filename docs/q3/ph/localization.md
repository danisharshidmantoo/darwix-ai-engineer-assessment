# Philippines Voice Bot — Localization Evidence

## Market

Philippines

## Sector

Life insurance / bancassurance

## Languages and Register

The prototype supports:

- English
- Filipino / Tagalog
- Natural Taglish

The conversation uses a polite customer-service register, including the Filipino politeness marker "po".

## Localization Examples

### Example 1 — Filipino customer-service language

The agent uses Filipino phrases such as:

> "Magandang araw po!"

and:

> "Salamat po."

This establishes a locally appropriate customer-service register rather than simply translating an English script.

### Example 2 — Natural Taglish

The bot naturally combines Filipino and English within the same interaction.

Examples include:

> "Almost done na po tayo with the basic details."

and:

> "I'm a little worried, though, that I won't be able to afford the monthly premium."

This reflects mixed-language conversational behavior rather than an English-only flow.

### Example 3 — Local financial/payment terminology

The prototype uses Philippine-relevant terminology and payment references including:

- premium
- policy
- sum assured
- coverage
- Auto-Debit Arrangement (ADA)
- E-Wallets
- GCash
- Maya
- Bills Payment
- Online Banking
- Financial Advisor

The second recorded call also demonstrates discussion of quarterly versus monthly payment preferences.

## Objection Localization

The affordability objection is handled in a polite Taglish/Filipino register.

Example:

> "I completely understand po, and it's very valid to be concerned about the budget."

The agent discusses payment frequency and plan tiers rather than ignoring the customer's financial concern.

## Human Escalation

When the customer requests a human representative, the bot maintains the same language/register and routes the request to a Financial Advisor.

## Fallback Behavior

When the customer asks for information that is not available to the bot, the prototype avoids fabricating an answer and offers human assistance.

The first Philippines recording demonstrates this behavior for a policy-coverage question and an out-of-scope question about employee salaries.

## ASR Observations

The recorded calls show imperfect recognition of some short Filipino utterances. Examples include short responses being transcribed as unrelated English words.

This is documented as a prototype limitation rather than being presented as perfect native-language ASR performance.

## Evidence

Two recorded Philippines calls are stored in the submitted Google Drive folder:

1. Q3 Philippines — Call 1: Cooperative Customer, Objection, Unsupported Query & Escalation
2. Q3 Philippines — Call 2: Taglish, Affordability Objection & Payment Preference
