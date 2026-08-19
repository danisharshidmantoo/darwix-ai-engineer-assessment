"""
Text cleaning / normalization.

Deliberately conservative: this stage prepares text for later chunking
and embedding, so it must not change meaning. It only:
  - normalizes unicode form
  - normalizes "smart" punctuation to plain ASCII equivalents
  - collapses redundant whitespace (trailing spaces, excess blank lines)

It intentionally does NOT lowercase, strip stopwords, or otherwise alter
content — that would reduce quality for later retrieval and citation.
"""

from __future__ import annotations

import re
import unicodedata

from darwix.schema import Document

_PUNCTUATION_MAP = {
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2026": "...",  # ellipsis
    "\u00a0": " ",  # non-breaking space
}

_TRAILING_WHITESPACE_RE = re.compile(r"[ \t]+(?=\n)")
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")


def normalize_unicode(text: str) -> str:
    """Normalize to NFKC form so equivalent characters compare equal."""
    return unicodedata.normalize("NFKC", text)


def normalize_punctuation(text: str) -> str:
    """Replace smart/typographic punctuation with plain ASCII equivalents."""
    for smart, plain in _PUNCTUATION_MAP.items():
        text = text.replace(smart, plain)
    return text


def normalize_whitespace(text: str) -> str:
    """Trim trailing whitespace on each line, collapse 3+ blank lines to
    exactly one blank line (two newlines), and strip leading/trailing
    whitespace from the whole text."""
    text = _TRAILING_WHITESPACE_RE.sub("", text)
    text = _EXCESS_BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Full cleaning pipeline applied to a raw string."""
    text = normalize_unicode(text)
    text = normalize_punctuation(text)
    text = normalize_whitespace(text)
    return text


def clean_document(document: Document) -> Document:
    """Populate `document.cleaned_content` (and basic stats in
    `document.metadata`) from `document.raw_content`. Mutates and returns
    the same `Document` instance.
    """
    cleaned = clean_text(document.raw_content)
    document.cleaned_content = cleaned
    document.metadata["char_count"] = len(cleaned)
    document.metadata["word_count"] = len(cleaned.split())
    return document
