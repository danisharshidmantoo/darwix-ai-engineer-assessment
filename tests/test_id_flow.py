"""Tests for the Indonesia deterministic domain flow and knowledge adapter."""

from pathlib import Path

import pytest

from darwix.q3.id.flow import (
    IDLeadFlow,
    IDLeadState,
    QualificationStatus,
    IDEscalationEvent,
)
from darwix.q3.id.knowledge import IDKnowledgeBase, LanguageRegister


def test_eligible_customer():
    state = IDLeadState()
    flow = IDLeadFlow(state)
    flow.begin()
    flow.record_detail("age", "30")
    flow.record_detail("residency", "Tinggal di Indonesia")
    flow.record_detail("identity_document", "KTP 1234xxxx")
    flow.record_detail("income", "Rp5000000")
    flow.record_detail("bank_account_holder", "Ya, pemegang rekening")
    # plan fields
    flow.record_detail("dp", "10%")
    flow.record_detail("tenor", "12")

    status = flow.status()
    assert status["qualification_status"] == QualificationStatus.READY_FOR_ADVISOR.value
    assert status["is_eligible"] is True


def test_ineligible_customer_low_income():
    flow = IDLeadFlow()
    flow.begin()
    flow.record_detail("age", "40")
    flow.record_detail("residency", "Tinggal di Indonesia")
    flow.record_detail("identity_document", "KTP")
    flow.record_detail("income", "Rp1500000")
    flow.record_detail("bank_account_holder", "Ya")

    status = flow.status()
    assert status["qualification_status"] == QualificationStatus.INELIGIBLE.value
    assert status["is_eligible"] is False
    assert any("penghasilan" in v.lower() for v in status["hard_requirement_violations"])


def test_incomplete_qualification():
    flow = IDLeadFlow()
    flow.begin()
    flow.record_detail("age", "29")
    flow.record_detail("residency", "Tinggal di Indonesia")
    # missing identity_document, income, bank_account_holder

    status = flow.status()
    assert status["qualification_status"] == QualificationStatus.INCOMPLETE.value
    assert "identity_document" in status["missing_mandatory_fields"]


def test_conflict_detection_and_resolution():
    flow = IDLeadFlow()
    flow.begin()
    flow.record_detail("age", "30")
    flow.record_detail("income", "Rp4000000")
    # conflicting age
    flow.record_detail("age", "35")
    status = flow.status()
    assert status["qualification_status"] == QualificationStatus.CONFLICTING.value
    assert len(status["conflicts"]) >= 1

    # resolve conflict
    flow.resolve_conflict("age", "35")
    status2 = flow.status()
    assert status2["qualification_status"] in (QualificationStatus.INCOMPLETE.value, QualificationStatus.READY_FOR_ADVISOR.value)


def test_grounded_product_faq_retrieval():
    kb = IDKnowledgeBase()
    # query that should be present in id_faqs
    res = kb.search("Apa itu tenor?", language=LanguageRegister.FORMAL)
    assert res.available is True
    assert len(res.citations) > 0
    assert "tenor" in res.context.lower()


def test_installment_objection_retrieval_colloquial():
    kb = IDKnowledgeBase()
    res = kb.search("Gak kuat cicilan nih, bisa minta tenor panjang?", language=LanguageRegister.COLLOQUIAL)
    assert res.available is True
    # Ensure retrieved context or citations contain installment terminology
    assert res.available is True
    assert ("cicilan" in res.context.lower()) or ("angsuran" in res.context.lower()) or any("cicilan" in c.title.lower() or "angsuran" in c.title.lower() for c in res.citations)


def test_unsupported_question_localized_fallbacks():
    kb = IDKnowledgeBase()
    res_formal = kb.search("Berapa tarif parkir di mall?", language=LanguageRegister.FORMAL)
    assert res_formal.available is False
    assert "maaf" in res_formal.context.lower()

    res_col = kb.search("Eh, ada promo ga buat parkiran?", language=LanguageRegister.COLLOQUIAL)
    assert res_col.available is False
    assert "sambungkan" in res_col.context.lower() or "agen" in res_col.context.lower()


def test_human_escalation_recording_and_language_preservation():
    flow = IDLeadFlow()
    flow.begin()
    flow.set_language(LanguageRegister.COLLOQUIAL)
    flow.request_human_assistance("Saya mau live agent", urgency="high")
    status = flow.status()
    assert status["escalation_requested"] is True
    assert len(status["details"]) == 0
    assert status["language"] == LanguageRegister.COLLOQUIAL.value


def test_finance_terminology_code_switching_behavior():
    kb = IDKnowledgeBase()
    # Mixed English/Indonesian query
    res = kb.search("What is DP and how much down payment needed?", language=LanguageRegister.MIXED)
    # Should return fallback or available; we accept either but ensure language preserved
    assert res.language == LanguageRegister.MIXED
