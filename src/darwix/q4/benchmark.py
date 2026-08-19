from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Any, Dict
import asyncio
import math

from darwix.q4.asr import TranscriptChunk
from darwix.q4.signals import SignalExtractor, Signal
from darwix.q4.nudges import NudgeEngine, Nudge
from darwix.q4.dashboard import DashboardService, ConnectionManager


@dataclass
class BenchmarkResult:
    samples_ms: List[float]
    iterations: int
    min_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    max_ms: float


def _ms(d: float) -> float:
    return d * 1000.0


def _percentile(sorted_samples: List[float], p: float) -> float:
    # deterministic percentile: use the value at ceil(p * n) - 1, with p in (0,1]
    if not sorted_samples:
        return 0.0
    n = len(sorted_samples)
    idx = math.ceil(p * n) - 1
    if idx < 0:
        idx = 0
    if idx >= n:
        idx = n - 1
    return sorted_samples[idx]


def compute_stats(samples_ms: List[float]) -> Dict[str, float]:
    # expects samples in ms
    if not samples_ms:
        return dict(min_ms=0.0, mean_ms=0.0, median_ms=0.0, p95_ms=0.0, max_ms=0.0)
    s_sorted = sorted(samples_ms)
    return {
        "min_ms": float(s_sorted[0]),
        "mean_ms": float(statistics.mean(s_sorted)),
        "median_ms": float(statistics.median(s_sorted)),
        "p95_ms": float(_percentile(s_sorted, 0.95)),
        "max_ms": float(s_sorted[-1]),
    }


def _measure_callable(func: Callable[[], Any], iterations: int, warmup: int) -> List[float]:
    # warmup
    for _ in range(warmup):
        res = func()
        if asyncio.iscoroutine(res):
            asyncio.run(res)

    samples: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        res = func()
        # if func returns a coroutine, run it
        if asyncio.iscoroutine(res):
            # run coroutine to completion; use asyncio.run for isolation
            asyncio.run(res)
        t1 = time.perf_counter()
        samples.append(_ms(t1 - t0))
    return samples


def measure_transcript_to_signals(
    tc: TranscriptChunk,
    extractor: Optional[SignalExtractor] = None,
    iterations: int = 10,
    warmup: int = 2,
) -> BenchmarkResult:
    extractor = extractor or SignalExtractor()

    def _fn():
        # measure only the call to process
        extractor.process(tc)
        return None

    samples = _measure_callable(_fn, iterations, warmup)
    stats = compute_stats(samples)
    return BenchmarkResult(samples_ms=samples, iterations=iterations, **stats)


def measure_signal_to_nudge(
    signal: Signal,
    engine: Optional[NudgeEngine] = None,
    iterations: int = 10,
    warmup: int = 2,
) -> BenchmarkResult:
    engine = engine or NudgeEngine()

    def _fn():
        engine.process(signal)
        return None

    samples = _measure_callable(_fn, iterations, warmup)
    stats = compute_stats(samples)
    return BenchmarkResult(samples_ms=samples, iterations=iterations, **stats)


def measure_nudge_to_dashboard(
    nudge: Nudge,
    service: Optional[DashboardService] = None,
    iterations: int = 10,
    warmup: int = 2,
) -> BenchmarkResult:
    # create manager/service if not provided
    if service is None:
        mgr = ConnectionManager()
        service = DashboardService(mgr)

    def _fn():
        # deliver returns a coroutine
        return service.deliver(nudge)

    samples = _measure_callable(_fn, iterations, warmup)
    stats = compute_stats(samples)
    return BenchmarkResult(samples_ms=samples, iterations=iterations, **stats)


def measure_end_to_end(
    tc: TranscriptChunk,
    extractor: Optional[SignalExtractor] = None,
    engine: Optional[NudgeEngine] = None,
    service: Optional[DashboardService] = None,
    iterations: int = 10,
    warmup: int = 2,
) -> BenchmarkResult:
    extractor = extractor or SignalExtractor()
    engine = engine or NudgeEngine()
    if service is None:
        mgr = ConnectionManager()
        service = DashboardService(mgr)

    def _fn():
        # run full pipeline: transcript -> signals -> nudges -> deliver
        signals = extractor.process(tc)
        nudges = []
        for s in signals:
            nudges.extend(engine.process(s))
        # deliver all nudges (async) as part of pipeline
        async def _deliver_all():
            for n in nudges:
                await service.deliver(n)

        return _deliver_all()

    samples = _measure_callable(_fn, iterations, warmup)
    stats = compute_stats(samples)
    return BenchmarkResult(samples_ms=samples, iterations=iterations, **stats)
