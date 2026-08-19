from darwix.embeddings import (
    HashedNgramEmbedding,
    cosine_similarity,
    provider_from_config,
)


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
    assert cfg.version == 2
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
