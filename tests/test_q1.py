import json
from pathlib import Path

import pytest

from darwix.ingest import build_index, load_retriever
from darwix.q1.knowledge import (
    UNAVAILABLE_INFORMATION_MESSAGE,
    KnowledgeBase,
)
from darwix.q1.livekit_agent import CandidateScreeningAgent
from darwix.q1.screening import (
    EligibilityStatus,
    ScreeningFlow,
    ScreeningStage,
)
from darwix.q1.simulate import run_scenarios

CORPUS_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic_docs"


@pytest.fixture
def knowledge_base(tmp_path: Path) -> KnowledgeBase:
    index_path = tmp_path / "vector_store.json"
    build_index(docs_dir=CORPUS_DIR, index_path=index_path)
    return KnowledgeBase(retriever=load_retriever(index_path, top_k=3))


def test_knowledge_tool_returns_grounded_context_and_citations(
    knowledge_base: KnowledgeBase,
):
    response = knowledge_base.search("Is this internship paid?")

    assert response.available is True
    assert "paid" in response.context.lower()
    assert response.citations
    assert response.citations[0].document_id == "candidate_faqs"


def test_knowledge_tool_uses_explicit_fallback_when_no_source_exists(
    knowledge_base: KnowledgeBase,
):
    response = knowledge_base.search("Will it rain in Mumbai tomorrow?")

    assert response.available is False
    assert response.context == UNAVAILABLE_INFORMATION_MESSAGE
    assert response.citations == []


def test_objection_is_retrieved_from_the_existing_q2_corpus(
    knowledge_base: KnowledgeBase,
):
    response = knowledge_base.search(
        "I don't have a vector database on my resume, am I still eligible?"
    )

    assert response.available is True
    assert any(
        citation.document_id == "common_objections"
        for citation in response.citations
    )
    assert "preferred, not required" in " ".join(response.context.lower().split())


def test_candidate_qualification_state_tracks_required_information():
    flow = ScreeningFlow()
    flow.begin()
    for field, value in (
        ("enrollment_status", "Currently enrolled in university"),
        ("work_authorization", "Authorized to work"),
        ("weekly_hours", "20 hours per week"),
    ):
        flow.record_detail(field, value)

    status = flow.status()
    assert status["stage"] == ScreeningStage.TECHNICAL_SIGNAL.value
    assert "enrollment_status" not in status["missing_information"]
    assert "availability_start_date" in status["missing_information"]
    assert status["is_eligible"] is True


def test_missing_information_remains_visible_until_collected():
    flow = ScreeningFlow()
    flow.begin()
    flow.record_detail("enrollment_status", "Currently enrolled")

    status = flow.status()
    assert status["eligibility_status"] == EligibilityStatus.INCOMPLETE.value
    assert set(status["missing_information"]) >= {
        "work_authorization",
        "weekly_hours",
        "availability_start_date",
        "python_experience",
        "rag_vector_experience",
        "role_relevant_questions",
    }


def test_conflicting_candidate_details_require_clarification():
    flow = ScreeningFlow()
    flow.begin()
    flow.record_detail("weekly_hours", "20 hours per week")
    status = flow.record_detail("weekly_hours", "10 hours per week")

    assert status["eligibility_status"] == EligibilityStatus.CONFLICTING.value
    assert status["conflicts"] == [
        {
            "field": "weekly_hours",
            "first_value": "20 hours per week",
            "new_value": "10 hours per week",
        }
    ]
    flow.resolve_conflict("weekly_hours", "20 hours per week")
    resolved_status = flow.status()
    assert resolved_status["conflicts"] == []


def test_eligibility_weekly_hours_enforced():
    flow = ScreeningFlow()
    flow.begin()
    status = flow.record_detail("weekly_hours", "10 hours per week")

    assert status["is_eligible"] is False
    assert status["eligibility_status"] == EligibilityStatus.INELIGIBLE.value
    assert any("20 hours" in v for v in status["hard_requirement_violations"])


def test_eligibility_work_authorization_enforced():
    flow = ScreeningFlow()
    flow.begin()
    status = flow.record_detail("work_authorization", "I do not have work authorization")

    assert status["is_eligible"] is False
    assert status["eligibility_status"] == EligibilityStatus.INELIGIBLE.value
    assert any("authorization" in v.lower() for v in status["hard_requirement_violations"])


def test_eligibility_enrollment_status_enforced():
    flow = ScreeningFlow()
    flow.begin()
    status = flow.record_detail("enrollment_status", "Graduated 3 years ago")

    assert status["is_eligible"] is False
    assert status["eligibility_status"] == EligibilityStatus.INELIGIBLE.value
    assert any("12 months" in v for v in status["hard_requirement_violations"])


def test_eligibility_python_experience_enforced():
    flow = ScreeningFlow()
    flow.begin()
    status = flow.record_detail("python_experience", "I have zero python knowledge")

    assert status["is_eligible"] is False
    assert status["eligibility_status"] == EligibilityStatus.INELIGIBLE.value
    assert any("Python" in v for v in status["hard_requirement_violations"])


def test_eligibility_prior_internships_enforced():
    flow = ScreeningFlow()
    flow.begin()
    status = flow.record_detail("enrollment_status", "Enrolled student, completed 2 prior internships here")

    assert status["is_eligible"] is False
    assert status["eligibility_status"] == EligibilityStatus.INELIGIBLE.value
    assert any("two prior internships" in v.lower() for v in status["hard_requirement_violations"])


