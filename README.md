# Darwix AI Engineer Assessment — Q2 Knowledge Base / RAG

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

## What exists right now

This stage is **Q2 retrieval** on top of the existing document foundation
(load → clean → schema). It does **not** include the Q1 voice agent.

Concretely, this stage delivers:

1. A modular Python project (`src/darwix/`, `data/`, `tests/`).
2. Six synthetic candidate-screening documents in Markdown with YAML front
   matter metadata.
3. A `Document` schema and a `Chunk` schema (`src/darwix/schema.py`).
4. A Markdown loader (`src/darwix/loaders/markdown_loader.py`) and a
   `BaseDocumentLoader` abstraction for later PDF/web loaders.
5. A conservative text cleaner (`src/darwix/cleaning.py`) that does **not**
   lowercase stored content.
6. Metadata-aware chunking (`src/darwix/chunker.py`) with stable chunk IDs,
   heading/section labels, and configurable size/overlap.
7. An offline, deterministic embedding provider (`src/darwix/embeddings.py`)
   behind a swappable `EmbeddingProvider` interface. No paid APIs and no
   network calls.
8. A persistent local JSON vector store (`src/darwix/vector_store.py`) that
   records embedding/chunker configuration next to the vectors.
9. An ingest pipeline and retriever (`src/darwix/ingest.py`,
   `src/darwix/retriever.py`) with top-k cosine search, citation metadata,
   and a minimum similarity threshold for ungrounded queries.
10. Unit and integration tests for foundation + Q2 behavior.

## Project structure

```
darwix-ai-engineer-assessment/
├── README.md
├── requirements.txt
├── .env.example
├── pyproject.toml
├── .gitignore
├── data/
│   ├── synthetic_docs/          # synthetic knowledge base source documents
│   └── index/                   # generated locally; not committed
├── src/
│   └── darwix/
│       ├── __init__.py
│       ├── schema.py             # Document + Chunk
│       ├── cleaning.py
│       ├── chunker.py
│       ├── embeddings.py         # EmbeddingProvider + hashed n-grams
│       ├── vector_store.py       # JSON persistence + brute-force cosine
│       ├── retriever.py
│       ├── ingest.py             # load → clean → chunk → embed → save
│       └── loaders/
│           ├── __init__.py
│           ├── base.py
│           └── markdown_loader.py
└── tests/
    ├── test_loader.py
    ├── test_cleaner.py
    ├── test_chunker.py
    ├── test_embeddings.py
    ├── test_vector_store.py
    └── test_retriever.py
```

## Offline embeddings and vector store (design and limits)

**Embeddings.** `HashedNgramEmbedding` maps text to a fixed-length vector
(default 256 dimensions) using signed SHA-256 feature hashing over
character n-grams (3–5) and word uni/bigrams. Vectors are L2-normalized.
The same string always produces the same vector in any process (Python's
built-in `hash()` is **not** used, because it is randomized per process).

This is **not** a neural embedding model. It captures lexical/character
overlap, so it can rank FAQ/policy passages that share wording with a
query. It will not match paraphrases that share little surface form.
A future dense model can implement `EmbeddingProvider` and rebuild the
index; ingest persists `EmbeddingConfig` so retrieval refuses a silent
mismatch.

**Vector store.** Indexed chunks are stored as JSON (paths, text,
metadata, and float vectors). Search is exact cosine similarity over all
vectors. The synthetic corpus is small, so this needs no Chroma, FAISS, or
NumPy. Rebuilding the index is deterministic for the same documents and
chunker/embedding settings.

**Grounding.** `Retriever` drops hits below `min_similarity` (default
`0.18`). Queries with no hit at or above that threshold return an empty
result list (`has_results` is false). Empty/whitespace queries raise
`ValueError`.

## Build / rebuild the local index

From the project root (after installing requirements):

```bash
python -m darwix.ingest
```

This reads `data/synthetic_docs/*.md` and writes
`data/index/vector_store.json` (gitignored). Options:

```bash
python -m darwix.ingest \
  --docs data/synthetic_docs \
  --index data/index/vector_store.json \
  --chunk-size 700 \
  --chunk-overlap 120
```

Rebuild after changing documents, chunker settings, or the embedding
provider. Retrieval loads the provider from the file; if you pass a
different `EmbeddingProvider` config, it raises rather than searching with
incompatible vectors.

## Running the tests

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -v
```

Tests rebuild indexes under pytest's `tmp_path`; you do not need a
pre-built `data/index/` file to run them.

## Configuration

No API keys or external services are required for Q2. See `.env.example`
for placeholders that later stages (Q1 voice / hosted models) may use.

## What is explicitly NOT built yet

- The Q1 voice agent (ASR, conversation manager, TTS)
- LLM answer generation over retrieved chunks
- Deterministic screening rules / candidate state
- Neural / API embedding models
- Q3 (Philippines / Indonesia localization)
- Q4 (real-time streaming nudges)

## Next stage

After Q2 retrieval is solid, start Q1: a conversation manager that calls
the Q2 retriever for FAQ/policy questions and keeps deterministic
screening logic (eligibility checks, required questions) in code, not in
the LLM prompt.
