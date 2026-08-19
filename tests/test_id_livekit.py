"""Unit tests for Indonesia Pembiayaan LiveKit voice agent adapter."""

import asyncio
from pathlib import Path

import pytest

from darwix.ingest import build_index, load_retriever
from darwix.q3.id.flow import IDLeadFlow, QualificationStatus, IDStage
from darwix.q3.id.knowledge import IDKnowledgeBase, LanguageRegister
from darwix.q3.id.livekit_agent import (
    ID_AGENT_NAME,
    IDPembiayaanAgent,
    ID_INSTRUCTIONS,
)

ID_DOCS_DIR = Path(__file__).resolve().parents[1] / "data" / "q3" / "id_docs"


@pytest.fixture
def id_knowledge_base(tmp_path: Path) -> IDKnowledgeBase:
    index_path = tmp_path / "id_livekit_test_index.json"
    build_index(docs_dir=ID_DOCS_DIR, index_path=index_path)
    return IDKnowledgeBase(
        retriever=load_retriever(index_path, top_k=3),
        default_language=LanguageRegister.FORMAL,
    )


def test_id_agent_construction_and_tools(id_knowledge_base: IDKnowledgeBase):
    flow = IDLeadFlow()
    agent = IDPembiayaanAgent(flow, id_knowledge_base)

    assert agent is not None
    assert agent.flow is flow
    assert agent.knowledge_base is id_knowledge_base
    assert ID_AGENT_NAME == "darwix-pembiayaan-id"

    tool_names = {
        "search_pembiayaan_knowledge",
        "record_lead_detail",
        "resolve_conflict",
        "get_lead_status",
        "set_preferred_language",
        "request_human_assistance",
    }
    for tool_name in tool_names:
        assert hasattr(agent, tool_name), f"Missing tool: {tool_name}"


def test_id_agent_instructions_are_behavioral_only():
    forbidden = ("Rp3,000,000", "0% DP", "36 months", "denda 2%")
    for f in forbidden:
        assert f.lower() not in ID_INSTRUCTIONS.lower()

    assert "search_pembiayaan_knowledge" in ID_INSTRUCTIONS
    assert "record_lead_detail" in ID_INSTRUCTIONS
    assert "resolve_conflict" in ID_INSTRUCTIONS
    assert "request_human_assistance" in ID_INSTRUCTIONS


def test_id_agent_tools_execution(id_knowledge_base: IDKnowledgeBase):
    async def _run():
        flow = IDLeadFlow()
        agent = IDPembiayaanAgent(flow, id_knowledge_base)

        lang_res = await agent.set_preferred_language(None, "colloquial")
        assert lang_res["language"] == "id-col"

        d1 = await agent.record_lead_detail(None, "age", "32")
        assert d1["details"]["age"] == "32"
        assert d1["stage"] == IDStage.QUALIFICATION.value

        c1 = await agent.record_lead_detail(None, "age", "40")
        assert len(c1["conflicts"]) == 1
        assert c1["qualification_status"] == QualificationStatus.CONFLICTING.value

        r1 = await agent.resolve_conflict(None, "age", "40")
        assert len(r1["conflicts"]) == 0
        assert r1["details"]["age"] == "40"

        s1 = await agent.get_lead_status(None)
        assert "qualification_status" in s1
        assert "missing_mandatory_fields" in s1

        kb_res = await agent.search_pembiayaan_knowledge(None, "Apa itu tenor?", language="id")
        assert kb_res["available"] is True
        assert "tenor" in kb_res["context"].lower()
        assert len(kb_res["citations"]) > 0

        kb_unsupp = await agent.search_pembiayaan_knowledge(None, "Best surf spot in Bali?", language="colloquial")
        assert kb_unsupp["available"] is False
        assert kb_unsupp["citations"] == []
        assert kb_unsupp["language"] == "id-col"

        esc_res = await agent.request_human_assistance(None, "Butuh agen manusia", urgency="high")
        assert esc_res["escalation_requested"] is True
        assert esc_res["stage"] == IDStage.ESCALATED.value
        assert len(agent.flow.state.escalations) == 1

    asyncio.run(_run())