def test_complete_eligible_candidate_ready_for_review():
    flow = ScreeningFlow()
    flow.begin()
    for field, value in (
        ("enrollment_status", "Currently enrolled in BS Computer Science"),
        ("work_authorization", "Legally authorized to work"),
        ("weekly_hours", "20 hours per week"),
        ("availability_start_date", "June 2026"),
        ("python_experience", "2 years of Python coursework"),
        ("rag_vector_experience", "Built a vector search demo"),
    ):
        flow.record_detail(field, value)
    flow.record_technical_signal("Evaluate retrieval with ground-truth test queries")
    flow.record_technical_signal("Inspect low-scoring chunks and refine chunk size")

    status = flow.status()
    assert status["is_eligible"] is True
    assert status["ready_for_human_review"] is True
    assert status["eligibility_status"] == EligibilityStatus.READY_FOR_HUMAN_REVIEW.value
    assert status["stage"] == ScreeningStage.READY_FOR_REVIEW.value


def test_human_escalation_is_recorded_locally():
    flow = ScreeningFlow()
    flow.begin()
    status = flow.request_human_assistance("Candidate asked for a recruiter")

    assert status["escalation_requested"] is True
    assert status["stage"] == ScreeningStage.ESCALATED.value
    assert flow.state.escalations[0].reason == "Candidate asked for a recruiter"


def test_livekit_agent_tools_invoke_domain_logic(
    knowledge_base: KnowledgeBase,
):
    import asyncio

    async def _run():
        flow = ScreeningFlow()
        agent = CandidateScreeningAgent(flow, knowledge_base)

        # 1. Search knowledge tool
        kb_res = await agent.search_candidate_knowledge(None, "Is this internship paid?")
        assert kb_res["available"] is True
        assert "paid" in kb_res["context"].lower()

        # 2. Record detail tool
        detail_res = await agent.record_candidate_detail(None, "weekly_hours", "20 hours per week")
        assert detail_res["answers"]["weekly_hours"] == "20 hours per week"

        # 3. Conflict detection and resolve tool
        conflict_res = await agent.record_candidate_detail(None, "weekly_hours", "10 hours per week")
        assert len(conflict_res["conflicts"]) == 1

        resolved_res = await agent.resolve_conflict(None, "weekly_hours", "20 hours per week")
        assert len(resolved_res["conflicts"]) == 0
        assert resolved_res["answers"]["weekly_hours"] == "20 hours per week"

        # 4. Record technical signal tool
        signal_res = await agent.record_technical_signal(None, "Testing retrieval precision")
        assert signal_res["technical_signal_answer_count"] == 1

        # 5. Get status tool
        status_res = await agent.get_screening_status(None)
        assert "eligibility_status" in status_res
        assert "stage" in status_res

        # 6. Request human assistance tool
        esc_res = await agent.request_human_assistance(None, "Candidate requested human recruiter")
        assert esc_res["escalation_requested"] is True

    asyncio.run(_run())


def test_knowledge_base_safe_fallback_on_missing_or_corrupt_index(tmp_path: Path):
    # Missing index
    missing_kb = KnowledgeBase(index_path=tmp_path / "nonexistent.json")
    res1 = missing_kb.search("Is this internship paid?")
    assert res1.available is False
    assert res1.context == UNAVAILABLE_INFORMATION_MESSAGE

    # Corrupt index
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{malformed json...", encoding="utf-8")
    corrupt_kb = KnowledgeBase(index_path=corrupt_file)
    res2 = corrupt_kb.search("Is this internship paid?")
    assert res2.available is False
    assert res2.context == UNAVAILABLE_INFORMATION_MESSAGE

    # Empty query
    res3 = missing_kb.search("   ")
    assert res3.available is False
    assert res3.context == UNAVAILABLE_INFORMATION_MESSAGE


def test_deterministic_scenarios_use_the_shared_q1_services(
    knowledge_base: KnowledgeBase,
):
    scenarios = run_scenarios(knowledge_base)

    assert set(scenarios) == {
        "cooperative",
        "objection",
        "incomplete",
        "conflicting",
        "out_of_scope",
        "human_assistance",
    }
    assert scenarios["cooperative"].status["ready_for_human_review"] is True
    assert scenarios["cooperative"].status["eligibility_status"] == EligibilityStatus.READY_FOR_HUMAN_REVIEW.value
    assert scenarios["incomplete"].status["missing_information"]
    assert scenarios["incomplete"].status["eligibility_status"] == EligibilityStatus.INCOMPLETE.value
    assert not scenarios["conflicting"].status["conflicts"]
    assert any("unavailable" in line.lower() or UNAVAILABLE_INFORMATION_MESSAGE in line for line in scenarios["out_of_scope"].transcript)
    assert scenarios["human_assistance"].status["escalation_requested"] is True


def test_unsupported_coding_assessment_is_not_invented(
    knowledge_base: KnowledgeBase,
):
    response = knowledge_base.search(
        "I don't want to complete the coding assessment."
    )

    assert response.available is False
    assert response.context == UNAVAILABLE_INFORMATION_MESSAGE


def test_livekit_prompt_contains_behavior_not_corpus_answers():
    from darwix.q1.livekit_agent import INSTRUCTIONS

    forbidden_corpus_facts = (
        "20 hours per week",
        "within the last 12 months",
        "conversion to full-time is a separate",
        "internship is paid",
    )
    assert all(fact not in INSTRUCTIONS.lower() for fact in forbidden_corpus_facts)
    assert "search_candidate_knowledge" in INSTRUCTIONS
    assert "resolve_conflict" in INSTRUCTIONS
