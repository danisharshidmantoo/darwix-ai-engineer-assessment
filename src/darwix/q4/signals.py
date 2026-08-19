from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

from darwix.q4.asr import TranscriptChunk


@dataclass
class Signal:
    signal_type: str
    timestamp: float
    speaker: Optional[str]
    evidence: str
    confidence: float
    sequence_id: Optional[int] = None


class SignalExtractor:
    """Deterministic, incremental signal extractor for live transcript events.

    Usage:
        extractor = SignalExtractor()
        signals = extractor.process(transcript_chunk)

    The extractor preserves timestamps and speaker labels from the TranscriptChunk.
    Duplicate suppression prevents emitting the same (speaker, type, normalized evidence)
    more than once within the suppression_window (seconds).
    """

    # suppression window in seconds for duplicate signals
    suppression_window: float = 10.0

    def __init__(self, suppression_window: float = 10.0):
        self.suppression_window = suppression_window
        # map (speaker, signal_type, normalized_evidence) -> last_emitted_timestamp
        self._recent: Dict[Tuple[Optional[str], str, str], float] = {}

        # compile patterns for faster matching
        # Each entry maps signal_type -> list of regex patterns
        self._patterns: Dict[str, List[re.Pattern]] = {
            "CUSTOMER_CONFUSION": [
                re.compile(r"\bi don't understand\b", re.I),
                re.compile(r"\bwhat do you mean\b", re.I),
                re.compile(r"\bcan you explain( that)?\b", re.I),
                re.compile(r"\bsaya kurang paham\b", re.I),
                re.compile(r"\bmaksudnya (bagaimana|gimana)\b", re.I),
                re.compile(r"\bbisa dijelaskan( lagi)?\b", re.I),
            ],
            "CUSTOMER_HESITATION": [
                re.compile(r"\bI'm not sure\b", re.I),
                re.compile(r"\blet me think\b", re.I),
                re.compile(r"\bi need to think about it\b", re.I),
                re.compile(r"\bsaya masih ragu\b", re.I),
                re.compile(r"\bsaya pikir-?pikir( dulu)?\b", re.I),
            ],
            "PAYMENT_CONCERN": [
                re.compile(r"\btoo expensive\b", re.I),
                re.compile(r"\bi can't afford( the)?( installment| payment)?\b", re.I),
                re.compile(r"\bthe payment is too high\b", re.I),
                re.compile(r"\bcicilan(nya|nya)? terlalu (besar|tinggi)\b", re.I),
                re.compile(r"\bterlalu mahal\b", re.I),
                re.compile(r"\bsaya tidak sanggup bayar\b", re.I),
                re.compile(r"\bsaya gak sanggup bayar\b", re.I),
            ],
            "OBJECTION": [
                re.compile(r"\bi don't want this\b", re.I),
                re.compile(r"\bi'm not interested\b", re.I),
                re.compile(r"\bsaya tidak tertarik\b", re.I),
                re.compile(r"\bsaya tidak mau\b", re.I),
            ],
            "HUMAN_ASSISTANCE_REQUEST": [
                re.compile(r"\bi want to speak to a human\b", re.I),
                re.compile(r"\bconnect me to( an)? agent\b", re.I),
                re.compile(r"\bsaya mau bicara dengan (manusia|customer service|cs)\b", re.I),
                re.compile(r"\bsaya ingin bicara dengan (customer service|cs|manusia)\b", re.I),
            ],
            "PURCHASE_INTENT": [
                re.compile(r"\bi'm interested\b", re.I),
                re.compile(r"\bi would like to apply\b", re.I),
                re.compile(r"\bi'd like to apply\b", re.I),
                re.compile(r"\bi'd like to apply\b", re.I),
                re.compile(r"\bsaya tertarik\b", re.I),
                re.compile(r"\bsaya ingin mengajukan( pembiayaan| pinjaman)?\b", re.I),
            ],
        }

    def _normalize(self, text: str) -> str:
        t = text.strip().lower()
        # collapse whitespace
        t = re.sub(r"\s+", " ", t)
        return t

    def _is_duplicate(self, speaker: Optional[str], signal_type: str, evidence_norm: str, now: float) -> bool:
        key = (speaker, signal_type, evidence_norm)
        last = self._recent.get(key)
        if last is None:
            return False
        # if last emitted within window, consider duplicate
        return (now - last) < self.suppression_window

    def _mark_emitted(self, speaker: Optional[str], signal_type: str, evidence_norm: str, now: float) -> None:
        key = (speaker, signal_type, evidence_norm)
        self._recent[key] = now

    def process(self, tc: TranscriptChunk) -> List[Signal]:
        """Process a TranscriptChunk incrementally and return zero-or-more Signals.

        Only customer utterances produce signals. The extractor is deterministic and
        offline: it uses regex matching against the transcript text.
        """
        if tc is None:
            return []

        # Only examine customer utterances
        speaker = tc.speaker
        if speaker is None:
            return []

        # Normalize a few known labels — prefer exact 'customer'
        speaker_norm = speaker.lower() if isinstance(speaker, str) else speaker
        if speaker_norm != "customer":
            return []

        text = tc.text or ""
        if not text.strip():
            return []

        text_norm = self._normalize(text)
        now = tc.start_time if tc.start_time else time.time()

        signals: List[Signal] = []

        for s_type, patterns in self._patterns.items():
            for pat in patterns:
                if pat.search(text):
                    # evidence is the original matched substring when possible
                    m = pat.search(text)
                    evidence = m.group(0) if m is not None else text
                    evidence_norm = self._normalize(evidence)

                    if self._is_duplicate(speaker_norm, s_type, evidence_norm, now):
                        # skip duplicate
                        continue

                    sig = Signal(
                        signal_type=s_type,
                        timestamp=tc.start_time,
                        speaker=speaker,
                        evidence=evidence,
                        confidence=1.0,
                        sequence_id=tc.sequence_id,
                    )
                    signals.append(sig)
                    self._mark_emitted(speaker_norm, s_type, evidence_norm, now)
                    # once one pattern for this signal type matches, avoid checking others
                    break

        return signals


# Expose common signal type constants for tests/consumers
CUSTOMER_CONFUSION = "CUSTOMER_CONFUSION"
CUSTOMER_HESITATION = "CUSTOMER_HESITATION"
PAYMENT_CONCERN = "PAYMENT_CONCERN"
OBJECTION = "OBJECTION"
HUMAN_ASSISTANCE_REQUEST = "HUMAN_ASSISTANCE_REQUEST"
PURCHASE_INTENT = "PURCHASE_INTENT"
