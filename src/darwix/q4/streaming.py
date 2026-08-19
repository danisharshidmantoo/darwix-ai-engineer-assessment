"""Streaming / simulation input component for Q4.

Provides ReplayAudioStream which emits audio chunks (AudioChunk) incrementally,
supports real-time replay timing, and yields stream lifecycle events.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import AsyncGenerator, List, Optional


@dataclass
class StreamStart:
    start_time: float


@dataclass
class StreamEnd:
    end_time: float


@dataclass
class StreamError:
    error: str
    timestamp: float


@dataclass
class AudioChunk:
    """Represents a single chunk of audio in the stream.

    payload: raw audio bytes (opaque to streaming layer)
    start_time: float  # seconds since epoch indicating chunk start
    end_time: float  # seconds since epoch indicating chunk end
    speaker: Optional[str] = None
    sequence_id: Optional[int] = None
    transcript_hint: Optional[str] = None  # for mock ASR/testing only
    """

    payload: bytes
    start_time: float
    end_time: float
    speaker: Optional[str] = None
    sequence_id: Optional[int] = None
    transcript_hint: Optional[str] = None


class ReplayAudioStream:
    """Replay an in-memory sequence of audio segments as a real-time stream.

    segments: list of dicts each containing:
      - payload (bytes)
      - duration (float seconds)
      - speaker (optional str)
      - transcript_hint (optional str)  # used by MockStreamingASR

    The stream yields:
      - StreamStart once at the beginning
      - AudioChunk objects sequentially, respecting realtime flag
      - StreamEnd once when finished

    Parameters:
      segments: list of segment dicts as described
      realtime: if True, replay sleeps between chunks to match durations
      chunk_interval: if provided, override per-segment duration and use this
        value for inter-chunk timing
    """

    def __init__(
        self,
        segments: List[dict],
        realtime: bool = False,
        chunk_interval: Optional[float] = None,
    ) -> None:
        self.segments = segments or []
        self.realtime = realtime
        self.chunk_interval = chunk_interval

    async def stream(self) -> AsyncGenerator[object, None]:
        """Async generator yielding StreamStart, AudioChunk..., StreamEnd."""
        start_ts = time.time()
        yield StreamStart(start_time=start_ts)

        seq = 0
        for seg in self.segments:
            payload = seg.get("payload", b"") or b""
            duration = seg.get("duration", 0.0)
            speaker = seg.get("speaker")
            hint = seg.get("transcript_hint")

            # Determine inter-chunk interval
            interval = self.chunk_interval if self.chunk_interval is not None else duration

            chunk_start = time.time()
            chunk_end = chunk_start + duration
            chunk = AudioChunk(
                payload=payload,
                start_time=chunk_start,
                end_time=chunk_end,
                speaker=speaker,
                sequence_id=seq,
                transcript_hint=hint,
            )

            yield chunk

            seq += 1

            if self.realtime:
                # Sleep to simulate real-time between chunk emissions
                # If interval is zero or negative, no sleep
                if interval and interval > 0:
                    await asyncio.sleep(interval)
                else:
                    await asyncio.sleep(0)

        end_ts = time.time()
        yield StreamEnd(end_time=end_ts)
