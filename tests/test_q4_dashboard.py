"""Tests for real-time nudge delivery dashboard abstraction (Q4 Step 4)."""
import asyncio
import time

from darwix.q4.dashboard import ConnectionManager, DashboardService
from darwix.q4.nudges import Nudge


class FakeClient:
    def __init__(self, name="c"):
        self.name = name
        self.messages = []
        self.closed = False

    async def send_json(self, obj):
        if self.closed:
            raise RuntimeError("client closed")
        # simulate small async delay
        await asyncio.sleep(0)
        self.messages.append(obj)

    def close(self):
        self.closed = True


class BrokenClient(FakeClient):
    async def send_json(self, obj):
        # simulate failure
        await asyncio.sleep(0)
        raise RuntimeError("send failed")


def _mk_nudge(msg="test", ts=None, nudge_type="TYPE", priority=10, source="SIG", evidence="ev", seq=0):
    t = ts if ts is not None else time.time()
    return Nudge(
        nudge_type=nudge_type,
        priority=priority,
        timestamp=t,
        message=msg,
        source_signal_type=source,
        evidence=evidence,
        sequence_id=seq,
    )


def test_client_connect_disconnect():
    mgr = ConnectionManager()

    async def _run():
        c = FakeClient("a")
        await mgr.connect(c)
        # connect again should not raise
        await mgr.connect(c)
        await mgr.disconnect(c)

    asyncio.run(_run())


def test_connect_invalid_client_raises():
    mgr = ConnectionManager()

    async def _run():
        try:
            await mgr.connect(None)
            raise AssertionError("connect(None) should have raised")
        except ValueError:
            pass

        class NotAsync:
            def send_json(self, obj):
                pass

        try:
            await mgr.connect(NotAsync())
            raise AssertionError("connect(non-async) should have raised")
        except ValueError:
            pass

    asyncio.run(_run())


def test_broadcast_to_one_client_preserves_nudge():
    mgr = ConnectionManager()
    svc = DashboardService(mgr)

    async def _run():
        c = FakeClient("one")
        await mgr.connect(c)
        n = _mk_nudge(msg="Please clarify", nudge_type="CUSTOMER_CONFUSION", priority=50, source="SIG", evidence="Saya kurang paham")
        # preserve original
        orig = repr(n)
        await svc.deliver(n)
        assert len(c.messages) == 1
        ev = c.messages[0]
        assert ev["event_type"] == "nudge"
        assert ev["nudge_type"] == "CUSTOMER_CONFUSION"
        assert ev["priority"] == 50
        assert ev["message"] == n.message
        assert ev["evidence"] == n.evidence
        assert repr(n) == orig

    asyncio.run(_run())


def test_broadcast_to_multiple_clients():
    mgr = ConnectionManager()
    svc = DashboardService(mgr)

    async def _run():
        c1 = FakeClient("c1")
        c2 = FakeClient("c2")
        await mgr.connect(c1)
        await mgr.connect(c2)
        n = _mk_nudge(msg="Affordability", nudge_type="PAYMENT_CONCERN", priority=80, source="SIG", evidence="terlalu mahal")
        await svc.deliver(n)
        assert len(c1.messages) == 1
        assert len(c2.messages) == 1
        assert c1.messages[0]["nudge_type"] == "PAYMENT_CONCERN"

    asyncio.run(_run())


def test_no_clients_broadcast_noop():
    mgr = ConnectionManager()
    svc = DashboardService(mgr)

    async def _run():
        n = _mk_nudge()
        # should not raise
        await svc.deliver(n)

    asyncio.run(_run())


def test_disconnected_client_does_not_break_others():
    mgr = ConnectionManager()
    svc = DashboardService(mgr)

    async def _run():
        good = FakeClient("good")
        bad = BrokenClient("bad")
        await mgr.connect(good)
        await mgr.connect(bad)
        n = _mk_nudge(msg="Escalate", nudge_type="HUMAN_ASSISTANCE_REQUEST", priority=100, source="SIG", evidence="connect me")
        await svc.deliver(n)
        # good got it
        assert len(good.messages) == 1
        # bad should have been disconnected
        # subsequent broadcast should go only to good
        n2 = _mk_nudge(msg="Next", nudge_type="PURCHASE_INTENT", priority=40, source="SIG", evidence="I want")
        await svc.deliver(n2)
        assert len(good.messages) == 2

    asyncio.run(_run())


def test_multiple_nudges_ordering_and_serialization():
    mgr = ConnectionManager()
    svc = DashboardService(mgr)

    async def _run():
        c = FakeClient("ord")
        await mgr.connect(c)
        t = time.time()
        n1 = _mk_nudge(msg="First", ts=t + 0.1, nudge_type="TYPE1", priority=20, source="S1", evidence="e1", seq=1)
        n2 = _mk_nudge(msg="Second", ts=t + 0.2, nudge_type="TYPE2", priority=30, source="S2", evidence="e2", seq=2)
        await svc.deliver(n1)
        await svc.deliver(n2)
        assert len(c.messages) == 2
        # delivered in order
        assert c.messages[0]["message"] == "First"
        assert c.messages[1]["message"] == "Second"
        # deterministic serialization: keys exist and types are primitive
        for ev in c.messages:
            assert isinstance(ev["timestamp"], float)
            assert isinstance(ev["priority"], int)

    asyncio.run(_run())


def test_no_pii_added_by_delivery_layer():
    mgr = ConnectionManager()
    svc = DashboardService(mgr)

    async def _run():
        c = FakeClient("pii")
        await mgr.connect(c)
        n = _mk_nudge(msg="Contains PII", nudge_type="PAYMENT_CONCERN", priority=80, source="SIG", evidence="user@example.com")
        await svc.deliver(n)
        ev = c.messages[0]
        # delivery should not add PII; it should preserve evidence as-is (redaction handled earlier)
        assert ev["evidence"] == n.evidence

    asyncio.run(_run())


def test_invalid_disconnect_and_empty_handling():
    mgr = ConnectionManager()

    async def _run():
        # disconnecting unknown client is safe
        fake = FakeClient()
        await mgr.disconnect(fake)
        # disconnect None should not raise
        await mgr.disconnect(None)

    asyncio.run(_run())


def test_integration_nudge_to_dashboard_event():
    mgr = ConnectionManager()
    svc = DashboardService(mgr)

    async def _run():
        c = FakeClient("int")
        await mgr.connect(c)
        n = _mk_nudge(msg="Please clarify", nudge_type="CUSTOMER_CONFUSION", priority=50, source="SIG", evidence="Saya kurang paham", seq=9)
        await svc.deliver(n)
        ev = c.messages[0]
        assert ev["nudge_type"] == n.nudge_type
        assert ev["source_signal_type"] == n.source_signal_type
        assert ev["sequence_id"] == 9

    asyncio.run(_run())
