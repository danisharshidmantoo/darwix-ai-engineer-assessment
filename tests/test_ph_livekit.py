"""Unit tests for Philippines Bancassurance LiveKit voice agent adapter."""

import asyncio
from pathlib import Path

import pytest

from darwix.ingest import build_index, load_retriever
from darwix.q3.ph.flow import (
    BancassuranceStage,
    LanguageRegister,
    PHLeadFlow,
    QualificationStatus,
)
from darwix.q3.ph.knowledge import (
    FALLBACK_MESSAGES,
    PHKnowledgeBase,
)
from darwix.q3.ph.livekit_agent import (
    PH_AGENT_NAME,
    PH_INSTRUCTIONS,
    PHBancassuranceAgent,
)

PH_DOCS_DIR = Path(__file__).resolve().parents[1] / "data" / "q3" / "ph_docs"


@pytest.fixture
def ph_knowledge_base(tmp_path: Path) -> PHKnowledgeBase:
    index_path = tmp_path / "ph_livekit_test_index.json"
    build_index(docs_dir=PH_DOCS_DIR, index_path=index_path)
    return PHKnowledgeBase(
        retriever=load_retriever(index_path, top_k=3),
        default_language=LanguageRegister.TAGLISH,
    )


def test_ph_agent_construction_and_tools(ph_knowledge_base: PHKnowledgeBase):
    flow = PHLeadFlow()
    agent = PHBancassuranceAgent(flow, ph_knowledge_base)

    assert agent is not None
    assert agent.flow is flow
    assert agent.knowledge_base is ph_knowledge_base
    assert PH_AGENT_NAME == "darwix-bancassurance-ph"

    # Verify tool functions exist on the agent
    tool_names = {
        "search_bancassurance_knowledge",
        "record_lead_detail",
        "resolve_conflict",
        "get_lead_status",
        "set_preferred_language",
        "request_human_assistance",
    }
    for tool_name in tool_names:
        assert hasattr(agent, tool_name), f"Missing tool: {tool_name}"


def test_ph_agent_instructions_are_behavioral_only():
    # Prompt must NOT contain hardcoded corpus facts / specific figures
    forbidden_corpus_facts = (
        "₱500,000",
        "₱1,000,000",
        "31-day grace period",
        "24 months from the date of lapse",
        "36 covered major critical illnesses",
    )
    for fact in forbidden_corpus_facts:
        assert fact.lower() not in PH_INSTRUCTIONS.lower()

    # Must contain essential tool guidance
    assert "search_bancassurance_knowledge" in PH_INSTRUCTIONS
    assert "record_lead_detail" in PH_INSTRUCTIONS
    assert "resolve_conflict" in PH_INSTRUCTIONS
    assert "request_human_assistance" in PH_INSTRUCTIONS


def test_ph_agent_tools_execution(ph_knowledge_base: PHKnowledgeBase):
    async def _run():
        flow = PHLeadFlow()
        agent = PHBancassuranceAgent(flow, ph_knowledge_base)

        # 1. Test set_preferred_language tool
        lang_res = await agent.set_preferred_language(None, "en")
        assert lang_res["language"] == "en"

        # 2. Test record_lead_detail tool
        d1 = await agent.record_lead_detail(None, "age", "35")
        assert d1["details"]["age"] == "35"
        assert d1["stage"] == BancassuranceStage.QUALIFICATION.value

        # 3. Test conflict detection and resolve_conflict tool
        c1 = await agent.record_lead_detail(None, "age", "65")
        assert len(c1["conflicts"]) == 1
        assert c1["qualification_status"] == QualificationStatus.CONFLICTING.value

        r1 = await agent.resolve_conflict(None, "age", "35")
        assert len(r1["conflicts"]) == 0
        assert r1["details"]["age"] == "35"

        # 4. Test get_lead_status tool
        s1 = await agent.get_lead_status(None)
        assert "qualification_status" in s1
        assert "missing_mandatory_fields" in s1

        # 5. Test search_bancassurance_knowledge tool with grounded query
        kb_res = await agent.search_bancassurance_knowledge(
            None, "Paano po mag-assign o mag-update ng beneficiary sa policy?"
        )
        assert kb_res["available"] is True
        assert "beneficiary" in kb_res["context"].lower()
        assert len(kb_res["citations"]) > 0

        # 6. Test search_bancassurance_knowledge tool with unsupported query & register preservation
        kb_unsupp = await agent.search_bancassurance_knowledge(
            None,
            "Weather forecast in Boracay island tomorrow afternoon",
            language="en",
        )
        assert kb_unsupp["available"] is False
        assert kb_unsupp["citations"] == []
        assert kb_unsupp["context"] == FALLBACK_MESSAGES[LanguageRegister.ENGLISH]
        assert kb_unsupp["language"] == "en"

        # 7. Test request_human_assistance tool
        esc_res = await agent.request_human_assistance(
            None, "Customer requested licensed Financial Advisor", urgency="high"
        )
        assert esc_res["escalation_requested"] is True
        assert esc_res["stage"] == BancassuranceStage.ESCALATED.value
        assert len(agent.flow.state.escalations) == 1
        assert agent.flow.state.escalations[0].urgency == "high"

    asyncio.run(_run())


def test_ph_livekit_tts_configuration_object_instantiation(monkeypatch):
    from livekit.agents import inference

    monkeypatch.setenv("LIVEKIT_API_KEY", "test-api-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-api-secret")

    tts_instance = inference.TTS(model="inworld/inworld-tts-2", voice="Ashley")
    assert tts_instance.model == "inworld/inworld-tts-2"
    assert tts_instance._opts.voice == "Ashley"
