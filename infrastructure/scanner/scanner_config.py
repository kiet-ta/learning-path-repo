"""
Scanner Configuration - Infrastructure Layer

Centralises all scanner behaviour policy: which directories to skip, which
file types to ignore, size limits, and the authoritative extension → language
mapping used by LanguageDetector.

Separating policy from the scanner classes (SRP) allows configuration to be
swapped in tests without touching the detection or file-system code.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set


# ---------------------------------------------------------------------------
# Default policy sets (module-level constants, not mutable class defaults)
# ---------------------------------------------------------------------------

_DEFAULT_IGNORE_DIRS: FrozenSet[str] = frozenset(
    {
        ".git", ".hg", ".svn", ".bzr",
        "node_modules", ".npm", ".yarn",
        "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        ".tox", ".nox", "venv", ".venv", "env", ".env",
        "dist", "build", "target", "out", ".next", ".nuxt",
        "vendor", "third_party", "site-packages",
        ".idea", ".vscode", ".vs",
        "coverage", ".nyc_output", "htmlcov",
        ".terraform", ".serverless",
    }
)

_BINARY_EXTENSIONS: FrozenSet[str] = frozenset(
    {
        # Images
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".svg",
        # Archives
        ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
        # Compiled / binary
        ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".class", ".o", ".a",
        ".wasm", ".elf",
        # Media
        ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
        # Documents
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        # Fonts
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
        # Misc binary
        ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
    }
)

# Canonical extension → language name mapping.
# Language names match the supported_languages set in domain/entities/repository.py.
_EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    # Python
    ".py": "python", ".pyw": "python", ".pyx": "python",
    # JavaScript / TypeScript
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript",
    # Java / JVM
    ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala",
    ".groovy": "java",
    # C / C++
    ".c": "c", ".h": "c",
    ".cpp": "c++", ".cc": "c++", ".cxx": "c++", ".hpp": "c++", ".hxx": "c++",
    # C#
    ".cs": "c#",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # Swift
    ".swift": "swift",
    # PHP
    ".php": "php",
    # Ruby
    ".rb": "ruby", ".rake": "ruby", ".gemspec": "ruby",
    # R
    ".r": "r", ".R": "r",
    # MATLAB
    ".m": "matlab",
    # Shell
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".fish": "shell",
    # Markup / config
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css", ".sass": "css", ".less": "css",
    ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".jsonc": "json",
    ".toml": "yaml",
    ".xml": "yaml",
    # Infra
    ".tf": "yaml",        # Terraform (maps to yaml as catch-all infra)
    ".hcl": "yaml",
}


@dataclass
class ScannerConfig:
    """
    Policy object for the infrastructure scanner subsystem.

    All fields have sensible defaults — callers only need to override the
    fields relevant to their scanning scenario.

    Attributes:
        ignore_dirs:       Directory names to skip during recursive walk.
        ignore_extensions: File extensions that should not be scanned.
        max_depth:         Maximum directory recursion depth (1-based).
        max_file_size_mb:  Files larger than this (megabytes) are skipped.
        min_file_size_bytes: Files smaller than this are skipped (avoids stubs).
        follow_symlinks:   Whether to follow symbolic links during walk.
    """

    ignore_dirs: List[str] = field(
        default_factory=lambda: list(_DEFAULT_IGNORE_DIRS)
    )
    ignore_extensions: List[str] = field(
        default_factory=lambda: list(_BINARY_EXTENSIONS)
    )
    max_depth: int = 10
    max_file_size_mb: float = 10.0
    min_file_size_bytes: int = 1
    follow_symlinks: bool = False

    # Allow callers to inject extra extension mappings (e.g., project-specific DSLs)
    extra_extension_map: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate configuration bounds."""
        if not 1 <= self.max_depth <= 50:
            raise ValueError(f"max_depth must be between 1 and 50, got {self.max_depth}")
        if self.max_file_size_mb <= 0:
            raise ValueError("max_file_size_mb must be positive")

    # ------------------------------------------------------------------
    # Query methods — used by LanguageDetector
    # ------------------------------------------------------------------

    def should_ignore_directory(self, name: str) -> bool:
        """Return True if a directory should be excluded from scanning.

        Args:
            name: Directory base name (not full path).
        """
        return name in self.ignore_dirs or name.startswith(".")

    def is_binary_file(self, file_path: Path) -> bool:
        """Return True if the file is likely binary (non-text).

        Decision is based on file extension only — no file-open required,
        keeping the method fast for large trees.

        Args:
            file_path: Full or relative path to the file.
        """
        return file_path.suffix.lower() in self.ignore_extensions

    def get_language_from_extension(self, extension: str) -> str:
        """Map a file extension to a canonical language name.

        Args:
            extension: File extension including the leading dot, e.g. ".py".

        Returns:
            Lowercase language name matching the domain entity vocabulary,
            or "unknown" if the extension is not recognised.
        """
        ext_lower = extension.lower()

        # Caller-supplied overrides take priority
        if ext_lower in self.extra_extension_map:
            return self.extra_extension_map[ext_lower]

        return _EXTENSION_LANGUAGE_MAP.get(ext_lower, "unknown")

    def get_effective_ignore_dirs(self) -> Set[str]:
        """Return ignore_dirs as a set for O(1) lookup."""
        return set(self.ignore_dirs)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> "ScannerConfig":
        """Return a ScannerConfig with project defaults."""
        return cls()

    @classmethod
    def for_testing(cls) -> "ScannerConfig":
        """Return a permissive ScannerConfig suitable for unit tests."""
        return cls(
            ignore_dirs=[".git"],
            ignore_extensions=[],
            max_depth=5,
            max_file_size_mb=1.0,
        )
