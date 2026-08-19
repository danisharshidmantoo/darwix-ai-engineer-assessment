"""
Semantic top-k retrieval over a persisted `VectorStore`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from darwix.embeddings import EmbeddingConfig, EmbeddingProvider
from darwix.vector_store import VectorStore

DEFAULT_TOP_K = 5
DEFAULT_MIN_SIMILARITY = 0.18


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    title: str
    source: str
    section: Optional[str]
    content: str
    score: float
    doc_type: str
    position: int
    metadata: dict


@dataclass
class RetrievalResponse:
    query: str
    results: List[RetrievalResult]

    @property
    def has_results(self) -> bool:
        return bool(self.results)


class Retriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: EmbeddingProvider,
        top_k: int = DEFAULT_TOP_K,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if not 0.0 <= min_similarity <= 1.0:
            raise ValueError("min_similarity must be between 0 and 1")

        _assert_compatible(store.embedding_config, embedder.config)
        self.store = store
        self.embedder = embedder
        self.top_k = top_k
        self.min_similarity = min_similarity

    def retrieve(self, query: str) -> RetrievalResponse:
        if query is None or not str(query).strip():
            raise ValueError("Query must be a non-empty string")

        cleaned_query = str(query).strip()
        query_embedding = self.embedder.embed_one(cleaned_query)
        hits = self.store.search(
            query_embedding,
            top_k=self.top_k,
            min_similarity=self.min_similarity,
        )
        results = [
            RetrievalResult(
                chunk_id=hit.chunk.chunk_id,
                document_id=hit.chunk.doc_id,
                title=hit.chunk.title,
                source=hit.chunk.source_path,
                section=hit.chunk.section,
                content=hit.chunk.text,
                score=hit.score,
                doc_type=hit.chunk.doc_type,
                position=hit.chunk.position,
                metadata=dict(hit.chunk.metadata),
            )
            for hit in hits
        ]
        return RetrievalResponse(query=cleaned_query, results=results)


def _assert_compatible(stored: EmbeddingConfig, current: EmbeddingConfig) -> None:
    if stored != current:
        raise ValueError(
            "Embedding configuration on the index does not match the "
            f"retriever provider (index={stored.to_dict()}, "
            f"provider={current.to_dict()}). Rebuild the index."
        )
