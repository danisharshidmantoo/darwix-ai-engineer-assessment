"""Unit and integration tests for Philippines Bancassurance deterministic domain logic."""

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

PH_DOCS_DIR = Path(__file__).resolve().parents[1] / "data" / "q3" / "ph_docs"


@pytest.fixture
def ph_knowledge_base(tmp_path: Path) -> PHKnowledgeBase:
    index_path = tmp_path / "ph_test_index.json"
    build_index(docs_dir=PH_DOCS_DIR, index_path=index_path)
    return PHKnowledgeBase(
        retriever=load_retriever(index_path, top_k=3),
        default_language=LanguageRegister.TAGLISH,
    )


# --- Lead Qualification Tests ---


def test_eligible_lead_ready_for_advisor():
    flow = PHLeadFlow()
    flow.begin()
    flow.set_language(LanguageRegister.TAGLISH)

    for field, value in (
        ("age", "32 years old"),
        ("residency", "Residing in Quezon City, Philippines"),
        ("government_id", "Philippine Passport and UMID"),
        ("bank_account_holder", "Yes, active BPI savings account holder"),
        ("medical_declaration", "Healthy, no recent hospitalization or surgery"),
        ("sum_assured_tier", "Tier B (₱1,000,000 Sum Assured)"),
        ("preferred_payment_mode", "Monthly Auto-Debit Arrangement"),
    ):
        flow.record_detail(field, value)

    status = flow.status()
    assert status["is_eligible"] is True
    assert status["ready_for_advisor"] is True
    assert status["qualification_status"] == QualificationStatus.READY_FOR_ADVISOR.value
    assert status["stage"] == BancassuranceStage.READY_FOR_ADVISOR.value
    assert status["missing_mandatory_fields"] == []
    assert status["hard_requirement_violations"] == []


def test_missing_qualification_information_tracked():
    flow = PHLeadFlow()
    flow.begin()
    flow.record_detail("age", "28")

    status = flow.status()
    assert status["is_eligible"] is True
    assert status["qualification_status"] == QualificationStatus.INCOMPLETE.value
    assert set(status["missing_mandatory_fields"]) == {
        "residency",
        "government_id",
        "bank_account_holder",
        "medical_declaration",
    }


@pytest.mark.parametrize(
    "field,value,violation_keyword",
    [
        ("age", "16 years old", "minimum eligible age"),
        ("age", "65 years old", "maximum eligible age"),
        ("residency", "Living permanently in Dubai UAE", "residing in the Philippines"),
        ("government_id", "No valid ID", "valid Philippine government-issued ID"),
        ("bank_account_holder", "No bank account", "partner bank deposit account"),
        ("medical_declaration", "Failed, currently on dialysis", "health declaration"),
    ],
)
def test_ineligible_lead_enforces_grounded_rules(field, value, violation_keyword):
    flow = PHLeadFlow()
    flow.begin()
    status = flow.record_detail(field, value)

    assert status["is_eligible"] is False
    assert status["qualification_status"] == QualificationStatus.INELIGIBLE.value
    assert any(violation_keyword in v for v in status["hard_requirement_violations"])


def test_conflict_detection_and_resolution():
    flow = PHLeadFlow()
    flow.begin()
    flow.record_detail("age", "30")
    status1 = flow.record_detail("age", "65")

    assert status1["qualification_status"] == QualificationStatus.CONFLICTING.value
    assert len(status1["conflicts"]) == 1
    assert status1["conflicts"][0]["field"] == "age"

    status2 = flow.resolve_conflict("age", "30")
    assert status2["conflicts"] == []
    assert status2["details"]["age"] == "30"


def test_state_progression_across_stages():
    flow = PHLeadFlow()
    assert flow.state.stage == BancassuranceStage.GREETING

    flow.begin()
    assert flow.state.stage == BancassuranceStage.QUALIFICATION

    # Complete 5 mandatory qualification fields
    for field, value in (
        ("age", "30"),
        ("residency", "Philippines"),
        ("government_id", "Passport"),
        ("bank_account_holder", "Yes"),
        ("medical_declaration", "Good health"),
    ):
        flow.record_detail(field, value)

    assert flow.state.stage == BancassuranceStage.PLAN_SELECTION

    flow.record_detail("sum_assured_tier", "Tier A ₱500,000")
    flow.record_detail("preferred_payment_mode", "Monthly")

    assert flow.state.stage == BancassuranceStage.READY_FOR_ADVISOR


# --- Grounded Knowledge & Localized Fallback Tests ---


def test_grounded_product_and_faq_question(ph_knowledge_base: PHKnowledgeBase):
    res = ph_knowledge_base.search(
        "Paano po mag-assign o mag-update ng beneficiary sa aking policy?"
    )
    assert res.available is True
    assert "beneficiary" in res.context.lower()
    assert res.citations
    assert any(c.document_id == "ph_bancassurance_faqs" for c in res.citations)


def test_grounded_sector_specific_objection(ph_knowledge_base: PHKnowledgeBase):
    res = ph_knowledge_base.search(
        "Medyo gipit ako ngayon sa budget, pwede bang i-delay muna ang hulog?"
    )
    assert res.available is True
    assert "grace period" in res.context.lower() or "budget" in res.context.lower()
    assert any(c.document_id == "ph_common_objections" for c in res.citations)


def test_unsupported_question_returns_localized_fallback(
    ph_knowledge_base: PHKnowledgeBase,
):
    res = ph_knowledge_base.search("May flight booking ba kayo papuntang Tokyo?")
    assert res.available is False
    assert res.citations == []
    assert res.context == FALLBACK_MESSAGES[LanguageRegister.TAGLISH]


def test_language_registers_for_fallback(ph_knowledge_base: PHKnowledgeBase):
    # English
    en_res = ph_knowledge_base.search(
        "Weather forecast in Boracay island tomorrow afternoon",
        language=LanguageRegister.ENGLISH,
    )
    assert en_res.available is False
    assert en_res.context == FALLBACK_MESSAGES[LanguageRegister.ENGLISH]
    assert en_res.language == LanguageRegister.ENGLISH

    # Taglish
    taglish_res = ph_knowledge_base.search(
        "May flight booking ba kayo papuntang Tokyo?",
        language=LanguageRegister.TAGLISH,
    )
    assert taglish_res.available is False
    assert taglish_res.context == FALLBACK_MESSAGES[LanguageRegister.TAGLISH]
    assert taglish_res.language == LanguageRegister.TAGLISH

    # Filipino
    fil_res = ph_knowledge_base.search(
        "Weather forecast Boracay Batanes bagyo bukas",
        language=LanguageRegister.FILIPINO,
    )
    assert fil_res.available is False
    assert fil_res.context == FALLBACK_MESSAGES[LanguageRegister.FILIPINO]
    assert fil_res.language == LanguageRegister.FILIPINO


# --- Human Escalation Tests ---


def test_human_escalation_records_structured_event_without_false_promise():
    flow = PHLeadFlow()
    flow.begin()
    flow.set_language(LanguageRegister.TAGLISH)

    status = flow.request_human_assistance(
        reason="Customer disputing hospital claim deduction",
        urgency="high",
    )

    assert status["escalation_requested"] is True
    assert status["stage"] == BancassuranceStage.ESCALATED.value
    assert len(flow.state.escalations) == 1

    esc = flow.state.escalations[0]
    assert esc.reason == "Customer disputing hospital claim deduction"
    assert esc.preferred_language == "taglish"
    assert esc.urgency == "high"
    assert esc.stage == BancassuranceStage.QUALIFICATION
    assert "no immediate outbound call is guaranteed" in esc.disclaimer
