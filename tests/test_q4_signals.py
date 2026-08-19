"""Unit tests for deterministic streaming signal extraction (Q4 Step 2).

These tests exercise the SignalExtractor against TranscriptChunk events.
"""
import time

from darwix.q4.signals import SignalExtractor, CUSTOMER_CONFUSION, CUSTOMER_HESITATION, PAYMENT_CONCERN, OBJECTION, HUMAN_ASSISTANCE_REQUEST, PURCHASE_INTENT
from darwix.q4.asr import TranscriptChunk


def _mk_chunk(text, start_time=None, speaker="customer", seq=0):
    now = start_time if start_time is not None else time.time()
    return TranscriptChunk(
        text=text,
        start_time=now,
        end_time=now + 0.01,
        speaker=speaker,
        is_final=True,
        sequence_id=seq,
        emitted_at=now + 0.01,
    )


def test_english_confusion_detection():
    ex = SignalExtractor()
    tc = _mk_chunk("I don't understand what you mean", speaker="customer")
    sigs = ex.process(tc)
    assert any(s.signal_type == CUSTOMER_CONFUSION for s in sigs)
    # evidence preserved
    assert any("don't understand" in s.evidence.lower() or "what you mean" in s.evidence.lower() for s in sigs)


def test_indonesian_confusion_detection():
    ex = SignalExtractor()
    tc = _mk_chunk("Saya kurang paham, bisa dijelaskan lagi?", speaker="customer")
    sigs = ex.process(tc)
    assert any(s.signal_type == CUSTOMER_CONFUSION for s in sigs)
    assert any("saya kurang paham" in s.evidence.lower() or "bisa dijelaskan" in s.evidence.lower() for s in sigs)


def test_hesitation_detection():
    ex = SignalExtractor()
    tc = _mk_chunk("I'm not sure about this", speaker="customer")
    sigs = ex.process(tc)
    assert any(s.signal_type == CUSTOMER_HESITATION for s in sigs)

    tc2 = _mk_chunk("Saya masih ragu", speaker="customer")
    sigs2 = ex.process(tc2)
    assert any(s.signal_type == CUSTOMER_HESITATION for s in sigs2)


def test_payment_concern_detection():
    ex = SignalExtractor()
    tc = _mk_chunk("The payment is too high, I can't afford it", speaker="customer")
    sigs = ex.process(tc)
    assert any(s.signal_type == PAYMENT_CONCERN for s in sigs)

    tc2 = _mk_chunk("Cicilannya terlalu besar dan saya tidak sanggup bayar", speaker="customer")
    sigs2 = ex.process(tc2)
    assert any(s.signal_type == PAYMENT_CONCERN for s in sigs2)


def test_objection_detection():
    ex = SignalExtractor()
    tc = _mk_chunk("I don't want this", speaker="customer")
    sigs = ex.process(tc)
    assert any(s.signal_type == OBJECTION for s in sigs)

    tc2 = _mk_chunk("Saya tidak tertarik", speaker="customer")
    sigs2 = ex.process(tc2)
    assert any(s.signal_type == OBJECTION for s in sigs2)


def test_human_assistance_detection():
    ex = SignalExtractor()
    tc = _mk_chunk("I want to speak to a human, please connect me to an agent", speaker="customer")
    sigs = ex.process(tc)
    assert any(s.signal_type == HUMAN_ASSISTANCE_REQUEST for s in sigs)

    tc2 = _mk_chunk("Saya mau bicara dengan customer service", speaker="customer")
    sigs2 = ex.process(tc2)
    assert any(s.signal_type == HUMAN_ASSISTANCE_REQUEST for s in sigs2)


def test_purchase_intent_detection():
    ex = SignalExtractor()
    tc = _mk_chunk("I'm interested. I'd like to apply", speaker="customer")
    sigs = ex.process(tc)
    assert any(s.signal_type == PURCHASE_INTENT for s in sigs)

    tc2 = _mk_chunk("Saya tertarik dan ingin mengajukan pembiayaan", speaker="customer")
    sigs2 = ex.process(tc2)
    assert any(s.signal_type == PURCHASE_INTENT for s in sigs2)


def test_agent_speech_is_ignored():
    ex = SignalExtractor()
    tc = _mk_chunk("I don't understand", speaker="agent")
    sigs = ex.process(tc)
    assert sigs == []


