"""Unit tests for Q4 streaming/simulation foundation."""
import asyncio
import time

import pytest

from darwix.q4.streaming import ReplayAudioStream, AudioChunk, StreamStart, StreamEnd
from darwix.q4.asr import MockStreamingASR, TranscriptChunk


def test_chunks_emitted_incrementally_and_terminate_cleanly():
    async def _run():
        segments = [
            {"payload": b"a1", "duration": 0.01, "speaker": "agent", "transcript_hint": "Halo"},
            {"payload": b"a2", "duration": 0.01, "speaker": "customer", "transcript_hint": "Saya mau pinjam"},
        ]
        stream = ReplayAudioStream(segments, realtime=False)
        gen = stream.stream()

        events = []
        async for e in gen:
            events.append(e)

        # Expect StreamStart, two AudioChunk, StreamEnd
        assert isinstance(events[0], StreamStart)
        assert isinstance(events[1], AudioChunk)
        assert isinstance(events[2], AudioChunk)
        assert isinstance(events[3], StreamEnd)

    asyncio.run(_run())


def test_replay_respects_realtime_timing():
    async def _run():
        # Use small durations but check that real-time flag causes sleeps approximately
        segments = [
            {"payload": b"s1", "duration": 0.05, "speaker": "agent", "transcript_hint": "A"},
            {"payload": b"s2", "duration": 0.05, "speaker": "customer", "transcript_hint": "B"},
        ]
        stream = ReplayAudioStream(segments, realtime=True)
        gen = stream.stream()

        timestamps = []
        async for e in gen:
            if isinstance(e, AudioChunk):
                timestamps.append(time.time())

        # We should have two timestamps and interval between them >= ~0.05
        assert len(timestamps) == 2
        interval = timestamps[1] - timestamps[0]
        assert interval >= 0.04

    asyncio.run(_run())


def test_transcript_events_emitted_incrementally_and_speaker_preserved():
    async def _run():
        segments = [
            {"payload": b"x1", "duration": 0.01, "speaker": "agent", "transcript_hint": "Selamat"},
            {"payload": b"x2", "duration": 0.01, "speaker": "customer", "transcript_hint": "Terima kasih"},
        ]
        stream = ReplayAudioStream(segments, realtime=False)
        asr = MockStreamingASR(per_chunk_delay=0)

        async def merged():
            async for event in asr.transcribe(stream.stream()):
                yield event

        results = []
        async for t in merged():
            results.append(t)

        assert len(results) == 2
        assert all(isinstance(r, TranscriptChunk) for r in results)
        assert results[0].text == "Selamat"
        assert results[0].speaker == "agent"
        assert results[1].text == "Terima kasih"
        assert results[1].speaker == "customer"
        # timestamps monotonic
        assert results[0].emitted_at <= results[1].emitted_at

    asyncio.run(_run())


def test_empty_input_handled_safely():
    async def _run():
        stream = ReplayAudioStream([], realtime=False)
        asr = MockStreamingASR()

        seen = []
        async for e in asr.transcribe(stream.stream()):
            seen.append(e)

        assert seen == []

    asyncio.run(_run())


def test_invalid_segment_handled():
    async def _run():
        # segment missing payload/duration -> should still emit chunk with defaults
        segments = [{"speaker": "agent"}]
        stream = ReplayAudioStream(segments, realtime=False)
        events = []
        async for e in stream.stream():
            events.append(e)

        # should see StreamStart, AudioChunk, StreamEnd
        assert any(isinstance(x, AudioChunk) for x in events)

    asyncio.run(_run())
