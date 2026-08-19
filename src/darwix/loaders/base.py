"""
Base loader interface.

To add a new source format later (PDF, web page, etc.), subclass
`BaseDocumentLoader`, set `source_format`, and implement `load_file`.
`load_directory` works for free as long as `load_file` returns a valid
`Document`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Union

from darwix.schema import Document


class BaseDocumentLoader(ABC):
    """Common interface for all document loaders."""

    #: Overridden by subclasses, e.g. "markdown", "pdf", "web".
    source_format: str = "unknown"

    @abstractmethod
    def load_file(self, path: Union[str, Path]) -> Document:
        """Load a single file into a `Document`."""
        raise NotImplementedError

    def load_directory(
        self, directory: Union[str, Path], pattern: str = "*"
    ) -> List[Document]:
        """Load every file matching `pattern` in `directory` (non-recursive,
        sorted for deterministic ordering). Raises `ValueError` if two
        loaded documents share a `doc_id`, since later stages assume
        `doc_id` is unique.
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise FileNotFoundError(f"Not a directory: {directory}")

        paths = sorted(directory.glob(pattern))
        documents = [self.load_file(p) for p in paths]

        seen_ids = set()
        for doc in documents:
            if doc.doc_id in seen_ids:
                raise ValueError(f"Duplicate doc_id found: '{doc.doc_id}'")
            seen_ids.add(doc.doc_id)

        return documents
