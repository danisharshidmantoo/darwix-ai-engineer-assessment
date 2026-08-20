import asyncio
import time

from darwix.q4.streaming import ReplayAudioStream
from darwix.q4.asr import MockStreamingASR
from darwix.q4.signals import SignalExtractor
from darwix.q4.nudges import NudgeEngine


SEGMENTS = [
    {
        "payload": b"",
        "duration": 2.0,
        "speaker": "customer",
        "transcript_hint": "I'm interested in applying for the financing.",
    },
    {
        "payload": b"",
        "duration": 2.0,
        "speaker": "agent",
        "transcript_hint": "Great. Let me collect a few details.",
    },
    {
        "payload": b"",
        "duration": 2.0,
        "speaker": "customer",
        "transcript_hint": "The payment is too high and I'm worried I can't afford it.",
    },
    {
        "payload": b"",
        "duration": 2.0,
        "speaker": "agent",
        "transcript_hint": "I understand your concern.",
    },
    {
        "payload": b"",
        "duration": 2.0,
        "speaker": "customer",
        "transcript_hint": "I'm interested in another option as well.",
    },
    {
        "payload": b"",
        "duration": 2.0,
        "speaker": "customer",
        "transcript_hint": "The payment is too high and I'm worried I can't afford it.",
    },
    {
        "payload": b"",
        "duration": 2.0,
        "speaker": "customer",
        "transcript_hint": "The payment is too high and I'm worried I can't afford it.",
    },
    {
        "payload": b"",
        "duration": 2.0,
        "speaker": "customer",
        "transcript_hint": "I want to speak to a human.",
    },
    {
        "payload": b"",
        "duration": 2.0,
        "speaker": "customer",
        "transcript_hint": "I want to speak to a human.",
    },
]


async def main():
    stream = ReplayAudioStream(SEGMENTS, realtime=True)
    asr = MockStreamingASR(per_chunk_delay=0.05)
    extractor = SignalExtractor(suppression_window=10.0)
    nudges = NudgeEngine()

    print("=" * 72)
    print("Q4 — REAL-TIME AGENT ASSIST LIVE DEMO")
    print("=" * 72)
    print()
    print("Pipeline:")
    print("Audio Replay → Streaming ASR → Signal Detection → Nudge Generation")
    print()
    print("Starting real-time stream...")
    print()

    start = time.perf_counter()

    async for tc in asr.transcribe(stream.stream()):
        elapsed = time.perf_counter() - start

        print(
            f"[{elapsed:6.2f}s] "
            f"{tc.speaker.upper():8s}: {tc.text}"
        )

        signals = extractor.process(tc)

        if not signals and tc.speaker == "customer":
            print("           SIGNAL  → suppressed / no actionable signal")

        for signal in signals:
            print(
                f"           SIGNAL  → {signal.signal_type} "
                f"(confidence={signal.confidence:.2f})"
            )

            generated = nudges.process(signal)

            if not generated:
                print(
                    f"           NUDGE   → suppressed by cooldown "
                    f"({signal.signal_type})"
                )

            for nudge in generated:
                print(
                    f"           NUDGE   → [{nudge.priority}] "
                    f"{nudge.message}"
                )
        print()

    print("=" * 72)
    print("STREAM COMPLETE")
    print("=" * 72)
    print()
    print("Demonstrated:")
    print("✓ Real-time transcript replay")
    print("✓ Incremental signal detection")
    print("✓ Purchase-intent detection")
    print("✓ Payment-concern detection")
    print("✓ Human-assistance escalation")
    print("✓ Nudge priority")
    print("✓ Duplicate/cooldown suppression")
    print()


if __name__ == "__main__":
    asyncio.run(main())
