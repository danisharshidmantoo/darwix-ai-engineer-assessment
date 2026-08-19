"""
Shared document schema.

Every loader (Markdown today, PDF/web later) must produce `Document`
objects. Downstream stages (cleaning, chunking, embedding, retrieval)
depend only on this schema, never on how the document was ingested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class Document:
    """A single source document in the knowledge corpus.

    Attributes:
        doc_id: Stable, unique identifier for the document (e.g.
            "job_description"). Used later as a citation key.
        title: Human-readable title, shown in citations/answers.
        doc_type: Category of the document (e.g. "job_description",
            "eligibility_policy"). Free-form but expected to be one of
            the categories used by the synthetic corpus.
        source_path: Filesystem (or later, URL) path the document was
            loaded from.
        source_format: Format the document was ingested from
            ("markdown", "pdf", "web", ...). Lets downstream code stay
            agnostic to ingestion format.
        raw_content: The document body exactly as extracted, before any
            cleaning.
        cleaned_content: The normalized body, populated by
            `darwix.cleaning.clean_document`. `None` until cleaning runs.
        metadata: Arbitrary metadata carried from the source (front
            matter fields, ingestion-time stats, etc.). Not meant to be
            exhaustive or schema-locked — later stages read from it, they
            don't own it.
        loaded_at: ISO-8601 UTC timestamp of when this object was built.
    """

    doc_id: str
    title: str
    doc_type: str
    source_path: str
    source_format: str
    raw_content: str
    cleaned_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    loaded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not self.doc_id or not self.doc_id.strip():
            raise ValueError("Document.doc_id must be a non-empty string")
        if not self.raw_content or not self.raw_content.strip():
            raise ValueError(
                f"Document '{self.doc_id}' has empty raw_content"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Plain-dict representation, useful for logging/serialization."""
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "doc_type": self.doc_type,
            "source_path": self.source_path,
            "source_format": self.source_format,
            "raw_content": self.raw_content,
            "cleaned_content": self.cleaned_content,
            "metadata": self.metadata,
            "loaded_at": self.loaded_at,
        }


@dataclass
class Chunk:
    """A retrieval unit produced from a cleaned `Document`.

    Document-level fields (`doc_id`, `title`, `doc_type`, `source_path`,
    `source_format`) are copied onto every chunk so citations do not need
    to join back to the parent document. `section` is the nearest Markdown
    heading, when one exists.

    `chunk_id` is assigned by the chunker and must be stable for the same
    document text, chunker configuration, and position.
    """

    chunk_id: str
    doc_id: str
    text: str
    position: int
    title: str
    source_path: str
    source_format: str
    doc_type: str
    section: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.chunk_id or not self.chunk_id.strip():
            raise ValueError("Chunk.chunk_id must be a non-empty string")
        if self.position < 0:
            raise ValueError(
                f"Chunk '{self.chunk_id}' position must be >= 0"
            )
        if not self.text or not self.text.strip():
            raise ValueError(f"Chunk '{self.chunk_id}' has empty text")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "text": self.text,
            "position": self.position,
            "title": self.title,
            "source_path": self.source_path,
            "source_format": self.source_format,
            "doc_type": self.doc_type,
            "section": self.section,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chunk":
        return cls(
            chunk_id=data["chunk_id"],
            doc_id=data["doc_id"],
            text=data["text"],
            position=int(data["position"]),
            title=data["title"],
            source_path=data["source_path"],
            source_format=data["source_format"],
            doc_type=data["doc_type"],
            section=data.get("section"),
            metadata=dict(data.get("metadata") or {}),
        )
