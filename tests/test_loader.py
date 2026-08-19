from pathlib import Path

import pytest

from darwix.loaders.markdown_loader import MarkdownLoader
from darwix.schema import Document

SAMPLE_WITH_FRONT_MATTER = """---
doc_id: sample_doc
doc_type: faq
title: Sample Document
is_synthetic: true
---
This is the body.

It has multiple paragraphs.
"""

SAMPLE_WITHOUT_FRONT_MATTER = "Just a plain body with no metadata.\n"


def _write(tmp_path: Path, filename: str, content: str) -> Path:
    file_path = tmp_path / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_load_file_parses_front_matter_and_body(tmp_path: Path):
    path = _write(tmp_path, "sample_doc.md", SAMPLE_WITH_FRONT_MATTER)

    doc = MarkdownLoader().load_file(path)

    assert isinstance(doc, Document)
    assert doc.doc_id == "sample_doc"
    assert doc.doc_type == "faq"
    assert doc.title == "Sample Document"
    assert doc.source_format == "markdown"
    assert doc.source_path == str(path)
    assert "This is the body." in doc.raw_content
    assert doc.metadata["is_synthetic"] is True
    assert doc.cleaned_content is None  # cleaning happens separately


def test_load_file_without_front_matter_uses_filename_defaults(tmp_path: Path):
    path = _write(tmp_path, "no_front_matter.md", SAMPLE_WITHOUT_FRONT_MATTER)

    doc = MarkdownLoader().load_file(path)

    assert doc.doc_id == "no_front_matter"
    assert doc.doc_type == "unknown"
    assert doc.title == "No Front Matter"
    assert doc.metadata == {}
    assert doc.raw_content.strip() == "Just a plain body with no metadata."


def test_load_directory_returns_all_markdown_files(tmp_path: Path):
    _write(tmp_path, "a.md", "---\ndoc_id: a\n---\nBody A")
    _write(tmp_path, "b.md", "---\ndoc_id: b\n---\nBody B")
    _write(tmp_path, "not_markdown.txt", "should be ignored")

    docs = MarkdownLoader().load_directory(tmp_path, pattern="*.md")

    assert len(docs) == 2
    assert {d.doc_id for d in docs} == {"a", "b"}


def test_load_directory_raises_on_duplicate_doc_ids(tmp_path: Path):
    _write(tmp_path, "a.md", "---\ndoc_id: dup\n---\nBody A")
    _write(tmp_path, "b.md", "---\ndoc_id: dup\n---\nBody B")

    with pytest.raises(ValueError, match="Duplicate doc_id"):
        MarkdownLoader().load_directory(tmp_path, pattern="*.md")


def test_load_directory_raises_for_missing_directory(tmp_path: Path):
    missing = tmp_path / "does_not_exist"

    with pytest.raises(FileNotFoundError):
        MarkdownLoader().load_directory(missing)


def test_real_synthetic_corpus_loads_successfully():
    """Sanity check against the actual synthetic corpus shipped in data/."""
    corpus_dir = Path(__file__).resolve().parents[1] / "data" / "synthetic_docs"

    docs = MarkdownLoader().load_directory(corpus_dir, pattern="*.md")

    assert len(docs) == 6
    for doc in docs:
        assert doc.metadata.get("is_synthetic") is True
        assert "SYNTHETIC ASSESSMENT DATA" in doc.raw_content
