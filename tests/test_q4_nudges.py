"""Unit tests for deterministic nudge generation (Q4 Step 3)."""
import time

from darwix.q4.nudges import NudgeEngine
from darwix.q4.signals import Signal
from darwix.q4.signals import (
    CUSTOMER_CONFUSION,
    CUSTOMER_HESITATION,
    PAYMENT_CONCERN,
    OBJECTION,
    HUMAN_ASSISTANCE_REQUEST,
    PURCHASE_INTENT,
)


def _mk_signal(sig_type, evidence, timestamp=None, speaker="customer", seq=0):
    ts = timestamp if timestamp is not None else time.time()
    return Signal(
        signal_type=sig_type,
        timestamp=ts,
        speaker=speaker,
        evidence=evidence,
        confidence=1.0,
        sequence_id=seq,
    )


def test_confusion_nudge():
    eng = NudgeEngine()
    s = _mk_signal(CUSTOMER_CONFUSION, "Saya kurang paham")
    nudges = eng.process(s)
    assert len(nudges) == 1
    n = nudges[0]
    assert n.source_signal_type == CUSTOMER_CONFUSION
    assert "Clarify the explanation" in n.message
    assert n.priority == 50
    assert n.timestamp == s.timestamp
    assert "Saya kurang paham" in n.evidence


def test_hesitation_nudge():
    eng = NudgeEngine()
    s = _mk_signal(CUSTOMER_HESITATION, "I'm not sure")
    nudges = eng.process(s)
    assert len(nudges) == 1
    assert "Acknowledge the hesitation" in nudges[0].message
    assert nudges[0].priority == 50


def test_payment_concern_nudge():
    eng = NudgeEngine()
    s = _mk_signal(PAYMENT_CONCERN, "cicilannya terlalu besar")
    nudges = eng.process(s)
    assert len(nudges) == 1
    assert "affordable" in nudges[0].message.lower() or "installment" in nudges[0].message.lower()
    assert nudges[0].priority == 80


def test_objection_nudge():
    eng = NudgeEngine()
    s = _mk_signal(OBJECTION, "Saya tidak tertarik")
    nudges = eng.process(s)
    assert len(nudges) == 1
    assert "Acknowledge the objection" in nudges[0].message
    assert nudges[0].priority == 75


def test_human_assistance_nudge():
    eng = NudgeEngine()
    s = _mk_signal(HUMAN_ASSISTANCE_REQUEST, "Saya mau bicara dengan customer service")
    nudges = eng.process(s)
    assert len(nudges) == 1
    assert "Prepare escalation" in nudges[0].message
    assert nudges[0].priority == 100


def test_purchase_intent_nudge():
    eng = NudgeEngine()
    s = _mk_signal(PURCHASE_INTENT, "Saya tertarik")
    nudges = eng.process(s)
    assert len(nudges) == 1
    assert "next qualification step" in nudges[0].message.lower()
    assert nudges[0].priority == 40


def test_priority_ordering_in_batch():
    eng = NudgeEngine()
    t = time.time()
    signals = [
        _mk_signal(PURCHASE_INTENT, "Saya tertarik", timestamp=t + 0.1),
        _mk_signal(HUMAN_ASSISTANCE_REQUEST, "I want to speak to a human", timestamp=t + 0.05),
        _mk_signal(PAYMENT_CONCERN, "too expensive", timestamp=t + 0.2),
    ]
    nudges = eng.process_batch(signals)
    # highest priority (human assistance) should come first
    assert nudges[0].priority >= nudges[1].priority
    assert nudges[0].source_signal_type == HUMAN_ASSISTANCE_REQUEST


def test_timestamp_and_evidence_propagation():
    eng = NudgeEngine()
    t = 12345.0
    s = _mk_signal(CUSTOMER_CONFUSION, "Maksudnya bagaimana?", timestamp=t)
    n = eng.process(s)[0]
    assert n.timestamp == t
    assert "Maksudnya" in n.evidence


def test_duplicate_suppression_within_cooldown():
    eng = NudgeEngine()
    t0 = time.time()
    s1 = _mk_signal(CUSTOMER_CONFUSION, "Saya kurang paham", timestamp=t0)
    s2 = _mk_signal(CUSTOMER_CONFUSION, "Saya kurang paham", timestamp=t0 + 1)
    n1 = eng.process(s1)
    n2 = eng.process(s2)
    assert len(n1) == 1
    assert n2 == []


def test_same_signal_after_cooldown_emits_again():
    cooldown = 2.0
    eng = NudgeEngine(cooldowns={CUSTOMER_CONFUSION: cooldown})
    t0 = time.time()
    s1 = _mk_signal(CUSTOMER_CONFUSION, "Saya kurang paham", timestamp=t0)
    s2 = _mk_signal(CUSTOMER_CONFUSION, "Saya kurang paham", timestamp=t0 + cooldown + 0.1)
    assert len(eng.process(s1)) == 1
    assert len(eng.process(s2)) == 1


def test_different_signal_types_not_suppressed():
    eng = NudgeEngine()
    t0 = time.time()
    s_conf = _mk_signal(CUSTOMER_CONFUSION, "Saya kurang paham", timestamp=t0)
    s_obj = _mk_signal(OBJECTION, "Saya tidak mau", timestamp=t0 + 1)
    assert len(eng.process(s_conf)) == 1
    assert len(eng.process(s_obj)) == 1


def test_human_escalation_bypasses_normal_suppression():
    # create engine where human cooldown is zero so repeated human signals still produce nudges
    eng = NudgeEngine(cooldowns={HUMAN_ASSISTANCE_REQUEST: 0.0})
    t0 = time.time()
    s1 = _mk_signal(HUMAN_ASSISTANCE_REQUEST, "Connect me", timestamp=t0)
    s2 = _mk_signal(HUMAN_ASSISTANCE_REQUEST, "Connect me", timestamp=t0 + 0.5)
    assert len(eng.process(s1)) == 1
    assert len(eng.process(s2)) == 1


def test_configurable_cooldown_behavior():
    eng = NudgeEngine(cooldowns={CUSTOMER_HESITATION: 0.5})
    t0 = time.time()
    s1 = _mk_signal(CUSTOMER_HESITATION, "Saya masih ragu", timestamp=t0)
    s2 = _mk_signal(CUSTOMER_HESITATION, "Saya masih ragu", timestamp=t0 + 0.6)
    assert len(eng.process(s1)) == 1
    assert len(eng.process(s2)) == 1


def test_no_pii_leakage_in_message():
    eng = NudgeEngine()
    s = _mk_signal(PAYMENT_CONCERN, "My email is user@example.com and phone +62 8123456789")
    nudges = eng.process(s)
    assert len(nudges) == 1
    msg = nudges[0].message
    # raw email/phone should be redacted
    assert "user@example.com" not in msg
    assert "+62 8123456789" not in msg
    assert "[REDACTED]" in msg


def test_deterministic_output_for_identical_inputs():
    eng1 = NudgeEngine()
    eng2 = NudgeEngine()
    s = _mk_signal(OBJECTION, "Saya tidak tertarik")
    n1 = eng1.process(s)
    n2 = eng2.process(s)
    assert len(n1) == len(n2)
    assert all(a.message == b.message and a.priority == b.priority for a, b in zip(n1, n2))
