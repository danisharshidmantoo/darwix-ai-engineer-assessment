from darwix.embeddings import (
    DEFAULT_DIMENSIONS,
    HashedNgramEmbedding,
    cosine_similarity,
    embedding_text_for_chunk,
    provider_from_config,
)
from darwix.schema import Chunk


def test_default_embedding_dimension_is_1024():
    assert DEFAULT_DIMENSIONS == 1024
    assert HashedNgramEmbedding().config.dimensions == 1024


def test_embedding_shape_and_unit_norm():
    embedder = HashedNgramEmbedding(dimensions=64)
    vectors = embedder.embed(["hello world", "another string"])
    assert len(vectors) == 2
    for vec in vectors:
        assert len(vec) == 64
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-9


def test_embeddings_are_deterministic_across_calls_and_instances():
    text = "Eligibility requires 20 hours per week."
    first = HashedNgramEmbedding().embed_one(text)
    second = HashedNgramEmbedding().embed_one(text)
    assert first == second
    assert HashedNgramEmbedding().embed([text, text])[0] == first


def test_config_is_explicit_and_round_trips_through_provider_factory():
    embedder = HashedNgramEmbedding(dimensions=128, ngram_min=3, ngram_max=4)
    cfg = embedder.config
    assert cfg.provider == "hashed_ngram"
    assert cfg.dimensions == 128
    assert cfg.version == 3
    rebuilt = provider_from_config(cfg)
    assert rebuilt.config == cfg
    assert rebuilt.embed_one("paid internship") == embedder.embed_one(
        "paid internship"
    )


def test_similar_phrases_outrank_unrelated_text():
    embedder = HashedNgramEmbedding()
    query = embedder.embed_one("Is the internship paid?")
    related = embedder.embed_one(
        "Yes, in this synthetic scenario the internship is paid."
    )
    unrelated = embedder.embed_one(
        "quantum xylophone banana stapler nebula 99999"
    )
    assert cosine_similarity(query, related) > cosine_similarity(
        query, unrelated
    )
    assert cosine_similarity(query, related) > 0.25
    assert cosine_similarity(query, unrelated) < 0.12


def test_empty_string_returns_zero_vector():
    vec = HashedNgramEmbedding(dimensions=32).embed_one("")
    assert vec == [0.0] * 32


def test_chunk_embedding_text_adds_metadata_without_changing_content():
    chunk = Chunk(
        chunk_id="d::0000",
        doc_id="d",
        text="Python proficiency is required.",
        position=0,
        title="AI Engineer Intern",
        source_path="d.md",
        source_format="markdown",
        doc_type="job_description",
        section="Required qualifications",
        metadata={},
    )

    assert embedding_text_for_chunk(chunk) == (
        "Document title: AI Engineer Intern\n"
        "Section: Required qualifications\n"
        "Content: Python proficiency is required."
    )
