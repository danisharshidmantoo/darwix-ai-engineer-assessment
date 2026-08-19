from darwix.cleaning import (
    clean_document,
    clean_text,
    normalize_punctuation,
    normalize_whitespace,
)
from darwix.schema import Document


def test_normalize_punctuation_replaces_smart_quotes_and_dashes():
    text = "\u201cHello\u201d \u2014 it's a test\u2026"
    result = normalize_punctuation(text)
    assert result == '"Hello" - it\'s a test...'


def test_normalize_whitespace_trims_trailing_spaces():
    text = "line one   \nline two\t\n"
    result = normalize_whitespace(text)
    assert result == "line one\nline two"


def test_normalize_whitespace_collapses_excess_blank_lines():
    text = "para one\n\n\n\n\npara two"
    result = normalize_whitespace(text)
    assert result == "para one\n\npara two"


def test_normalize_whitespace_strips_leading_and_trailing():
    text = "\n\n  content here  \n\n"
    result = normalize_whitespace(text)
    assert result == "content here"


def test_clean_text_full_pipeline():
    text = "  \u201cQuoted\u201d text\u2014with dashes.   \n\n\n\nNext para.  "
    result = clean_text(text)
    assert result == '"Quoted" text-with dashes.\n\nNext para.'


def test_clean_document_sets_cleaned_content_and_stats():
    doc = Document(
        doc_id="d1",
        title="Doc 1",
        doc_type="faq",
        source_path="none",
        source_format="markdown",
        raw_content="  Hello   world.  \n\n\n\nBye.  ",
    )

    result = clean_document(doc)

    assert result is doc  # mutated in place
    assert doc.cleaned_content == "Hello   world.\n\nBye."
    assert doc.metadata["char_count"] == len(doc.cleaned_content)
    assert doc.metadata["word_count"] == 3