def test_timestamp_and_speaker_preserved():
    ex = SignalExtractor()
    t0 = time.time()
    tc = _mk_chunk("I don't understand", start_time=t0, speaker="customer")
    sigs = ex.process(tc)
    assert sigs and sigs[0].timestamp == t0
    assert sigs[0].speaker == "customer"


def test_evidence_preserved_and_mixed_language():
    ex = SignalExtractor()
    tc = _mk_chunk("Saya tertarik to apply for pembiayaan", speaker="customer")
    sigs = ex.process(tc)
    assert any(s.signal_type == PURCHASE_INTENT for s in sigs)
    # evidence should contain Indonesian phrase
    assert any("saya tertarik" in s.evidence.lower() or "mengajukan" in s.evidence.lower() for s in sigs)


def test_duplicate_suppression():
    ex = SignalExtractor(suppression_window=5.0)
    tc1 = _mk_chunk("Saya kurang paham", speaker="customer", seq=1)
    sigs1 = ex.process(tc1)
    assert any(s.signal_type == CUSTOMER_CONFUSION for s in sigs1)

    # Immediately process same text again; should be suppressed
    tc2 = _mk_chunk("Saya kurang paham", speaker="customer", seq=2, start_time=tc1.start_time + 1)
    sigs2 = ex.process(tc2)
    assert sigs2 == []

    # After suppression window, same text should re-emit
    tc3 = _mk_chunk("Saya kurang paham", speaker="customer", seq=3, start_time=tc1.start_time + 10)
    sigs3 = ex.process(tc3)
    assert any(s.signal_type == CUSTOMER_CONFUSION for s in sigs3)


def test_incremental_processing_multiple_chunks():
    ex = SignalExtractor()
    # multiple different signals across chunks should all be emitted
    tc1 = _mk_chunk("I'm not sure", speaker="customer", seq=1)
    tc2 = _mk_chunk("I want to speak to a human", speaker="customer", seq=2)
    tc3 = _mk_chunk("The payment is too high", speaker="customer", seq=3)

    s1 = ex.process(tc1)
    s2 = ex.process(tc2)
    s3 = ex.process(tc3)

    types = [sig.signal_type for sig in (s1 + s2 + s3)]
    assert CUSTOMER_HESITATION in types
    assert HUMAN_ASSISTANCE_REQUEST in types
    assert PAYMENT_CONCERN in types


def test_deterministic_offline_behavior():
    # Running twice with same inputs yields same outputs deterministically
    ex1 = SignalExtractor()
    ex2 = SignalExtractor()
    tc = _mk_chunk("Saya tidak tertarik", speaker="customer")
    s1 = ex1.process(tc)
    s2 = ex2.process(tc)
    assert len(s1) == len(s2)
    assert all(a.signal_type == b.signal_type for a, b in zip(s1, s2))


def test_duplicate_suppression_window_expiry():
    # Use a small suppression window and validate expiry behavior precisely
    window = 2.0
    ex = SignalExtractor(suppression_window=window)
    t0 = time.time()

    tc1 = _mk_chunk("Saya kurang paham", start_time=t0, speaker="customer", seq=1)
    s1 = ex.process(tc1)
    assert any(sig.signal_type == CUSTOMER_CONFUSION for sig in s1)

    # within window -> suppressed
    tc2 = _mk_chunk("Saya kurang paham", start_time=t0 + 1.0, speaker="customer", seq=2)
    s2 = ex.process(tc2)
    assert s2 == []

    # just after window -> should emit again
    tc3 = _mk_chunk("Saya kurang paham", start_time=t0 + window + 0.1, speaker="customer", seq=3)
    s3 = ex.process(tc3)
    assert any(sig.signal_type == CUSTOMER_CONFUSION for sig in s3)


def test_multiple_signals_in_single_chunk():
    ex = SignalExtractor()
    # craft a single chunk that contains both an objection and a human assistance request
    text = "Saya tidak mau ini, saya mau bicara dengan customer service sekarang"
    tc = _mk_chunk(text, speaker="customer")
    sigs = ex.process(tc)

    types = {s.signal_type for s in sigs}
    assert OBJECTION in types
    assert HUMAN_ASSISTANCE_REQUEST in types

    # verify evidence for each signal type is present
    obj_evidence = [s.evidence.lower() for s in sigs if s.signal_type == OBJECTION]
    human_evidence = [s.evidence.lower() for s in sigs if s.signal_type == HUMAN_ASSISTANCE_REQUEST]

    assert any("tidak mau" in e or "tidak tertarik" in e for e in obj_evidence)
    assert any("mau bicara" in e or "customer service" in e for e in human_evidence)
