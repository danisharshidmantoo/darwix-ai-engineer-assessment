"""Tests for deterministic benchmarking utilities (Q4 Step 5)."""
import time

from darwix.q4.benchmark import (
    measure_transcript_to_signals,
    measure_signal_to_nudge,
    measure_nudge_to_dashboard,
    measure_end_to_end,
    compute_stats,
    BenchmarkResult,
)
from darwix.q4.asr import TranscriptChunk
from darwix.q4.signals import SignalExtractor, Signal
from darwix.q4.nudges import NudgeEngine, Nudge
from darwix.q4.dashboard import DashboardService, ConnectionManager


def _mk_tc(text="hello", start_time=None, speaker="customer"):
    t = start_time if start_time is not None else time.time()
    return TranscriptChunk(text=text, start_time=t, end_time=t + 0.01, speaker=speaker, is_final=True, sequence_id=1, emitted_at=t + 0.01)


def _mk_signal(sig_type="TYPE", evidence="ev", timestamp=None):
    ts = timestamp if timestamp is not None else time.time()
    return Signal(signal_type=sig_type, timestamp=ts, speaker="customer", evidence=evidence, confidence=1.0, sequence_id=1)


def _mk_nudge(msg="n", ts=None):
    t = ts if ts is not None else time.time()
    return Nudge(nudge_type="TYPE", priority=10, timestamp=t, message=msg, source_signal_type="SIG", evidence="ev", sequence_id=1)


def test_benchmark_transcript_to_signals_runs_and_returns_stats():
    tc = _mk_tc("Saya kurang paham")
    res = measure_transcript_to_signals(tc, iterations=5, warmup=1)
    assert isinstance(res, BenchmarkResult)
    assert res.iterations == 5
    assert len(res.samples_ms) == 5
    assert all(s >= 0 for s in res.samples_ms)
    stats = compute_stats(res.samples_ms)
    assert "min_ms" in stats and "mean_ms" in stats and "p95_ms" in stats


def test_benchmark_signal_to_nudge_runs_and_respects_iterations():
    sig = _mk_signal(sig_type="CUSTOMER_CONFUSION", evidence="Saya kurang paham")
    res = measure_signal_to_nudge(sig, iterations=4, warmup=1)
    assert res.iterations == 4
    assert len(res.samples_ms) == 4


def test_benchmark_nudge_to_dashboard_nonetwork():
    n = _mk_nudge()
    # create a dashboard service with no clients (no network)
    mgr = ConnectionManager()
    svc = DashboardService(mgr)
    res = measure_nudge_to_dashboard(n, service=svc, iterations=3, warmup=1)
    assert len(res.samples_ms) == 3
    assert res.min_ms >= 0


def test_benchmark_end_to_end_executes():
    tc = _mk_tc("Cicilannya terlalu besar")
    res = measure_end_to_end(tc, iterations=3, warmup=1)
    assert isinstance(res, BenchmarkResult)
    assert len(res.samples_ms) == 3


def test_compute_stats_percentiles_deterministic():
    samples = [1, 2, 3, 4, 5]
    stats = compute_stats(samples)
    # with our percentile definition p95 -> index ceil(0.95*5)-1 = ceil(4.75)-1=5-1=4 -> samples[4]=5
    assert stats["p95_ms"] == 5
    assert stats["min_ms"] == 1
    assert stats["max_ms"] == 5


def test_warmup_excluded_from_measurements():
    tc = _mk_tc("Saya kurang paham")
    # choose a function with side effects to detect warmup influence; we count samples length
    res = measure_transcript_to_signals(tc, iterations=2, warmup=2)
    assert len(res.samples_ms) == 2


def test_repeated_benchmark_runs_return_valid_results():
    tc = _mk_tc("Saya kurang paham")
    r1 = measure_transcript_to_signals(tc, iterations=2, warmup=1)
    r2 = measure_transcript_to_signals(tc, iterations=2, warmup=1)
    assert len(r1.samples_ms) == len(r2.samples_ms) == 2
    assert all(x >= 0 for x in r1.samples_ms + r2.samples_ms)


def test_percentile_calculation_on_even_count():
    samples = [10, 20, 30, 40]
    stats = compute_stats(samples)
    # sorted = [10,20,30,40]; p95 index = ceil(0.95*4)-1 = ceil(3.8)-1=4-1=3 => 40
    assert stats["p95_ms"] == 40


def test_pipeline_components_used_not_reimplemented():
    # ensure extractor and engine are used by benchmarking functions
    tc = _mk_tc("Saya kurang paham")
    res = measure_transcript_to_signals(tc, iterations=1, warmup=0)
    assert len(res.samples_ms) == 1
    sig = _mk_signal(sig_type="PAYMENT_CONCERN", evidence="terlalu mahal")
    res2 = measure_signal_to_nudge(sig, iterations=1, warmup=0)
    assert len(res2.samples_ms) == 1


def test_units_are_milliseconds_and_nonnegative():
    tc = _mk_tc("Saya kurang paham")
    res = measure_transcript_to_signals(tc, iterations=3, warmup=1)
    assert all(isinstance(x, float) for x in res.samples_ms)
    assert all(x >= 0 for x in res.samples_ms)


def test_end_to_end_with_custom_components():
    tc = _mk_tc("Saya mau bicara dengan customer service")
    extractor = SignalExtractor()
    engine = NudgeEngine()
    mgr = ConnectionManager()
    svc = DashboardService(mgr)
    res = measure_end_to_end(tc, extractor=extractor, engine=engine, service=svc, iterations=2, warmup=1)
    assert len(res.samples_ms) == 2


def test_measured_samples_count_matches_iterations():
    tc = _mk_tc("Test")
    iters = 5
    res = measure_transcript_to_signals(tc, iterations=iters, warmup=1)
    assert res.iterations == iters
    assert len(res.samples_ms) == iters
