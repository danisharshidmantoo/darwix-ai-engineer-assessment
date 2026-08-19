# Darwix AI Engineer Assessment — Q1/Q2 Foundation

## Use case

**Candidate screening for an AI Engineer Intern role.**

Q1 (voice screening agent) and Q2 (knowledge-base / RAG system) are designed to
be connected from the start: Q1 will *retrieve* answers about the role,
eligibility, and process from Q2 instead of hardcoding FAQs or policy text
into an LLM prompt.

> **All data in this repository is synthetic assessment data.**
> The documents in `data/synthetic_docs/` are invented for this assessment
> only. They do **not** represent real Darwix policy, process, or hiring
> criteria. Every document is labelled `is_synthetic: true` in its front
> matter and carries a disclaimer in its body.

## What exists right now (this stage)

This is the **Q2 foundation only**: the document ingestion layer that later
pipeline stages (cleaning → chunking → embeddings → vector DB → retrieval)
will build on. Nothing beyond loading + cleaning + schema is implemented yet.

Concretely, this stage delivers:

1. A clean, modular Python project (`src/darwix/`, `data/`, `tests/`).
2. Six synthetic candidate-screening documents in Markdown with YAML front
   matter metadata.
3. A `Document` schema (`src/darwix/schema.py`) used by every later stage.
4. A Markdown loader (`src/darwix/loaders/markdown_loader.py`) that parses
   front matter + body into `Document` objects.
5. A text cleaner (`src/darwix/cleaning.py`) that normalizes whitespace,
   unicode, and punctuation without destroying meaning (no chunking, no
   lowercasing of content — that would hurt later retrieval quality).
6. A `BaseDocumentLoader` abstraction so PDF and web loaders can be added
   later without changing the `Document` schema or downstream code.
7. Unit tests for the loader and cleaner.

## Project structure

```
darwix-ai-engineer-assessment/
├── README.md
├── requirements.txt
├── .env.example
├── pyproject.toml
├── .gitignore
├── data/
│   └── synthetic_docs/          # synthetic knowledge base source documents
│       ├── job_description.md
│       ├── eligibility_policy.md
│       ├── screening_process.md
│       ├── candidate_faqs.md
│       ├── common_objections.md
│       └── hiring_process.md
├── src/
│   └── darwix/
│       ├── __init__.py
│       ├── schema.py             # Document dataclass (shared schema)
│       ├── cleaning.py           # text normalization utilities
│       └── loaders/
│           ├── __init__.py
│           ├── base.py           # BaseDocumentLoader (extensible)
│           └── markdown_loader.py
└── tests/
    ├── test_loader.py
    └── test_cleaner.py
```

## Why it's structured this way

- **`Document` is format-agnostic.** It has a `source_format` field
  (`"markdown"` today). A future `PdfLoader` or `WebLoader` just needs to
  produce the same `Document` object — nothing downstream needs to know or
  care where the text came from.
- **`BaseDocumentLoader` is the extension point.** Adding PDF or web
  ingestion later means writing `PdfLoader(BaseDocumentLoader)` /
  `WebLoader(BaseDocumentLoader)` and implementing one method
  (`load_file`). `load_directory` is inherited for free.
- **Cleaning is separate from loading.** `cleaning.py` has no knowledge of
  files, front matter, or metadata — it only transforms strings. This keeps
  it trivially testable and reusable by the future chunker.
- **No chunking, embeddings, or vector DB yet.** Those are the *next* stage
  and depend on a stable, tested loader + cleaner, which is what this stage
  provides.

## Running the tests

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -v
```

## Configuration

No API keys or external services are required for this stage. See
`.env.example` for the (currently unused) placeholders that later stages
will need.

## What is explicitly NOT built yet

- Chunking / metadata-aware splitting
- Embeddings + vector database + retrieval + citations
- The Q1 voice agent (ASR, conversation manager, TTS)
- Deterministic screening rules / candidate state
- Q3 (Philippines / Indonesia localization)
- Q4 (real-time streaming nudges)

## Next stage (for whoever picks this up next)

1. Add a `chunker.py` that takes a cleaned `Document` and produces
   `Chunk` objects (id, doc_id, text, position, metadata inherited from the
   parent document — e.g. `doc_type`, `title`).
2. Add an `embeddings.py` wrapping a single embedding provider (keep it
   swappable behind a small interface).
3. Add a minimal local vector store (e.g. Chroma or a flat FAISS index —
   pick whichever keeps dependencies smallest) plus a `retriever.py` that
   returns top-k chunks with citation metadata (`doc_id`, `title`, source
   path).
4. Only after Q2 retrieval is solid, start Q1: a conversation manager that
   calls the Q2 retriever for FAQ/policy questions and keeps deterministic
   screening logic (eligibility checks, required questions) in code, not in
   the LLM prompt.
