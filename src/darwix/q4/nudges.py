from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from darwix.q4.signals import (
    CUSTOMER_CONFUSION,
    CUSTOMER_HESITATION,
    PAYMENT_CONCERN,
    OBJECTION,
    HUMAN_ASSISTANCE_REQUEST,
    PURCHASE_INTENT,
    Signal,
)


# Priority numeric values (higher = more urgent)
PRIORITY = {
    HUMAN_ASSISTANCE_REQUEST: 100,
    PAYMENT_CONCERN: 80,
    OBJECTION: 75,
    CUSTOMER_CONFUSION: 50,
    CUSTOMER_HESITATION: 50,
    PURCHASE_INTENT: 40,
}


@dataclass
class Nudge:
    nudge_type: str
    priority: int
    timestamp: float
    message: str
    source_signal_type: str
    evidence: str
    sequence_id: Optional[int] = None


class NudgeEngine:
    """Deterministic nudge generator with suppression/cooldown semantics.

    cooldowns: mapping from signal_type -> cooldown seconds. If not provided,
    defaults are used. Suppression keys are (signal_type, normalized_evidence).

    The engine redacts obvious PII (emails, phone numbers) from evidence when
    embedding into nudge messages to avoid leaking sensitive data.
    """

    DEFAULT_COOLDOWNS = {
        CUSTOMER_CONFUSION: 10.0,
        CUSTOMER_HESITATION: 10.0,
        PAYMENT_CONCERN: 15.0,
        OBJECTION: 15.0,
        HUMAN_ASSISTANCE_REQUEST: 1.0,  # short cooldown / effectively bypass
        PURCHASE_INTENT: 10.0,
    }

    # simple regexes for redaction
    _email_re = re.compile(r"[\w\.-]+@[\w\.-]+")
    _phone_re = re.compile(r"\b\+?\d[\d\s\-]{6,}\b")

    def __init__(self, cooldowns: Optional[Dict[str, float]] = None):
        self.cooldowns = dict(self.DEFAULT_COOLDOWNS)
        if cooldowns:
            self.cooldowns.update(cooldowns)

        # last emitted nudge timestamp keyed by (signal_type, evidence_norm)
        self._last_emitted: Dict[tuple, float] = {}

    def _normalize(self, text: str) -> str:
        t = (text or "").strip().lower()
        t = re.sub(r"\s+", " ", t)
        return t

    def _redact_pii(self, text: str) -> str:
        if not text:
            return text
        s = text
        s = self._email_re.sub("[REDACTED]", s)
        s = self._phone_re.sub("[REDACTED]", s)
        return s

    def _allowed_to_emit(self, signal: Signal) -> bool:
        evidence_norm = self._normalize(signal.evidence)
        key = (signal.signal_type, evidence_norm)
        cooldown = self.cooldowns.get(signal.signal_type, 10.0)
        last = self._last_emitted.get(key)
        # Use signal timestamp for deterministic comparisons
        ts = signal.timestamp if signal.timestamp is not None else time.time()
        if last is None:
            return True
        return (ts - last) >= cooldown

    def _mark_emitted(self, signal: Signal) -> None:
        evidence_norm = self._normalize(signal.evidence)
        key = (signal.signal_type, evidence_norm)
        ts = signal.timestamp if signal.timestamp is not None else time.time()
        self._last_emitted[key] = ts

    def _build_message(self, signal: Signal) -> str:
        # Deterministic templates per signal type. Keep messages internal-only.
        evidence_safe = self._redact_pii(signal.evidence or "")
        if signal.signal_type == CUSTOMER_CONFUSION:
            return f"Clarify the explanation and ask if the customer would like an example. Evidence: '{evidence_safe}'"
        if signal.signal_type == CUSTOMER_HESITATION:
            return f"Acknowledge the hesitation and give the customer space to consider. Evidence: '{evidence_safe}'"
        if signal.signal_type == PAYMENT_CONCERN:
            return f"Explore more affordable installment or tenor options. Evidence: '{evidence_safe}'"
        if signal.signal_type == OBJECTION:
            return f"Acknowledge the objection and ask what concern is most important. Evidence: '{evidence_safe}'"
        if signal.signal_type == HUMAN_ASSISTANCE_REQUEST:
            return f"Customer requested human assistance. Prepare escalation and notify supervisor. Evidence: '{evidence_safe}'"
        if signal.signal_type == PURCHASE_INTENT:
            return f"Customer shows purchase intent. Continue with the next qualification step. Evidence: '{evidence_safe}'"
        # fallback
        return f"Signal {signal.signal_type} detected. Evidence: '{evidence_safe}'"

    def process(self, signal: Signal) -> List[Nudge]:
        """Process a single Signal and return zero-or-more Nudge objects."""
        if signal is None:
            return []

        # Only process customer-origin signals (assume Signal.speaker holds role)
        # This check is conservative; signals are produced by the extractor already.
        if signal.speaker is None:
            return []

        # Decide if allowed to emit based on cooldowns
        # HUMAN_ASSISTANCE_REQUEST has a short cooldown by default to ensure
        # prompt escalation even if repeated.
        if not self._allowed_to_emit(signal):
            return []

        # build nudge
        nudge = Nudge(
            nudge_type=signal.signal_type,
            priority=PRIORITY.get(signal.signal_type, 10),
            timestamp=signal.timestamp,
            message=self._build_message(signal),
            source_signal_type=signal.signal_type,
            evidence=self._redact_pii(signal.evidence or ""),
            sequence_id=signal.sequence_id,
        )

        # record emission
        self._mark_emitted(signal)

        return [nudge]

    def process_batch(self, signals: List[Signal]) -> List[Nudge]:
        """Process a list of signals and return nudges ordered by priority (descending).

        Deterministic: process signals in input order, generate allowed nudges, then
        sort by priority and timestamp to determine final ordering.
        """
        nudges: List[Nudge] = []
        for s in signals:
            nudges.extend(self.process(s))

        # sort by priority desc, then timestamp asc to keep deterministic order
        nudges.sort(key=lambda n: (-n.priority, n.timestamp or 0))
        return nudges
