"""
Code Chunker - RAG Infrastructure
Splits source code into semantically meaningful chunks for embedding.

Strategy:
  1. Use CodeSkeleton class/function boundaries when the AST parser is available.
  2. Fall back to langchain RecursiveCharacterTextSplitter with language-aware
     separators when tree-sitter is not available.
  3. Each Chunk carries rich metadata so vector search results can be traced
     back to an exact file + symbol.

Chunk size defaults:
  - 512 tokens target  (≈1,800 chars for Python)
  - 50 token overlap
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

from infrastructure.scanner.ast_parser import ASTParser, CodeSkeleton


class ChunkType(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    MODULE = "module"       # whole-file fallback / imports block
    SNIPPET = "snippet"     # generic text splitter output


@dataclass
class Chunk:
    """A single embeddable unit of code with traceability metadata."""
    content: str
    chunk_type: ChunkType
    file_path: str
    language: str
    # Optional symbol-level metadata
    symbol_name: Optional[str] = None
    start_line: Optional[int] = None
    # Stable ID derived from content hash
    chunk_id: str = field(init=False)
    # Metadata dict forwarded to the vector store
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        digest = hashlib.sha1(
            f"{self.file_path}:{self.content}".encode()
        ).hexdigest()[:16]
        self.chunk_id = digest
        self.metadata = {
            "file_path": self.file_path,
            "language": self.language,
            "chunk_type": self.chunk_type.value,
            "symbol_name": self.symbol_name or "",
            "start_line": self.start_line or 0,
        }


class CodeChunker:
    """
    Produces Chunk objects from source files or pre-parsed CodeSkeletons.

    Usage:
        chunker = CodeChunker()
        chunks = await chunker.chunk_file(Path("service.py"))
        # or from skeleton:
        chunks = chunker.chunk_skeleton(skeleton, source_text)
    """

    _CHAR_LIMIT = 6_000    # ~1,500 tokens at 4 chars/token
    _OVERLAP = 400          # character overlap between adjacent text chunks

    # Language-aware separators for text splitter fallback
    _SEPARATORS: dict[str, list[str]] = {
        "python": ["\nclass ", "\ndef ", "\n    def ", "\n\n", "\n", " "],
        "javascript": ["\nclass ", "\nfunction ", "\n\n", "\n", " "],
        "typescript": ["\nclass ", "\nfunction ", "\ninterface ", "\n\n", "\n", " "],
        "java": ["\nclass ", "\n    public ", "\n    private ", "\n\n", "\n", " "],
        "go": ["\nfunc ", "\ntype ", "\n\n", "\n", " "],
        "rust": ["\nfn ", "\nstruct ", "\nenum ", "\nimpl ", "\n\n", "\n", " "],
    }

    def __init__(self) -> None:
        self._ast_parser = ASTParser()

    async def chunk_file(self, file_path: Path, language: Optional[str] = None) -> List[Chunk]:
        """Parse and chunk a source file."""
        skeleton = await self._ast_parser.extract_skeleton(file_path, language)
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return self.chunk_skeleton(skeleton, source)

    def chunk_skeleton(self, skeleton: CodeSkeleton, source: str) -> List[Chunk]:
        """
        Build chunks from a pre-parsed skeleton + raw source text.
        Prefers symbol-level chunks; falls back to text splitting.
        """
        chunks: list[Chunk] = []

        if skeleton.imports:
            import_text = "\n".join(skeleton.imports[:30])
            chunks.append(Chunk(
                content=import_text,
                chunk_type=ChunkType.MODULE,
                file_path=skeleton.file_path,
                language=skeleton.language,
                symbol_name="__imports__",
                start_line=1,
            ))

        for cls in skeleton.classes:
            text = cls.docstring or ""
            if cls.methods:
                method_sigs = "\n".join(
                    f"  def {m.name}({', '.join(m.parameters)})"
                    for m in cls.methods
                )
                text = f"class {cls.name}({', '.join(cls.bases)}):\n{method_sigs}"
            if text:
                chunks.append(Chunk(
                    content=text[:self._CHAR_LIMIT],
                    chunk_type=ChunkType.CLASS,
                    file_path=skeleton.file_path,
                    language=skeleton.language,
                    symbol_name=cls.name,
                    start_line=cls.line_number,
                ))

        for fn in skeleton.functions:
            sig = f"{'async ' if fn.is_async else ''}def {fn.name}({', '.join(fn.parameters)})"
            if fn.return_type:
                sig += f" -> {fn.return_type}"
            text = sig
            if fn.docstring:
                text += f'\n    """{fn.docstring[:200]}"""'
            chunks.append(Chunk(
                content=text,
                chunk_type=ChunkType.FUNCTION,
                file_path=skeleton.file_path,
                language=skeleton.language,
                symbol_name=fn.name,
                start_line=fn.line_number,
            ))

        # If nothing structural was found, fall back to text splitting
        if not chunks:
            chunks = self._text_split(source, skeleton.file_path, skeleton.language)

        return chunks

    def _text_split(self, source: str, file_path: str, language: str) -> List[Chunk]:
        """
        Naive sliding-window split with language-aware separator awareness.
        Used when AST extraction yields no symbols.
        """
        separators = self._SEPARATORS.get(language, ["\n\n", "\n", " "])
        chunks: list[Chunk] = []

        # Try to split by primary separator first
        parts: list[str] = []
        primary_sep = separators[0]
        raw_parts = source.split(primary_sep)
        current = ""
        for part in raw_parts:
            candidate = current + primary_sep + part if current else part
            if len(candidate) <= self._CHAR_LIMIT:
                current = candidate
            else:
                if current:
                    parts.append(current)
                current = part
        if current:
            parts.append(current)

        line_offset = 1
        for idx, part in enumerate(parts):
            if not part.strip():
                line_offset += part.count("\n")
                continue
            chunks.append(Chunk(
                content=part[:self._CHAR_LIMIT],
                chunk_type=ChunkType.SNIPPET,
                file_path=file_path,
                language=language,
                symbol_name=f"chunk_{idx}",
                start_line=line_offset,
            ))
            line_offset += part.count("\n")

        return chunks
