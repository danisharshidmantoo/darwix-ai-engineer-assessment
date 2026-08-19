"""
Offline embedding providers.

The default implementation is a signed character/word n-gram hash into a
fixed-dimensional vector (no network, no model weights, fully
deterministic). A later dense model can implement the same
`EmbeddingProvider` interface without changing the retriever.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Sequence, Tuple

_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")

DEFAULT_DIMENSIONS = 256
DEFAULT_NGRAM_MIN = 3
DEFAULT_NGRAM_MAX = 5
PROVIDER_HASHED_NGRAM = "hashed_ngram"
PROVIDER_VERSION = 2

_CHAR_WEIGHT = 0.35
_WORD_WEIGHT = 6.0
_BIGRAM_WEIGHT = 4.0
_PREFIX_WEIGHT = 2.0

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "with",
        "this",
        "that",
        "it",
        "as",
        "at",
        "by",
        "from",
        "if",
        "do",
        "does",
        "can",
        "i",
        "you",
        "we",
        "my",
        "your",
        "our",
        "will",
        "should",
        "what",
        "how",
        "when",
        "where",
    }
)


@dataclass(frozen=True)
class EmbeddingConfig:
    """Parameters that must match between indexing and retrieval."""

    provider: str
    dimensions: int
    version: int
    ngram_min: int = DEFAULT_NGRAM_MIN
    ngram_max: int = DEFAULT_NGRAM_MAX

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "dimensions": self.dimensions,
            "version": self.version,
            "ngram_min": self.ngram_min,
            "ngram_max": self.ngram_max,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EmbeddingConfig":
        return cls(
            provider=data["provider"],
            dimensions=int(data["dimensions"]),
            version=int(data["version"]),
            ngram_min=int(data.get("ngram_min", DEFAULT_NGRAM_MIN)),
            ngram_max=int(data.get("ngram_max", DEFAULT_NGRAM_MAX)),
        )


class EmbeddingProvider(ABC):
    """Swappable embedding backend used by ingest and retrieval."""

    @property
    @abstractmethod
    def config(self) -> EmbeddingConfig:
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Return one L2-normalized vector per input string."""
        raise NotImplementedError

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]


class HashedNgramEmbedding(EmbeddingProvider):
    """Deterministic hashed n-gram encoder (character 3-5 + word 1-2)."""

    def __init__(
        self,
        dimensions: int = DEFAULT_DIMENSIONS,
        ngram_min: int = DEFAULT_NGRAM_MIN,
        ngram_max: int = DEFAULT_NGRAM_MAX,
        version: int = PROVIDER_VERSION,
    ) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be a positive integer")
        if ngram_min < 1 or ngram_max < ngram_min:
            raise ValueError("ngram_min/ngram_max are invalid")

        self._config = EmbeddingConfig(
            provider=PROVIDER_HASHED_NGRAM,
            dimensions=dimensions,
            version=version,
            ngram_min=ngram_min,
            ngram_max=ngram_max,
        )

    @property
    def config(self) -> EmbeddingConfig:
        return self._config

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [_vectorize(text, self._config) for text in texts]


def provider_from_config(config: EmbeddingConfig) -> EmbeddingProvider:
    """Rebuild the provider recorded in a persisted index."""
    if config.provider == PROVIDER_HASHED_NGRAM:
        return HashedNgramEmbedding(
            dimensions=config.dimensions,
            ngram_min=config.ngram_min,
            ngram_max=config.ngram_max,
            version=config.version,
        )
    raise ValueError(f"Unknown embedding provider: {config.provider!r}")


def _normalize_for_embed(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.lower()).strip()


def _char_ngrams(text: str, n_min: int, n_max: int) -> List[str]:
    grams: List[str] = []
    for n in range(n_min, n_max + 1):
        if len(text) < n:
            continue
        grams.extend(text[i : i + n] for i in range(len(text) - n + 1))
    return grams


def _stem(token: str) -> str:
    if len(token) <= 3:
        return token
    for suffix in ("ility", "ment", "tion", "ions", "ing", "ies", "ily", "ly", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _content_tokens(text: str) -> List[str]:
    tokens = [_stem(tok) for tok in _TOKEN_RE.findall(text)]
    return [tok for tok in tokens if tok not in _STOPWORDS and len(tok) > 1]


def _word_features(text: str) -> List[Tuple[str, float]]:
    tokens = _content_tokens(text)
    features: List[Tuple[str, float]] = [(f"w1:{tok}", _WORD_WEIGHT) for tok in tokens]
    features.extend(
        (f"w2:{tokens[i]}_{tokens[i + 1]}", _BIGRAM_WEIGHT)
        for i in range(len(tokens) - 1)
    )
    for tok in tokens:
        if len(tok) >= 5:
            features.append((f"p5:{tok[:5]}", _PREFIX_WEIGHT))
    return features


def _signed_index(feature: str, dimensions: int) -> Tuple[int, float]:
    digest = hashlib.sha256(feature.encode("utf-8")).digest()
    idx = int.from_bytes(digest[:4], "big") % dimensions
    sign = 1.0 if digest[4] < 128 else -1.0
    return idx, sign


def _vectorize(text: str, config: EmbeddingConfig) -> List[float]:
    dim = config.dimensions
    vec = [0.0] * dim
    normalized = _normalize_for_embed(text)
    if not normalized:
        return vec

    weighted: List[Tuple[str, float]] = [
        (gram, _CHAR_WEIGHT)
        for gram in _char_ngrams(normalized, config.ngram_min, config.ngram_max)
    ]
    weighted.extend(_word_features(normalized))
    for feature, weight in weighted:
        idx, sign = _signed_index(feature, dim)
        vec[idx] += sign * weight

    return _l2_normalize(vec)


def _l2_normalize(vec: Sequence[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return list(vec)
    return [v / norm for v in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("cosine_similarity requires equal-length vectors")
    return float(sum(x * y for x, y in zip(a, b)))
