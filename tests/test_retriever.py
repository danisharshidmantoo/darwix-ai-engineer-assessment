from pathlib import Path

import pytest

from darwix.embeddings import HashedNgramEmbedding
from darwix.ingest import build_index, load_retriever
from darwix.retriever import Retriever
from darwix.schema import Chunk
from darwix.vector_store import VectorStore

CORPUS_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic_docs"


def _tiny_store(texts):
    embedder = HashedNgramEmbedding()
    chunks = [
        Chunk(
            chunk_id=f"d::{i:04d}",
            doc_id="d",
            text=text,
            position=i,
            title="T",
            source_path="x.md",
            source_format="markdown",
            doc_type="faq",
            section="S",
            metadata={"is_synthetic": True},
        )
        for i, text in enumerate(texts)
    ]
    store = VectorStore(embedder.config)
    store.add(chunks, embedder.embed(texts))
    return store, embedder


def test_empty_query_is_rejected():
    store, embedder = _tiny_store(["hello world"])
    retriever = Retriever(store, embedder, min_similarity=0.0)
    with pytest.raises(ValueError, match="non-empty"):
        retriever.retrieve("   ")
    with pytest.raises(ValueError, match="non-empty"):
        retriever.retrieve("")


def test_incompatible_embedder_config_is_rejected():
    store, _ = _tiny_store(["hello world"])
    other = HashedNgramEmbedding(dimensions=64)
    with pytest.raises(ValueError, match="does not match"):
        Retriever(store, other)


def test_min_similarity_filters_weak_matches():
    store, embedder = _tiny_store(
        [
            "Yes, in this synthetic scenario the internship is paid.",
            "Garden tomatoes need full sun and well drained soil.",
        ]
    )
    open_retriever = Retriever(store, embedder, top_k=5, min_similarity=0.0)
    strict = Retriever(store, embedder, top_k=5, min_similarity=0.2)

    query = "Is the internship paid?"
    open_hits = open_retriever.retrieve(query).results
    strict_hits = strict.retrieve(query).results

    assert open_hits[0].document_id == "d"
    assert open_hits[0].score >= open_hits[-1].score
    assert all(h.score >= 0.2 for h in strict_hits)
    assert strict_hits[0].content.startswith("Yes, in this synthetic")


def test_corpus_faq_and_policy_queries_return_grounded_chunks(tmp_path: Path):
    index_path = tmp_path / "vector_store.json"
    build_index(docs_dir=CORPUS_DIR, index_path=index_path)
    retriever = load_retriever(index_path, top_k=3, min_similarity=0.18)

    paid = retriever.retrieve("Is this internship paid?")
    assert paid.has_results
    assert paid.results[0].document_id == "candidate_faqs"
    assert "paid" in paid.results[0].content.lower()
    _assert_result_metadata(paid.results[0])

    hours = retriever.retrieve("What is the minimum weekly hour commitment?")
    assert hours.has_results
    hour_docs = {hit.document_id for hit in hours.results}
    assert hour_docs & {
        "eligibility_policy",
        "candidate_faqs",
        "common_objections",
    }
    assert any(
        "20" in hit.content and "hour" in hit.content.lower()
        for hit in hours.results
    )

    remote = retriever.retrieve("Can I do this internship remotely?")
    assert remote.has_results
    assert remote.results[0].document_id == "candidate_faqs"

    scores = [hit.score for hit in paid.results]
    assert scores == sorted(scores, reverse=True)


def test_nonsense_query_returns_no_relevant_results(tmp_path: Path):
    index_path = tmp_path / "vector_store.json"
    build_index(docs_dir=CORPUS_DIR, index_path=index_path)
    retriever = load_retriever(index_path, top_k=5, min_similarity=0.18)

    response = retriever.retrieve(
        "xylophone quantum banana stapler nebula 99999 zxcvbn"
    )
    assert response.results == []
    assert response.has_results is False


def test_full_ingest_reload_retrieval_round_trip(tmp_path: Path):
    index_path = tmp_path / "idx.json"
    first = build_index(docs_dir=CORPUS_DIR, index_path=index_path)
    snapshot = index_path.read_bytes()
    second = build_index(docs_dir=CORPUS_DIR, index_path=index_path)
    assert index_path.read_bytes() == snapshot
    assert len(first) == len(second)
    assert first.embedding_config == second.embedding_config

    reloaded = VectorStore.load(index_path)
    assert len(reloaded) == len(first)
    assert reloaded.embedding_config.to_dict() == first.embedding_config.to_dict()

    retriever = load_retriever(index_path)
    result = retriever.retrieve("Who is not eligible to apply?")
    assert result.has_results
    doc_ids = {hit.document_id for hit in result.results}
    assert "eligibility_policy" in doc_ids
    assert any("not eligible" in hit.content.lower() for hit in result.results)
    _assert_result_metadata(result.results[0])


def _assert_result_metadata(result):
    assert result.chunk_id
    assert result.document_id
    assert result.title
    assert result.source
    assert result.content
    assert isinstance(result.score, float)
    assert 0.0 <= result.score <= 1.0
    assert result.doc_type
    assert "is_synthetic" in result.metadata
    assert result.metadata["is_synthetic"] is True
