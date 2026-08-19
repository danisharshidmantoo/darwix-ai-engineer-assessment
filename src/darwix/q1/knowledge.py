"""Grounded Q1 access to the existing Q2 retriever."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from darwix.ingest import DEFAULT_INDEX_PATH, load_retriever
from darwix.retriever import RetrievalResult, Retriever

UNAVAILABLE_INFORMATION_MESSAGE = (
    "I don't have that information available in the current candidate "
    "information. I can connect you with a human if you'd like."
)


@dataclass(frozen=True)
class Citation:
    """A source reference returned with a grounded knowledge response."""

    document_id: str
    title: str
    section: Optional[str]
    source: str
    chunk_id: str


@dataclass(frozen=True)
class KnowledgeResponse:
    """Tool-safe retrieval output for the Q1 agent and simulations."""

    query: str
    available: bool
    context: str
    citations: List[Citation]

    def to_tool_result(self) -> dict:
        """Return serializable data for a LiveKit function tool."""
        return {
            "available": self.available,
            "context": self.context,
            "citations": [citation.__dict__ for citation in self.citations],
        }


class KnowledgeBase:
    """Small adapter that makes Q2 the only source of business knowledge."""

    def __init__(
        self,
        retriever: Optional[Retriever] = None,
        index_path: Path | str = DEFAULT_INDEX_PATH,
        top_k: int = 3,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        self._retriever = retriever
        self._index_path = Path(index_path)
        self._top_k = top_k

    @property
    def retriever(self) -> Optional[Retriever]:
        """Load the pre-built Q2 index only when knowledge is first needed."""
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

    def search(self, query: str) -> KnowledgeResponse:
        """Retrieve supporting corpus text or return the explicit fallback."""
        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            return KnowledgeResponse(
                query=cleaned_query,
                available=False,
                context=UNAVAILABLE_INFORMATION_MESSAGE,
                citations=[],
            )

        try:
            retriever = self.retriever
            if retriever is None:
                return KnowledgeResponse(
                    query=cleaned_query,
                    available=False,
                    context=UNAVAILABLE_INFORMATION_MESSAGE,
                    citations=[],
                )

            response = retriever.retrieve(cleaned_query)
            if not response.has_results:
                return KnowledgeResponse(
                    query=response.query,
                    available=False,
                    context=UNAVAILABLE_INFORMATION_MESSAGE,
                    citations=[],
                )

            return KnowledgeResponse(
                query=response.query,
                available=True,
                context=_format_context(response.results),
                citations=[_citation_from_result(result) for result in response.results],
            )
        except Exception:
            return KnowledgeResponse(
                query=cleaned_query,
                available=False,
                context=UNAVAILABLE_INFORMATION_MESSAGE,
                citations=[],
            )


def _citation_from_result(result: RetrievalResult) -> Citation:
    return Citation(
        document_id=result.document_id,
        title=result.title,
        section=result.section,
        source=result.source,
        chunk_id=result.chunk_id,
    )


def _format_context(results: List[RetrievalResult]) -> str:
    """Preserve retrieved text and citations for the LLM; do not synthesize facts."""
    passages = []
    for result in results:
        location = result.section or "document overview"
        passages.append(
            f"Source: {result.title} — {location}\n{result.content}"
        )
    return "\n\n".join(passages)
