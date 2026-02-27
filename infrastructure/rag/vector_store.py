"""
Vector Store - RAG Infrastructure
ChromaDB-backed persistent vector store for code chunk embeddings.

Features:
  - Lazy initialization: only connects to ChromaDB when first used
  - Upsert semantics: re-embedding a file replaces old chunks
  - Configurable embedding function (default: chromadb's built-in sentence-transformer)
  - Graceful fallback when chromadb is not installed (raises ImportError with instructions)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_CHROMA_AVAILABLE = False
try:
    import chromadb
    from chromadb import Collection
    from chromadb.config import Settings
    _CHROMA_AVAILABLE = True
except ImportError:
    pass


@dataclass
class SearchResult:
    """A single retrieved chunk with its similarity distance."""
    chunk_id: str
    content: str
    distance: float
    file_path: str
    language: str
    chunk_type: str
    symbol_name: str
    start_line: int
    metadata: dict = field(default_factory=dict)


class VectorStore:
    """
    Persistent ChromaDB vector store for code chunks.

    Args:
        persist_dir: Directory where ChromaDB data is stored.
        collection_name: ChromaDB collection identifier.

    Usage:
        store = VectorStore(persist_dir=Path("data/chroma"))
        store.upsert(chunks)
        results = store.search("handle HTTP authentication", n_results=5)
    """

    def __init__(
        self,
        persist_dir: Path = Path("data/chroma"),
        collection_name: str = "code_chunks",
    ) -> None:
        if not _CHROMA_AVAILABLE:
            raise ImportError(
                "chromadb is not installed. "
                "Add `chromadb>=0.5.23` to requirements.txt and reinstall."
            )
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._client: Optional["chromadb.PersistentClient"] = None
        self._collection: Optional["Collection"] = None

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._client is not None:
            return
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self._persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "VectorStore connected — collection=%s persist_dir=%s",
            self._collection_name, self._persist_dir,
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def upsert(self, chunks: "list") -> int:
        """
        Insert or update chunks in the collection.
        Returns the number of chunks upserted.

        Args:
            chunks: List of Chunk dataclass instances from chunker.py
        """
        self._ensure_connected()
        if not chunks:
            return 0

        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [c.metadata for c in chunks]

        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug("Upserted %d chunks into collection '%s'", len(chunks), self._collection_name)
        return len(chunks)

    def delete_by_file(self, file_path: str) -> int:
        """Remove all chunks associated with a given file path."""
        self._ensure_connected()
        results = self._collection.get(
            where={"file_path": file_path},
            include=[],
        )
        ids = results.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
            logger.debug("Deleted %d chunks for file %s", len(ids), file_path)
        return len(ids)

    def clear(self) -> None:
        """Delete and recreate the collection (destructive)."""
        self._ensure_connected()
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.warning("VectorStore collection '%s' cleared", self._collection_name)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        n_results: int = 5,
        language_filter: Optional[str] = None,
        chunk_type_filter: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Semantic search over the code chunk collection.

        Args:
            query: Natural language or code query.
            n_results: Maximum number of results to return.
            language_filter: Optional language to restrict results to.
            chunk_type_filter: Optional chunk_type to restrict results to.

        Returns:
            List of SearchResult ordered by ascending distance (most similar first).
        """
        self._ensure_connected()

        where: dict = {}
        if language_filter:
            where["language"] = language_filter
        if chunk_type_filter:
            where["chunk_type"] = chunk_type_filter

        kwargs: dict = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        raw = self._collection.query(**kwargs)

        results: list[SearchResult] = []
        ids = (raw.get("ids") or [[]])[0]
        docs = (raw.get("documents") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        dists = (raw.get("distances") or [[]])[0]

        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            results.append(SearchResult(
                chunk_id=cid,
                content=doc,
                distance=float(dist),
                file_path=meta.get("file_path", ""),
                language=meta.get("language", ""),
                chunk_type=meta.get("chunk_type", ""),
                symbol_name=meta.get("symbol_name", ""),
                start_line=int(meta.get("start_line", 0)),
                metadata=meta,
            ))

        return results

    def count(self) -> int:
        """Return the total number of chunks stored."""
        self._ensure_connected()
        return self._collection.count()
