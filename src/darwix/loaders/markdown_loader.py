"""
Markdown loader.

Reads a `.md` file with an optional YAML front-matter block:

    ---
    doc_id: job_description
    doc_type: job_description
    title: Some Title
    ---
    Body content starts here...

Front-matter fields become `Document.metadata`. `doc_id`, `doc_type`, and
`title` are pulled out of metadata if present; otherwise they fall back to
sensible defaults derived from the filename.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Tuple, Union

import yaml

from darwix.loaders.base import BaseDocumentLoader
from darwix.schema import Document

_FRONT_MATTER_RE = re.compile(
    r"\A---\s*\n(?P<front_matter>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


def _split_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    """Split raw file text into (metadata_dict, body). If there is no
    front-matter block, metadata is an empty dict and body is the whole
    text.
    """
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text

    raw_front_matter = match.group("front_matter")
    body = match.group("body")

    metadata = yaml.safe_load(raw_front_matter) or {}
    if not isinstance(metadata, dict):
        raise ValueError("Front matter must be a YAML mapping")

    return metadata, body


class MarkdownLoader(BaseDocumentLoader):
    """Loads `.md` files into `Document` objects."""

    source_format = "markdown"

    def load_file(self, path: Union[str, Path]) -> Document:
        path = Path(path)
        text = path.read_text(encoding="utf-8")

        metadata, body = _split_front_matter(text)

        doc_id = str(metadata.get("doc_id") or path.stem)
        doc_type = str(metadata.get("doc_type") or "unknown")
        title = str(metadata.get("title") or doc_id.replace("_", " ").title())

        return Document(
            doc_id=doc_id,
            title=title,
            doc_type=doc_type,
            source_path=str(path),
            source_format=self.source_format,
            raw_content=body.strip(),
            metadata=metadata,
        )
