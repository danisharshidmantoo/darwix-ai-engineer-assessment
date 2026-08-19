"""
Deterministic Q2 ingest pipeline:

    load Markdown documents
    -> clean
    -> chunk
    -> embed
    -> persist JSON vector index

The persisted file records embedding and chunker configuration so a later
retrieval run cannot silently use an incompatible encoder.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence, Union

from darwix.chunker import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, Chunker
from darwix.cleaning import clean_document
from darwix.embeddings import (
    EmbeddingProvider,
    HashedNgramEmbedding,
    embedding_text_for_chunk,
)
from darwix.loaders.markdown_loader import MarkdownLoader
from darwix.retriever import DEFAULT_MIN_SIMILARITY, DEFAULT_TOP_K, Retriever
from darwix.vector_store import VectorStore

DEFAULT_DOCS_DIR = Path("data/synthetic_docs")
DEFAULT_INDEX_PATH = Path("data/index/vector_store.json")


def build_index(
    docs_dir: Union[str, Path] = DEFAULT_DOCS_DIR,
    index_path: Union[str, Path] = DEFAULT_INDEX_PATH,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    embedder: Optional[EmbeddingProvider] = None,
) -> VectorStore:
    """Load, clean, chunk, embed, and persist a vector index."""
    embedder = embedder or HashedNgramEmbedding()
    chunker = Chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    documents = MarkdownLoader().load_directory(docs_dir, pattern="*.md")
    documents.sort(key=lambda d: d.doc_id)
    for document in documents:
        clean_document(document)

    chunks = chunker.chunk_documents(documents)
    embeddings = embedder.embed([embedding_text_for_chunk(chunk) for chunk in chunks])

    store = VectorStore(
        embedding_config=embedder.config,
        chunker_config=chunker.config,
    )
    store.add(chunks, embeddings)
    store.save(index_path)
    return store


def load_retriever(
    index_path: Union[str, Path] = DEFAULT_INDEX_PATH,
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    embedder: Optional[EmbeddingProvider] = None,
) -> Retriever:
    """Load a persisted index and a matching embedding provider."""
    store = VectorStore.load(index_path)
    if embedder is None:
        from darwix.embeddings import provider_from_config

        embedder = provider_from_config(store.embedding_config)
    return Retriever(
        store=store,
        embedder=embedder,
        top_k=top_k,
        min_similarity=min_similarity,
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the local Q2 vector index from synthetic Markdown docs."
    )
    parser.add_argument(
        "--docs",
        type=Path,
        default=DEFAULT_DOCS_DIR,
        help="Directory of Markdown source documents.",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX_PATH,
        help="Output JSON path for the persisted vector store.",
    )
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument(
        "--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    store = build_index(
        docs_dir=args.docs,
        index_path=args.index,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(
        f"Wrote {len(store)} chunks to {args.index} "
        f"(provider={store.embedding_config.provider}, "
        f"dim={store.embedding_config.dimensions})"
    )


if __name__ == "__main__":
    main()
