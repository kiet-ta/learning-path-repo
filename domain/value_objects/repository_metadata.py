"""
Repository Metadata Value Object - Clean Architecture Domain Layer

Encapsulates all quantitative metadata about a repository's codebase.
Frozen (immutable) — all updates produce a new instance via update_from_analysis().

Why a value object: metadata has no identity; equality is determined entirely by
its fields. Two metadata objects with identical numbers describe the same state.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass(frozen=True)
class RepositoryMetadata:
    """
    Immutable value object holding repository analysis metadata.

    Populated by the infrastructure scanner layer after file-system analysis.
    Used by domain entities (Repository) to compute complexity and learning hours.
    """

    # Code size metrics
    lines_of_code: int = 0
    file_count: int = 0

    # Dependency information
    dependencies: List[str] = field(default_factory=list)

    # Quality signals
    has_tests: bool = False
    has_ci: bool = False
    has_documentation: bool = False

    # Language distribution (e.g., {"python": 80, "yaml": 15, "shell": 5})
    language_distribution: Dict[str, int] = field(default_factory=dict)

    # Additional raw data captured during scan
    extra: Dict[str, Any] = field(default_factory=dict)

    def update_from_analysis(self, content_data: Dict[str, Any]) -> "RepositoryMetadata":
        """
        Return a new RepositoryMetadata instance merged with content_data.

        Callers must reassign the result — this object is immutable.

        Args:
            content_data: Dict from scanner/AI analysis containing any subset of
                          fields: lines_of_code, file_count, dependencies,
                          has_tests, has_ci, has_documentation, language_distribution.

        Returns:
            New RepositoryMetadata with updated fields; unchanged fields retain
            current values.
        """
        return RepositoryMetadata(
            lines_of_code=content_data.get("lines_of_code", self.lines_of_code),
            file_count=content_data.get("file_count", self.file_count),
            dependencies=list(content_data.get("dependencies", self.dependencies)),
            has_tests=content_data.get("has_tests", self.has_tests),
            has_ci=content_data.get("has_ci", self.has_ci),
            has_documentation=content_data.get("has_documentation", self.has_documentation),
            language_distribution=dict(
                content_data.get("language_distribution", self.language_distribution)
            ),
            extra={**self.extra, **content_data.get("extra", {})},
        )

    @property
    def dependency_count(self) -> int:
        """Convenience property for len(dependencies)."""
        return len(self.dependencies)

    @property
    def is_large_codebase(self) -> bool:
        """True if codebase exceeds 10k lines — affects complexity score."""
        return self.lines_of_code > 10_000

    @property
    def is_medium_codebase(self) -> bool:
        """True if codebase is 1k–10k lines."""
        return 1_000 <= self.lines_of_code <= 10_000

    def __repr__(self) -> str:
        return (
            f"RepositoryMetadata("
            f"loc={self.lines_of_code}, "
            f"files={self.file_count}, "
            f"deps={self.dependency_count}, "
            f"has_tests={self.has_tests})"
        )
