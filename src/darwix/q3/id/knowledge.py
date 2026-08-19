"""Grounded Indonesia Pembiayaan knowledge retrieval with localized fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from darwix.ingest import load_retriever
from darwix.retriever import RetrievalResult, Retriever

DEFAULT_ID_INDEX_PATH = Path("data/q3/index/id_vector_store.json")


class LanguageRegister(str, Enum):
    FORMAL = "id"
    COLLOQUIAL = "id-col"
    MIXED = "id-mix"


FALLBACK_MESSAGES = {
    LanguageRegister.FORMAL: (
        "Maaf, informasi tersebut tidak tersedia dalam catatan kebijakan pembiayaan kami saat ini. "
        "Apakah Anda ingin saya menghubungkan Anda ke agen manusia untuk bantuan lebih lanjut?"
    ),
    LanguageRegister.COLLOQUIAL: (
        "Wah, maaf nih, informasinya nggak ada di data kita sekarang. Mau saya sambungkan ke agen aja?"
    ),
    LanguageRegister.MIXED: (
        "Sorry, info not found in our financing records. Mau connect ke agen manusia?"
    ),
}


@dataclass(frozen=True)
class Citation:
    document_id: str
    title: str
    section: Optional[str]
    source: str
    chunk_id: str


@dataclass(frozen=True)
class IDKnowledgeResponse:
    query: str
    available: bool
    context: str
    citations: List[Citation]
    language: LanguageRegister


class IDKnowledgeBase:
    """Adapter connecting the Indonesia pembiayaan domain to the Q2 vector index."""

    def __init__(
        self,
        retriever: Optional[Retriever] = None,
        index_path: Path | str = DEFAULT_ID_INDEX_PATH,
        top_k: int = 3,
        default_language: LanguageRegister = LanguageRegister.FORMAL,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        self._retriever = retriever
        self._index_path = Path(index_path)
        self._top_k = top_k
        self.default_language = default_language

    @property
    def retriever(self) -> Optional[Retriever]:
        """Lazy-load the Q2 retriever on the Indonesia index."""
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

    def _resolve_language(self, language: Optional[LanguageRegister | str]) -> LanguageRegister:
        if isinstance(language, LanguageRegister):
            return language
        if language is None:
            return self.default_language
        normalized = str(language).strip().lower()
        if normalized in ("colloquial", "col", "id-col"):
            return LanguageRegister.COLLOQUIAL
        if normalized in ("mix", "mixed", "id-mix"):
            return LanguageRegister.MIXED
        return LanguageRegister.FORMAL

    def search(self, query: str, language: Optional[LanguageRegister | str] = None) -> IDKnowledgeResponse:
        """Search the ID corpus or return a localized unavailable-information fallback."""
        register = self._resolve_language(language)
        cleaned_query = str(query or "").strip()
        fallback_text = FALLBACK_MESSAGES[register]

        if not cleaned_query:
            return IDKnowledgeResponse(
                query=cleaned_query,
                available=False,
                context=fallback_text,
                citations=[],
                language=register,
            )

        try:
            retriever = self.retriever
            if retriever is None:
                return IDKnowledgeResponse(
                    query=cleaned_query,
                    available=False,
                    context=fallback_text,
                    citations=[],
                    language=register,
                )

            response = retriever.retrieve(cleaned_query)
            if not response.has_results:
                return IDKnowledgeResponse(
                    query=response.query,
                    available=False,
                    context=fallback_text,
                    citations=[],
                    language=register,
                )

            return IDKnowledgeResponse(
                query=response.query,
                available=True,
                context=self._format_context(response.results),
                citations=[self._citation_from_result(r) for r in response.results],
                language=register,
            )
        except Exception:
            return IDKnowledgeResponse(
                query=cleaned_query,
                available=False,
                context=fallback_text,
                citations=[],
                language=register,
            )

    def _citation_from_result(self, result: RetrievalResult) -> Citation:
        return Citation(
            document_id=result.document_id,
            title=result.title,
            section=result.section,
            source=result.source,
            chunk_id=result.chunk_id,
        )

    def _format_context(self, results: List[RetrievalResult]) -> str:
        passages = []
        for result in results:
            location = result.section or "ringkasan dokumen"
            passages.append(f"Sumber: {result.title} — {location}\n{result.content}")
        return "\n\n".join(passages)
