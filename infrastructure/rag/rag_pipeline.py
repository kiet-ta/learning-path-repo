"""
RAG Pipeline - RAG Infrastructure
Orchestrates the full Retrieval-Augmented Generation workflow for code analysis.

Pipeline stages:
  1. Index  — chunk all source files and upsert into ChromaDB
  2. Retrieve — semantic search for relevant chunks given a query
  3. Generate — assemble a prompt with retrieved context and call the LLM

This module is intentionally thin; it delegates to CodeChunker, VectorStore,
and an injected LLM client (OpenAI-compatible).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, List, Optional

from infrastructure.rag.chunker import CodeChunker
from infrastructure.rag.vector_store import VectorStore, SearchResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RetrievalContext:
    """Structured context assembled from vector search results."""
    query: str
    chunks: List[SearchResult]
    formatted_context: str = field(init=False)

    def __post_init__(self) -> None:
        parts: list[str] = []
        seen_files: set[str] = set()
        for idx, result in enumerate(self.chunks, start=1):
            parts.append(
                f"### [{idx}] {result.file_path} (line {result.start_line}) "
                f"— {result.chunk_type} `{result.symbol_name}`\n"
                f"```{result.language}\n{result.content}\n```"
            )
            seen_files.add(result.file_path)
        self.formatted_context = "\n\n".join(parts)

    @property
    def source_files(self) -> list[str]:
        return list({r.file_path for r in self.chunks})


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class RAGPipeline:
    """
    Full RAG pipeline for code repository analysis.

    Args:
        vector_store: Pre-configured VectorStore instance.
        llm_client: Any object with an async `chat_complete(messages)` method
                    returning a string. Inject an OpenAI wrapper or a mock.
        chunker: Optional CodeChunker override for testing.

    Usage:
        pipeline = RAGPipeline(vector_store=store, llm_client=openai_client)

        # Index a repository
        n = await pipeline.index_repository(Path("/repos/my-service"))

        # Query
        answer = await pipeline.query("How does authentication work?")
    """

    _SYSTEM_PROMPT = (
        "You are an expert software engineer. "
        "Answer the user's question using ONLY the provided code context. "
        "If the context does not contain enough information, say so clearly. "
        "Reference specific file paths and line numbers when possible."
    )

    def __init__(
        self,
        vector_store: VectorStore,
        llm_client,
        chunker: Optional[CodeChunker] = None,
    ) -> None:
        self._store = vector_store
        self._llm = llm_client
        self._chunker = chunker or CodeChunker()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_repository(
        self,
        repo_path: Path,
        extensions: Optional[list[str]] = None,
        force_reindex: bool = False,
    ) -> int:
        """
        Walk a repository, chunk all matching files, and upsert to the store.

        Args:
            repo_path: Root directory of the repository.
            extensions: List of file extensions to include, e.g. [".py", ".ts"].
                        Defaults to all supported languages.
            force_reindex: If True, delete existing file chunks before re-indexing.

        Returns:
            Total number of chunks indexed.
        """
        _default_exts = {".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs"}
        exts = set(extensions or _default_exts)

        total = 0
        for file_path in sorted(repo_path.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix not in exts:
                continue
            if any(part.startswith(".") or part in {"node_modules", "__pycache__", "dist", "build"}
                   for part in file_path.parts):
                continue

            if force_reindex:
                self._store.delete_by_file(str(file_path))

            try:
                chunks = await self._chunker.chunk_file(file_path)
                if chunks:
                    n = self._store.upsert(chunks)
                    total += n
                    logger.debug("Indexed %s → %d chunks", file_path, n)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to index %s: %s", file_path, exc)

        logger.info("Repository indexed: %s — %d total chunks", repo_path, total)
        return total

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        n_results: int = 8,
        language_filter: Optional[str] = None,
    ) -> RetrievalContext:
        """
        Retrieve the most relevant code chunks for a query.

        Args:
            query: Natural language question about the codebase.
            n_results: Number of chunks to retrieve.
            language_filter: Restrict results to a specific language.

        Returns:
            RetrievalContext containing ranked chunks and formatted text.
        """
        results = self._store.search(
            query=query,
            n_results=n_results,
            language_filter=language_filter,
        )
        return RetrievalContext(query=query, chunks=results)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    async def query(
        self,
        question: str,
        n_results: int = 8,
        language_filter: Optional[str] = None,
    ) -> str:
        """
        Full RAG cycle: retrieve → assemble prompt → generate answer.

        Args:
            question: Natural language question about the codebase.
            n_results: Number of context chunks to include.
            language_filter: Optional language restriction.

        Returns:
            LLM-generated answer grounded in the retrieved code context.
        """
        ctx = self.retrieve(question, n_results=n_results, language_filter=language_filter)

        if not ctx.chunks:
            return (
                "No relevant code found in the indexed repository. "
                "Ensure the repository has been indexed with `index_repository()`."
            )

        user_message = (
            f"## Codebase Context\n\n{ctx.formatted_context}\n\n"
            f"## Question\n\n{question}"
        )
        messages = [
            {"role": "system", "content": self._SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        answer: str = await self._llm.chat_complete(messages)
        logger.info("RAG query answered — %d chunks used", len(ctx.chunks))
        return answer

    async def stream_query(
        self,
        question: str,
        n_results: int = 8,
        language_filter: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Streaming variant of `query`. Yields answer tokens as they arrive.

        The injected llm_client must implement `stream_chat_complete(messages)`
        returning an AsyncIterator[str].
        """
        ctx = self.retrieve(question, n_results=n_results, language_filter=language_filter)
        if not ctx.chunks:
            yield (
                "No relevant code found. Index the repository first "
                "with `index_repository()`."
            )
            return

        user_message = (
            f"## Codebase Context\n\n{ctx.formatted_context}\n\n"
            f"## Question\n\n{question}"
        )
        messages = [
            {"role": "system", "content": self._SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        async for token in self._llm.stream_chat_complete(messages):
            yield token
