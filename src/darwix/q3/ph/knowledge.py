"""Grounded Philippines Bancassurance knowledge retrieval with localized fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from darwix.ingest import load_retriever
from darwix.retriever import RetrievalResult, Retriever

DEFAULT_PH_INDEX_PATH = Path("data/q3/index/ph_vector_store.json")


class LanguageRegister(str, Enum):
    ENGLISH = "en"
    TAGLISH = "taglish"
    FILIPINO = "fil"


FALLBACK_MESSAGES = {
    LanguageRegister.ENGLISH: (
        "I don't have that information available in the current bancassurance "
        "policy records. Would you like me to connect you with a Financial Advisor?"
    ),
    LanguageRegister.TAGLISH: (
        "Pasensya na po, wala po sa aming record ang impormasyong iyan ngayon. "
        "Gusto niyo po bang ikonekta ko kayo sa aming Customer Service Officer o "
        "Financial Advisor?"
    ),
    LanguageRegister.FILIPINO: (
        "Ipagpaumanhin po ninyo, wala po sa aming talaan ang impormasyong iyan "
        "sa kasalukuyan. Nais po ba ninyong ikonekta ko kayo sa isang Kawani "
        "ng Bangko o Financial Advisor?"
    ),
}


@dataclass(frozen=True)
class Citation:
    """A source reference returned with a grounded knowledge response."""

    document_id: str
    title: str
    section: Optional[str]
    source: str
    chunk_id: str


@dataclass(frozen=True)
class PHKnowledgeResponse:
    """Retrieval output for Philippines Bancassurance queries with localized fallback."""

    query: str
    available: bool
    context: str
    citations: List[Citation]
    language: LanguageRegister


class PHKnowledgeBase:
    """Adapter connecting the Philippines bancassurance domain to the Q2 vector index."""

    def __init__(
        self,
        retriever: Optional[Retriever] = None,
        index_path: Path | str = DEFAULT_PH_INDEX_PATH,
        top_k: int = 3,
        default_language: LanguageRegister = LanguageRegister.TAGLISH,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        self._retriever = retriever
        self._index_path = Path(index_path)
        self._top_k = top_k
        self.default_language = default_language

    @property
    def retriever(self) -> Optional[Retriever]:
        """Lazy-load the Q2 retriever on the Philippines index."""
        if self._retriever is None:
            if not self._index_path.exists():
                return None
            try:
                self._retriever = load_retriever(
                    self._index_path,
                    top_k=self._top_k,
                )
            except Exception:
                return None
        return self._retriever

    def search(
        self, query: str, language: Optional[LanguageRegister | str] = None
    ) -> PHKnowledgeResponse:
        """Search the PH corpus or return a localized unavailable-information fallback."""
        register = _resolve_language(language or self.default_language)
        cleaned_query = str(query or "").strip()
        fallback_text = FALLBACK_MESSAGES[register]

        if not cleaned_query:
            return PHKnowledgeResponse(
                query=cleaned_query,
                available=False,
                context=fallback_text,
                citations=[],
                language=register,
            )

        try:
            retriever = self.retriever
            if retriever is None:
                return PHKnowledgeResponse(
                    query=cleaned_query,
                    available=False,
                    context=fallback_text,
                    citations=[],
                    language=register,
                )

            response = retriever.retrieve(cleaned_query)
            if not response.has_results:
                return PHKnowledgeResponse(
                    query=response.query,
                    available=False,
                    context=fallback_text,
                    citations=[],
                    language=register,
                )

            return PHKnowledgeResponse(
                query=response.query,
                available=True,
                context=_format_context(response.results),
                citations=[_citation_from_result(r) for r in response.results],
                language=register,
            )
        except Exception:
            return PHKnowledgeResponse(
                query=cleaned_query,
                available=False,
                context=fallback_text,
                citations=[],
                language=register,
            )


def _resolve_language(lang: LanguageRegister | str) -> LanguageRegister:
    if isinstance(lang, LanguageRegister):
        return lang
    normalized = str(lang).strip().lower()
    if normalized in ("en", "english"):
        return LanguageRegister.ENGLISH
    if normalized in ("fil", "filipino", "tl", "tagalog"):
        return LanguageRegister.FILIPINO
    return LanguageRegister.TAGLISH


def _citation_from_result(result: RetrievalResult) -> Citation:
    return Citation(
        document_id=result.document_id,
        title=result.title,
        section=result.section,
        source=result.source,
        chunk_id=result.chunk_id,
    )


def _format_context(results: List[RetrievalResult]) -> str:
    passages = []
    for result in results:
        location = result.section or "document overview"
        passages.append(
            f"Source: {result.title} — {location}\n{result.content}"
        )
    return "\n\n".join(passages)
