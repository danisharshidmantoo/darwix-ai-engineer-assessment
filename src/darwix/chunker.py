"""
Metadata-aware Markdown chunking.

Splits a cleaned `Document` into `Chunk` objects:
  1. Segment by Markdown headings so section titles stay attached.
  2. Window long sections with a configurable character size and overlap.
  3. Prefer paragraph/line/word boundaries over mid-token cuts.

Chunk IDs are `{doc_id}::{position:04d}` and are deterministic for a given
document body plus chunker configuration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from darwix.schema import Chunk, Document

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 120


@dataclass(frozen=True)
class ChunkerConfig:
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP

    def to_dict(self) -> dict:
        return {
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }


class Chunker:
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

        self.config = ChunkerConfig(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    def chunk_document(self, document: Document) -> List[Chunk]:
        """Split one document into ordered chunks."""
        text = (
            document.cleaned_content
            if document.cleaned_content is not None
            else document.raw_content
        )
        if not text or not text.strip():
            return []

        inherited = dict(document.metadata)
        chunks: List[Chunk] = []
        position = 0

        for section, section_text in _split_sections(text):
            for window in _window_text(
                section_text,
                size=self.config.chunk_size,
                overlap=self.config.chunk_overlap,
            ):
                metadata = dict(inherited)
                metadata["section"] = section
                metadata["chunk_size"] = self.config.chunk_size
                metadata["chunk_overlap"] = self.config.chunk_overlap

                chunks.append(
                    Chunk(
                        chunk_id=_stable_chunk_id(document.doc_id, position),
                        doc_id=document.doc_id,
                        text=window,
                        position=position,
                        title=document.title,
                        source_path=document.source_path,
                        source_format=document.source_format,
                        doc_type=document.doc_type,
                        section=section,
                        metadata=metadata,
                    )
                )
                position += 1

        return chunks

    def chunk_documents(self, documents: List[Document]) -> List[Chunk]:
        """Chunk many documents. Output is sorted by (doc_id, position)."""
        chunks: List[Chunk] = []
        for document in documents:
            chunks.extend(self.chunk_document(document))
        chunks.sort(key=lambda c: (c.doc_id, c.position))
        return chunks


def _stable_chunk_id(doc_id: str, position: int) -> str:
    return f"{doc_id}::{position:04d}"


def _split_sections(text: str) -> List[Tuple[Optional[str], str]]:
    """Return (heading_or_None, section_text) pairs in document order."""
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        stripped = text.strip()
        return [(None, stripped)] if stripped else []

    sections: List[Tuple[Optional[str], str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append((None, preamble))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            section_text = f"{heading}\n\n{body}"
        else:
            section_text = heading
        if section_text.strip():
            sections.append((heading, section_text))

    return sections


def _window_text(text: str, size: int, overlap: int) -> List[str]:
    """Split `text` into overlapping windows of about `size` characters."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    windows: List[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + size, n)
        if end < n:
            end = _prefer_break(text, start, end, size)

        piece = text[start:end].strip()
        if piece:
            windows.append(piece)

        if end >= n:
            break

        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return windows


def _prefer_break(text: str, start: int, end: int, size: int) -> int:
    """Move `end` back to a paragraph, line, or word boundary when possible."""
    window = text[start:end]
    min_offset = max(size // 2, 1)

    for separator in ("\n\n", "\n", " "):
        brk = window.rfind(separator)
        if brk >= min_offset:
            return start + brk
    return end
