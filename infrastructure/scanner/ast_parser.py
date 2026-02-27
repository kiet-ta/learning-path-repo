"""
AST Parser - Infrastructure Layer
Extracts structural code skeletons (classes, functions, imports) using tree-sitter.

Provides language-agnostic parsing for Python, JavaScript/TypeScript, Java, Go,
and Rust. Falls back to regex-based extraction when tree-sitter is unavailable.

Usage:
    parser = ASTParser()
    skeleton = await parser.extract_skeleton(Path("src/service.py"), "python")
    # → CodeSkeleton(classes=[...], functions=[...], imports=[...])
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# tree-sitter is optional — graceful degradation to regex fallback
try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    import tree_sitter_java as tsjava
    import tree_sitter_go as tsgo
    import tree_sitter_rust as tsrust
    from tree_sitter import Language, Parser

    _LANGUAGES: dict[str, Language] = {
        "python": Language(tspython.language()),
        "javascript": Language(tsjavascript.language()),
        "typescript": Language(tstypescript.language_typescript()),
        "java": Language(tsjava.language()),
        "go": Language(tsgo.language()),
        "rust": Language(tsrust.language()),
    }
    _TREE_SITTER_AVAILABLE = True
except ImportError:
    _TREE_SITTER_AVAILABLE = False
    _LANGUAGES = {}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FunctionSignature:
    name: str
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    line_number: int = 0


@dataclass
class ClassSignature:
    name: str
    bases: List[str] = field(default_factory=list)
    methods: List[FunctionSignature] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    line_number: int = 0


@dataclass
class CodeSkeleton:
    """Structural summary of a source file — no raw code bodies."""
    language: str
    file_path: str
    imports: List[str] = field(default_factory=list)
    classes: List[ClassSignature] = field(default_factory=list)
    functions: List[FunctionSignature] = field(default_factory=list)
    # Top-level constants / module-level variables
    constants: List[str] = field(default_factory=list)
    parse_error: Optional[str] = None

    def to_text(self) -> str:
        """Render skeleton as a compact human-readable text block for LLM context."""
        lines: list[str] = [f"# File: {self.file_path} [{self.language}]"]

        if self.imports:
            lines.append("## Imports")
            lines.extend(f"  {imp}" for imp in self.imports[:20])  # cap at 20

        if self.classes:
            lines.append("## Classes")
            for cls in self.classes:
                bases = f"({', '.join(cls.bases)})" if cls.bases else ""
                lines.append(f"  class {cls.name}{bases}:")
                if cls.docstring:
                    lines.append(f'    """{cls.docstring[:80]}"""')
                for method in cls.methods:
                    prefix = "async " if method.is_async else ""
                    params = ", ".join(method.parameters)
                    ret = f" -> {method.return_type}" if method.return_type else ""
                    lines.append(f"    {prefix}def {method.name}({params}){ret}")

        if self.functions:
            lines.append("## Functions")
            for fn in self.functions:
                prefix = "async " if fn.is_async else ""
                params = ", ".join(fn.parameters)
                ret = f" -> {fn.return_type}" if fn.return_type else ""
                lines.append(f"  {prefix}def {fn.name}({params}){ret}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class ASTParser:
    """
    Extracts code skeletons from source files.
    Uses tree-sitter when available; falls back to regex heuristics.
    """

    # Map file extensions to language names
    _EXT_MAP: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
    }

    async def extract_skeleton(self, file_path: Path, language: Optional[str] = None) -> CodeSkeleton:
        """
        Parse a source file and return its structural skeleton.

        Args:
            file_path: Absolute or relative path to the source file.
            language: Override language detection (e.g. "python").

        Returns:
            CodeSkeleton with classes, functions, imports extracted.
        """
        lang = language or self._detect_language(file_path)
        skeleton = CodeSkeleton(language=lang, file_path=str(file_path))

        try:
            source = file_path.read_bytes()
        except OSError as exc:
            skeleton.parse_error = str(exc)
            return skeleton

        if _TREE_SITTER_AVAILABLE and lang in _LANGUAGES:
            return self._parse_with_tree_sitter(source, lang, skeleton)
        return self._parse_with_regex(source.decode("utf-8", errors="replace"), lang, skeleton)

    # ------------------------------------------------------------------
    # tree-sitter path
    # ------------------------------------------------------------------

    def _parse_with_tree_sitter(self, source: bytes, lang: str, skeleton: CodeSkeleton) -> CodeSkeleton:
        parser = Parser(_LANGUAGES[lang])
        tree = parser.parse(source)
        root = tree.root_node

        if root.has_error:
            skeleton.parse_error = "tree-sitter reported syntax errors"

        src_lines = source.decode("utf-8", errors="replace").splitlines()

        if lang == "python":
            self._extract_python_ts(root, src_lines, skeleton)
        elif lang in ("javascript", "typescript"):
            self._extract_js_ts(root, src_lines, skeleton)
        elif lang == "java":
            self._extract_java_ts(root, src_lines, skeleton)
        elif lang == "go":
            self._extract_go_ts(root, src_lines, skeleton)
        elif lang == "rust":
            self._extract_rust_ts(root, src_lines, skeleton)

        return skeleton

    def _node_text(self, node, src_lines: list[str]) -> str:
        start_row, start_col = node.start_point
        end_row, end_col = node.end_point
        if start_row == end_row:
            return src_lines[start_row][start_col:end_col]
        parts = [src_lines[start_row][start_col:]]
        for row in range(start_row + 1, end_row):
            parts.append(src_lines[row])
        parts.append(src_lines[end_row][:end_col])
        return "\n".join(parts)

    def _extract_python_ts(self, root, src_lines: list[str], skeleton: CodeSkeleton) -> None:
        for node in root.children:
            kind = node.type
            if kind == "import_statement":
                skeleton.imports.append(self._node_text(node, src_lines))
            elif kind == "import_from_statement":
                skeleton.imports.append(self._node_text(node, src_lines))
            elif kind == "class_definition":
                skeleton.classes.append(self._py_class(node, src_lines))
            elif kind == "function_definition":
                skeleton.functions.append(self._py_function(node, src_lines))
            elif kind == "decorated_definition":
                inner = node.child_by_field_name("definition")
                if inner and inner.type == "class_definition":
                    skeleton.classes.append(self._py_class(inner, src_lines))
                elif inner and inner.type == "function_definition":
                    skeleton.functions.append(self._py_function(inner, src_lines))

    def _py_function(self, node, src_lines: list[str]) -> FunctionSignature:
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")
        ret_node = node.child_by_field_name("return_type")
        is_async = node.parent and node.parent.type == "decorated_definition" or \
                   any(c.type == "async" for c in node.children)

        name = self._node_text(name_node, src_lines) if name_node else "?"
        params: list[str] = []
        if params_node:
            for child in params_node.children:
                if child.type in ("identifier", "typed_parameter", "default_parameter",
                                  "typed_default_parameter", "list_splat_pattern",
                                  "dictionary_splat_pattern"):
                    params.append(self._node_text(child, src_lines))
        ret = self._node_text(ret_node, src_lines).lstrip("->").strip() if ret_node else None
        return FunctionSignature(
            name=name, parameters=params, return_type=ret,
            is_async=bool(is_async), line_number=node.start_point[0] + 1,
        )

    def _py_class(self, node, src_lines: list[str]) -> ClassSignature:
        name_node = node.child_by_field_name("name")
        bases_node = node.child_by_field_name("superclasses")
        body_node = node.child_by_field_name("body")

        name = self._node_text(name_node, src_lines) if name_node else "?"
        bases: list[str] = []
        if bases_node:
            for child in bases_node.children:
                if child.type not in (",", "(", ")"):
                    bases.append(self._node_text(child, src_lines))

        methods: list[FunctionSignature] = []
        if body_node:
            for child in body_node.children:
                if child.type == "function_definition":
                    methods.append(self._py_function(child, src_lines))
                elif child.type == "decorated_definition":
                    inner = child.child_by_field_name("definition")
                    if inner and inner.type == "function_definition":
                        methods.append(self._py_function(inner, src_lines))

        return ClassSignature(
            name=name, bases=bases, methods=methods,
            line_number=node.start_point[0] + 1,
        )

    def _extract_js_ts(self, root, src_lines: list[str], skeleton: CodeSkeleton) -> None:
        """Shallow extraction for JS/TS — covers named functions and classes."""
        for node in self._walk(root):
            if node.type in ("import_statement", "import_declaration"):
                skeleton.imports.append(self._node_text(node, src_lines)[:120])
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                cls = ClassSignature(
                    name=self._node_text(name_node, src_lines) if name_node else "?",
                    line_number=node.start_point[0] + 1,
                )
                skeleton.classes.append(cls)
            elif node.type in ("function_declaration", "function"):
                name_node = node.child_by_field_name("name")
                fn = FunctionSignature(
                    name=self._node_text(name_node, src_lines) if name_node else "anonymous",
                    line_number=node.start_point[0] + 1,
                )
                skeleton.functions.append(fn)

    def _extract_java_ts(self, root, src_lines: list[str], skeleton: CodeSkeleton) -> None:
        for node in self._walk(root):
            if node.type == "import_declaration":
                skeleton.imports.append(self._node_text(node, src_lines)[:120])
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                cls = ClassSignature(
                    name=self._node_text(name_node, src_lines) if name_node else "?",
                    line_number=node.start_point[0] + 1,
                )
                skeleton.classes.append(cls)
            elif node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                fn = FunctionSignature(
                    name=self._node_text(name_node, src_lines) if name_node else "?",
                    line_number=node.start_point[0] + 1,
                )
                skeleton.functions.append(fn)

    def _extract_go_ts(self, root, src_lines: list[str], skeleton: CodeSkeleton) -> None:
        for node in self._walk(root):
            if node.type == "import_declaration":
                skeleton.imports.append(self._node_text(node, src_lines)[:120])
            elif node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                fn = FunctionSignature(
                    name=self._node_text(name_node, src_lines) if name_node else "?",
                    line_number=node.start_point[0] + 1,
                )
                skeleton.functions.append(fn)
            elif node.type == "type_declaration":
                skeleton.constants.append(self._node_text(node, src_lines)[:80])

    def _extract_rust_ts(self, root, src_lines: list[str], skeleton: CodeSkeleton) -> None:
        for node in self._walk(root):
            if node.type == "use_declaration":
                skeleton.imports.append(self._node_text(node, src_lines)[:120])
            elif node.type in ("struct_item", "enum_item", "trait_item", "impl_item"):
                name_node = node.child_by_field_name("name")
                cls = ClassSignature(
                    name=self._node_text(name_node, src_lines) if name_node else node.type,
                    line_number=node.start_point[0] + 1,
                )
                skeleton.classes.append(cls)
            elif node.type == "function_item":
                name_node = node.child_by_field_name("name")
                fn = FunctionSignature(
                    name=self._node_text(name_node, src_lines) if name_node else "?",
                    line_number=node.start_point[0] + 1,
                )
                skeleton.functions.append(fn)

    def _walk(self, node):
        """Breadth-first traversal (shallow — stops at depth 4)."""
        queue = [(node, 0)]
        while queue:
            current, depth = queue.pop(0)
            yield current
            if depth < 4:
                queue.extend((child, depth + 1) for child in current.children)

    # ------------------------------------------------------------------
    # Regex fallback path
    # ------------------------------------------------------------------

    def _parse_with_regex(self, source: str, lang: str, skeleton: CodeSkeleton) -> CodeSkeleton:
        skeleton.parse_error = "tree-sitter unavailable — regex fallback"
        if lang == "python":
            self._regex_python(source, skeleton)
        elif lang in ("javascript", "typescript"):
            self._regex_js(source, skeleton)
        elif lang == "java":
            self._regex_java(source, skeleton)
        elif lang == "go":
            self._regex_go(source, skeleton)
        elif lang == "rust":
            self._regex_rust(source, skeleton)
        return skeleton

    def _regex_python(self, source: str, skeleton: CodeSkeleton) -> None:
        for m in re.finditer(r"^(?:import|from)\s+\S+.*", source, re.MULTILINE):
            skeleton.imports.append(m.group().strip())
        for m in re.finditer(r"^class\s+(\w+)\s*(?:\(([^)]*)\))?:", source, re.MULTILINE):
            skeleton.classes.append(ClassSignature(
                name=m.group(1),
                bases=[b.strip() for b in (m.group(2) or "").split(",") if b.strip()],
                line_number=source[:m.start()].count("\n") + 1,
            ))
        for m in re.finditer(r"^\s*(async\s+)?def\s+(\w+)\s*\(([^)]*)\)", source, re.MULTILINE):
            skeleton.functions.append(FunctionSignature(
                name=m.group(2),
                parameters=[p.strip() for p in m.group(3).split(",") if p.strip()],
                is_async=bool(m.group(1)),
                line_number=source[:m.start()].count("\n") + 1,
            ))

    def _regex_js(self, source: str, skeleton: CodeSkeleton) -> None:
        for m in re.finditer(r"^(?:import|require)\s+.*", source, re.MULTILINE):
            skeleton.imports.append(m.group().strip()[:120])
        for m in re.finditer(r"(?:^|\s)class\s+(\w+)", source, re.MULTILINE):
            skeleton.classes.append(ClassSignature(name=m.group(1)))
        for m in re.finditer(
            r"(?:^|\s)(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", source, re.MULTILINE
        ):
            skeleton.functions.append(FunctionSignature(
                name=m.group(1),
                parameters=[p.strip() for p in m.group(2).split(",") if p.strip()],
            ))

    def _regex_java(self, source: str, skeleton: CodeSkeleton) -> None:
        for m in re.finditer(r"^import\s+[\w.]+;", source, re.MULTILINE):
            skeleton.imports.append(m.group().strip())
        for m in re.finditer(r"(?:public|private|protected)?\s+class\s+(\w+)", source):
            skeleton.classes.append(ClassSignature(name=m.group(1)))
        for m in re.finditer(
            r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)", source
        ):
            skeleton.functions.append(FunctionSignature(
                name=m.group(1),
                parameters=[p.strip() for p in m.group(2).split(",") if p.strip()],
            ))

    def _regex_go(self, source: str, skeleton: CodeSkeleton) -> None:
        for m in re.finditer(r"^import\s+(?:\([\s\S]*?\)|\"[^\"]+\")", source, re.MULTILINE):
            skeleton.imports.append(m.group().strip()[:120])
        for m in re.finditer(r"^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(([^)]*)\)", source, re.MULTILINE):
            skeleton.functions.append(FunctionSignature(
                name=m.group(1),
                parameters=[p.strip() for p in m.group(2).split(",") if p.strip()],
            ))

    def _regex_rust(self, source: str, skeleton: CodeSkeleton) -> None:
        for m in re.finditer(r"^use\s+[\w:{}*]+;", source, re.MULTILINE):
            skeleton.imports.append(m.group().strip()[:120])
        for m in re.finditer(r"^(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)", source, re.MULTILINE):
            skeleton.classes.append(ClassSignature(name=m.group(1)))
        for m in re.finditer(r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\(", source, re.MULTILINE):
            skeleton.functions.append(FunctionSignature(
                name=m.group(1),
                is_async="async" in source[max(0, m.start() - 10):m.start()],
            ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_language(self, file_path: Path) -> str:
        return self._EXT_MAP.get(file_path.suffix.lower(), "unknown")
