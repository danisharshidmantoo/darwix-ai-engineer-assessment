from pathlib import Path

import pytest

from darwix.chunker import ChunkerConfig
from darwix.embeddings import HashedNgramEmbedding
from darwix.schema import Chunk
from darwix.vector_store import VectorStore


def _chunk(chunk_id: str, text: str, doc_id: str = "d1") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        text=text,
        position=int(chunk_id.rsplit("::", 1)[-1]),
        title="Title",
        source_path="docs/d1.md",
        source_format="markdown",
        doc_type="faq",
        section="Section",
        metadata={"is_synthetic": True},
    )


def test_add_and_search_orders_by_descending_score():
    embedder = HashedNgramEmbedding(dimensions=64)
    chunks = [
        _chunk("d1::0000", "The internship is paid in this synthetic scenario."),
        _chunk("d1::0001", "Applicants must commit twenty hours each week."),
        _chunk("d1::0002", "Unrelated gardening instructions for tomatoes."),
    ]
    store = VectorStore(embedder.config, ChunkerConfig(80, 20))
    store.add(chunks, embedder.embed([c.text for c in chunks]))

    query = embedder.embed_one("Is this internship paid?")
    hits = store.search(query, top_k=3)

    assert len(hits) == 3
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert hits[0].chunk.chunk_id == "d1::0000"
    assert hits[0].score > hits[1].score


def test_persistence_reload_preserves_vectors_and_metadata(tmp_path: Path):
    embedder = HashedNgramEmbedding()
    chunk = _chunk("job_description::0000", "The intern will write unit tests.")
    store = VectorStore(embedder.config, ChunkerConfig(700, 120))
    store.add([chunk], [embedder.embed_one(chunk.text)])

    path = tmp_path / "index" / "vector_store.json"
    store.save(path)

    loaded = VectorStore.load(path)
    assert loaded.embedding_config == embedder.config
    assert loaded.chunker_config == ChunkerConfig(700, 120)
    assert len(loaded) == 1

    hits = loaded.search(embedder.embed_one(chunk.text), top_k=1)
    assert hits[0].chunk.chunk_id == chunk.chunk_id
    assert hits[0].chunk.metadata["is_synthetic"] is True
    assert hits[0].chunk.section == "Section"
    assert abs(hits[0].score - 1.0) < 1e-9


def test_dimension_mismatch_is_rejected():
    embedder = HashedNgramEmbedding(dimensions=32)
    store = VectorStore(embedder.config)
    chunk = _chunk("d1::0000", "hello")
    with pytest.raises(ValueError, match="expected 32"):
        store.add([chunk], [[0.1, 0.2]])
