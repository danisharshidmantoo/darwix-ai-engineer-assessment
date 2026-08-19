"""
Persistent local vector store.

Stores L2-normalized embeddings plus chunk metadata as JSON. No extra
packages (Chroma/FAISS/numpy) are required; the synthetic corpus is small
enough that brute-force cosine search is exact and reproducible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from darwix.chunker import ChunkerConfig
from darwix.embeddings import EmbeddingConfig, cosine_similarity
from darwix.schema import Chunk


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float


class VectorStore:
    def __init__(
        self,
        embedding_config: EmbeddingConfig,
        chunker_config: Optional[ChunkerConfig] = None,
    ) -> None:
        self.embedding_config = embedding_config
        self.chunker_config = chunker_config
        self._items: List[Dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self._items)

    def add(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        dim = self.embedding_config.dimensions
        for chunk, embedding in zip(chunks, embeddings):
            if len(embedding) != dim:
                raise ValueError(
                    f"Embedding for {chunk.chunk_id} has length "
                    f"{len(embedding)}, expected {dim}"
                )
            self._items.append(
                {
                    "chunk": chunk.to_dict(),
                    "embedding": [float(x) for x in embedding],
                }
            )

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int = 5,
        min_similarity: Optional[float] = None,
    ) -> List[ScoredChunk]:
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if len(query_embedding) != self.embedding_config.dimensions:
            raise ValueError(
                "Query embedding dimensions do not match the store "
                f"({len(query_embedding)} != {self.embedding_config.dimensions})"
            )

        scored: List[ScoredChunk] = []
        for item in self._items:
            score = cosine_similarity(query_embedding, item["embedding"])
            if min_similarity is None or score >= min_similarity:
                scored.append(
                    ScoredChunk(
                        chunk=Chunk.from_dict(item["chunk"]),
                        score=score,
                    )
                )

        scored.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
        return scored[:top_k]

    def save(self, path: Union[str, Path]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "embedding": self.embedding_config.to_dict(),
            "chunker": (
                self.chunker_config.to_dict() if self.chunker_config else None
            ),
            "items": self._items,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Union[str, Path]) -> "VectorStore":
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        embedding_config = EmbeddingConfig.from_dict(payload["embedding"])
        chunker_raw = payload.get("chunker")
        chunker_config = (
            ChunkerConfig(
                chunk_size=int(chunker_raw["chunk_size"]),
                chunk_overlap=int(chunker_raw["chunk_overlap"]),
            )
            if chunker_raw
            else None
        )
        store = cls(embedding_config, chunker_config)
        items = payload.get("items") or []
        if not isinstance(items, list):
            raise ValueError("Persisted index 'items' must be a list")
        store._items = items
        return store
