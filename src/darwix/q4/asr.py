"""Streaming ASR abstraction and a mock implementation for tests.

Defines a simple StreamingASR interface and MockStreamingASR which consumes
AudioChunk objects and emits TranscriptChunk events incrementally.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

from darwix.q4.streaming import AudioChunk


@dataclass
class TranscriptChunk:
    text: str
    start_time: float
    end_time: float
    speaker: Optional[str]
    is_final: bool
    sequence_id: Optional[int]
    emitted_at: float


class StreamingASR:
    """Abstract streaming ASR interface.

    Implementations should provide an async transcribe(audio_async_iterable)
    method that accepts an async iterable of AudioChunk and yields TranscriptChunk
    events as they become available.
    """

    async def transcribe(self, audio_chunks) -> AsyncGenerator[TranscriptChunk, None]:
        raise NotImplementedError


class MockStreamingASR(StreamingASR):
    """Deterministic mock ASR for tests.

    Behavior:
      - For each AudioChunk, if chunk.transcript_hint is provided, emit a
        TranscriptChunk with that text.
      - Otherwise, emit a generic text like "audio_chunk_{sequence_id}".
      - Emission occurs shortly after receiving the chunk to simulate streaming
        latency; configurable via per_chunk_delay (seconds).
    """

    def __init__(self, per_chunk_delay: float = 0.0):
        self.per_chunk_delay = per_chunk_delay

    async def transcribe(self, audio_async_iterable) -> AsyncGenerator[TranscriptChunk, None]:
        seq = 0
        async for obj in audio_async_iterable:
            # Only process AudioChunk objects; ignore StreamStart/StreamEnd
            if isinstance(obj, AudioChunk):
                # simulate processing latency
                if self.per_chunk_delay and self.per_chunk_delay > 0:
                    await asyncio.sleep(self.per_chunk_delay)

                text = obj.transcript_hint if obj.transcript_hint is not None else f"audio_chunk_{obj.sequence_id}"
                now = time.time()
                tc = TranscriptChunk(
                    text=text,
                    start_time=obj.start_time,
                    end_time=obj.end_time,
                    speaker=obj.speaker,
                    is_final=True,
                    sequence_id=obj.sequence_id,
                    emitted_at=now,
                )
                yield tc
                seq += 1
            else:
                # pass through other events
                continue
