"""Verification tests for the Phase 3 Indonesia Pembiayaan synthetic corpus."""

import re
from pathlib import Path

import pytest

from darwix.ingest import build_index, load_retriever
from darwix.loaders.markdown_loader import MarkdownLoader

ID_DOCS_DIR = Path(__file__).resolve().parents[1] / "data" / "q3" / "id_docs"


def test_id_documents_load_successfully():
    loader = MarkdownLoader()
    docs = loader.load_directory(ID_DOCS_DIR, pattern="*.md")

    assert len(docs) == 6
    doc_ids = {doc.doc_id for doc in docs}
    expected_doc_ids = {
        "id_product_pembiayaan",
        "id_lead_qualification",
        "id_payment_policy",
        "id_faqs",
        "id_common_objections",
        "id_human_escalation",
    }
    assert doc_ids == expected_doc_ids

    for doc in docs:
        assert doc.metadata.get("is_synthetic") is True
        assert doc.metadata.get("market") == "ID"
        assert doc.raw_content
        assert "SINTETIS" in doc.raw_content.upper() or "SYNTHETIC" in doc.raw_content.upper()


def test_id_required_categories_and_content_exist():
    loader = MarkdownLoader()
    docs = loader.load_directory(ID_DOCS_DIR, pattern="*.md")
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

    # Key required Indonesian finance terminology (including loanwords and colloquial)
    required_terms = [
        "cicilan",
        "angsuran",
        "tenor",
        "denda",
        "dp",
        "jatuh tempo",
        "pembiayaan",
        "down payment",
        "autodebit",
        "rp",
    ]
    for term in required_terms:
        assert term in corpus_text, f"Expected term {term!r} missing from ID corpus"


def test_id_utf8_indonesian_text_survives_ingestion_and_retrieval(tmp_path: Path):
    index_path = tmp_path / "id_vector_store.json"
    build_index(docs_dir=ID_DOCS_DIR, index_path=index_path)

    retriever = load_retriever(index_path, top_k=3, min_similarity=0.18)

    # 1. Qualification Query (formal)
    q1 = "Apa persyaratan penghasilan untuk mengajukan pembiayaan konsumer?"
    res1 = retriever.retrieve(q1)
    assert res1.has_results
    # Accept a range of relevant keywords in results since retrieval may return product or faq chunks
    assert any(
        any(k in hit.content.lower() for k in ["persyaratan", "penghasilan", "kualifikasi", "kriteria", "dp", "tenor", "angsuran"])
        for hit in res1.results
    )

    # 2. Colloquial objection / installment question
    q2 = "Gak kuat cicilan nih, bisa minta tenor panjang?"
    res2 = retriever.retrieve(q2)
    assert res2.has_results
    assert any("tenor" in hit.content.lower() or "cicilan" in hit.content.lower() or "angsuran" in hit.content.lower() for hit in res2.results)

    # 3. Escalation request
    q3 = "Saya mau ngobrol sama agen atau live agent"
    res3 = retriever.retrieve(q3)
    assert res3.has_results
    assert any("escalat" in hit.content.lower() or "agen" in hit.content.lower() or "live agent" in hit.content.lower() for hit in res3.results)

    # 4. Intentionally unsupported / Out-of-Scope Query
    unsupported_res = retriever.retrieve("What is the best surfing spot in Bali?")
    assert unsupported_res.has_results is False
    assert unsupported_res.results == []


def test_id_no_real_pii_present():
    loader = MarkdownLoader()
    docs = loader.load_directory(ID_DOCS_DIR, pattern="*.md")

    # Patterns for potential real PII: phone numbers (+62 / 08...), email addresses, credit cards
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    phone_pattern = re.compile(r"\b(?:\+62|08)\d{6,12}\b")
    card_pattern = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")

    for doc in docs:
        assert not email_pattern.search(doc.raw_content), f"Found email in {doc.doc_id}"
        assert not phone_pattern.search(doc.raw_content), f"Found phone in {doc.doc_id}"
        assert not card_pattern.search(doc.raw_content), f"Found card number in {doc.doc_id}"
