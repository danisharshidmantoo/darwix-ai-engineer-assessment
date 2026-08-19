"""Verification tests for the Phase 3 Philippines Bancassurance synthetic corpus."""

import re
from pathlib import Path

import pytest

from darwix.ingest import build_index, load_retriever
from darwix.loaders.markdown_loader import MarkdownLoader

PH_DOCS_DIR = Path(__file__).resolve().parents[1] / "data" / "q3" / "ph_docs"


def test_ph_documents_load_successfully():
    loader = MarkdownLoader()
    docs = loader.load_directory(PH_DOCS_DIR, pattern="*.md")

    assert len(docs) == 6
    doc_ids = {doc.doc_id for doc in docs}
    expected_doc_ids = {
        "ph_protectplus_product",
        "ph_lead_qualification",
        "ph_premium_payment_policy",
        "ph_bancassurance_faqs",
        "ph_common_objections",
        "ph_human_escalation",
    }
    assert doc_ids == expected_doc_ids

    for doc in docs:
        assert doc.metadata.get("is_synthetic") is True
        assert doc.metadata.get("market") == "PH"
        assert doc.raw_content
        assert "SYNTHETIC ASSESSMENT DATA" in doc.raw_content


def test_ph_required_categories_and_content_exist():
    loader = MarkdownLoader()
    docs = loader.load_directory(PH_DOCS_DIR, pattern="*.md")
    categories = {doc.doc_type for doc in docs}

    expected_categories = {
        "product_coverage",
        "lead_qualification",
        "payment_policy",
        "faqs",
        "common_objections",
        "escalation_policy",
    }
    assert categories == expected_categories

    corpus_text = " ".join(doc.raw_content.lower() for doc in docs)

    # Key required insurance & bancassurance terminology
    required_terms = [
        "premium",
        "policy",
        "beneficiary",
        "rider",
        "lapse",
        "coverage",
        "bank referral",
        "sum assured",
        "grace period",
        "auto-debit",
        "po",
        "opo",
        "₱",
    ]
    for term in required_terms:
        assert term in corpus_text, f"Expected term {term!r} missing from PH corpus"


def test_ph_utf8_taglish_text_survives_ingestion_and_retrieval(tmp_path: Path):
    index_path = tmp_path / "ph_vector_store.json"
    build_index(docs_dir=PH_DOCS_DIR, index_path=index_path)

    retriever = load_retriever(index_path, top_k=3, min_similarity=0.18)

    # 1. Taglish Beneficiary Query
    bene_res = retriever.retrieve("Paano po mag-assign o mag-update ng beneficiary sa policy?")
    assert bene_res.has_results
    assert any("beneficiary" in hit.content.lower() for hit in bene_res.results)

    # 2. Taglish Objection Query
    obj_res = retriever.retrieve("Medyo gipit ako ngayon sa budget, pwede bang i-delay ang hulog?")
    assert obj_res.has_results
    assert any(
        "grace period" in hit.content.lower() or "budget" in hit.content.lower()
        for hit in obj_res.results
    )

    # 3. Escalation Query
    esc_res = retriever.retrieve("Gusto ko pong makausap ang live agent o Financial Advisor")
    assert esc_res.has_results
    assert any("escalat" in hit.content.lower() or "advisor" in hit.content.lower() for hit in esc_res.results)

    # 4. Intentionally Unsupported / Out-of-Scope Query
    unsupported_res = retriever.retrieve("Will it rain in Boracay tomorrow?")
    assert unsupported_res.has_results is False
    assert unsupported_res.results == []


def test_ph_no_real_pii_present():
    loader = MarkdownLoader()
    docs = loader.load_directory(PH_DOCS_DIR, pattern="*.md")

    # Patterns for potential real PII: phone numbers (+63 / 09XX), email addresses, credit cards
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    phone_pattern = re.compile(r"\b(?:\+63|09)\d{9}\b")
    card_pattern = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")

    for doc in docs:
        assert not email_pattern.search(doc.raw_content), f"Found email in {doc.doc_id}"
        assert not phone_pattern.search(doc.raw_content), f"Found phone in {doc.doc_id}"
        assert not card_pattern.search(doc.raw_content), f"Found card number in {doc.doc_id}"
