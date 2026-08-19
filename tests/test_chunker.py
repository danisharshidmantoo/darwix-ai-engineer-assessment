from darwix.chunker import Chunker
from darwix.schema import Document


def _doc(raw: str, doc_id: str = "d1", **kwargs) -> Document:
    return Document(
        doc_id=doc_id,
        title=kwargs.get("title", "Doc 1"),
        doc_type=kwargs.get("doc_type", "faq"),
        source_path=kwargs.get("source_path", "docs/d1.md"),
        source_format="markdown",
        raw_content=raw,
        cleaned_content=kwargs.get("cleaned_content", raw),
        metadata=dict(
            kwargs.get("metadata")
            or {"is_synthetic": True, "version": "1.0"}
        ),
    )


def test_chunker_rejects_overlap_equal_to_size():
    try:
        Chunker(chunk_size=10, chunk_overlap=10)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "chunk_overlap" in str(exc)


def test_heading_sections_are_preserved():
    text = (
        "# Title\n\n"
        "Intro paragraph about the role.\n\n"
        "## Eligibility\n\n"
        "Applicants must commit 20 hours per week.\n\n"
        "## Process\n\n"
        "Screening has three stages."
    )
    chunks = Chunker(chunk_size=700, chunk_overlap=50).chunk_document(_doc(text))

    sections = {c.section for c in chunks}
    assert "Eligibility" in sections
    assert "Process" in sections

    eligibility = next(c for c in chunks if c.section == "Eligibility")
    assert "20 hours per week" in eligibility.text
    assert eligibility.metadata["is_synthetic"] is True
    assert eligibility.metadata["section"] == "Eligibility"
    assert eligibility.title == "Doc 1"
    assert eligibility.doc_id == "d1"
    assert eligibility.doc_type == "faq"
    assert eligibility.source_path == "docs/d1.md"


def test_metadata_is_inherited_on_every_chunk():
    text = "alpha " * 80
    chunks = Chunker(chunk_size=80, chunk_overlap=20).chunk_document(
        _doc(
            text,
            metadata={
                "is_synthetic": True,
                "version": "1.0",
                "custom": "keep",
            },
        )
    )
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.metadata["custom"] == "keep"
        assert chunk.metadata["is_synthetic"] is True
        assert chunk.metadata["version"] == "1.0"


def test_chunk_ids_are_stable_and_positional():
    text = "word " * 200
    chunker = Chunker(chunk_size=90, chunk_overlap=20)
    first = chunker.chunk_document(_doc(text))
    second = chunker.chunk_document(_doc(text))

    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.position for c in first] == list(range(len(first)))
    assert first[0].chunk_id == "d1::0000"
    assert first[1].chunk_id == "d1::0001"


def test_windows_overlap_on_long_unbroken_text():
    text = "abcdefghijklmnopqrstuvwxyz" * 6  # 156 chars, no break characters
    chunk_size = 40
    overlap = 10
    chunks = Chunker(chunk_size=chunk_size, chunk_overlap=overlap).chunk_document(
        _doc(text)
    )

    assert len(chunks) >= 3
    for left, right in zip(chunks, chunks[1:]):
        shared = left.text[-overlap:]
        assert right.text.startswith(shared), (
            f"expected overlap {overlap!r} between {left.chunk_id} and {right.chunk_id}"
        )


def test_short_document_is_a_single_chunk():
    chunks = Chunker().chunk_document(_doc("Short body."))
    assert len(chunks) == 1
    assert chunks[0].text == "Short body."
    assert chunks[0].position == 0


def test_chunk_documents_sorts_by_doc_id_and_position():
    chunker = Chunker(chunk_size=40, chunk_overlap=5)
    chunks = chunker.chunk_documents(
        [
            _doc("bbbbbbbbbb " * 20, doc_id="b"),
            _doc("aaaaaaaaaa " * 20, doc_id="a"),
        ]
    )
    ids = [c.doc_id for c in chunks]
    assert ids == sorted(ids)
    a_positions = [c.position for c in chunks if c.doc_id == "a"]
    assert a_positions == list(range(len(a_positions)))
