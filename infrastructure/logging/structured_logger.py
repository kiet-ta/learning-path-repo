"""
Structured Logger - Infrastructure Layer

Thin wrapper around Python's stdlib logging that emits JSON-structured
records. All infrastructure components receive this logger via constructor
injection — never use module-level logging.getLogger() directly in
infrastructure code.

Why structured logs: downstream tools (Loki, CloudWatch, Splunk) can
parse JSON fields as columns, enabling fast filtering by repo_path,
language, correlation_id etc. without regex parsing.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class StructuredLogger:
    """
    JSON-structured logger wrapping Python stdlib logging.

    Usage:
        logger = StructuredLogger("infrastructure.scanner")
        logger.info("Scanning repository", repo_path="/repos/my-project")
        logger.error("Scan failed", error=exc, repo_path="/repos/my-project")
        logger.log_language_detection("/repos/my-project", "python", {"python": 40})
    """

    def __init__(self, name: str, level: int = logging.INFO) -> None:
        self._logger = logging.getLogger(name)
        self._name = name

        # Attach a JSON handler only once per logger name
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(_JsonFormatter())
            self._logger.addHandler(handler)
            self._logger.propagate = False

        self._logger.setLevel(level)

    # ------------------------------------------------------------------
    # Core log methods
    # ------------------------------------------------------------------

    def debug(self, message: str, **context: Any) -> None:
        """Log at DEBUG level with optional structured context fields."""
        self._emit(logging.DEBUG, message, **context)

    def info(self, message: str, **context: Any) -> None:
        """Log at INFO level with optional structured context fields."""
        self._emit(logging.INFO, message, **context)

    def warning(self, message: str, **context: Any) -> None:
        """Log at WARNING level with optional structured context fields."""
        self._emit(logging.WARNING, message, **context)

    def log(self, message: str, **context: Any) -> None:
        """Alias for info — matches the interface expected by LanguageDetector."""
        self.info(message, **context)

    def error(self, message: str, error: Optional[Exception] = None, **context: Any) -> None:
        """
        Log at ERROR level with optional exception detail.

        Args:
            message: Human-readable error description.
            error:   The exception instance (optional). Its type and str() are
                     added to the structured record automatically.
            **context: Additional key-value fields to include in the JSON record.
        """
        if error is not None:
            context["error_type"] = type(error).__name__
            context["error_detail"] = str(error)
        self._emit(logging.ERROR, message, **context)

    # ------------------------------------------------------------------
    # Domain-specific convenience methods
    # ------------------------------------------------------------------

    def log_language_detection(
        self,
        repo_path: str,
        primary_language: str,
        distribution: Dict[str, int],
    ) -> None:
        """
        Emit a structured INFO record for language detection results.

        Called by LanguageDetector after successfully detecting the primary
        language of a repository.
        """
        self.info(
            "Language detection complete",
            repo_path=repo_path,
            primary_language=primary_language,
            language_distribution=distribution,
            total_language_count=len(distribution),
        )

    def log_scan_start(self, repo_path: str, max_depth: int) -> None:
        """Emit INFO record when a repository scan begins."""
        self.info("Starting repository scan", repo_path=repo_path, max_depth=max_depth)

    def log_scan_complete(self, repo_path: str, file_count: int, duration_ms: float) -> None:
        """Emit INFO record when a repository scan completes."""
        self.info(
            "Repository scan complete",
            repo_path=repo_path,
            file_count=file_count,
            duration_ms=round(duration_ms, 2),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, level: int, message: str, **context: Any) -> None:
        """Build structured record and forward to stdlib logger."""
        extra = {"structured_context": context}
        self._logger.log(level, message, extra=extra)


class _JsonFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Output example:
        {"ts": "2026-02-27T10:00:00Z", "level": "INFO", "logger": "scanner",
         "message": "Language detection complete", "primary_language": "python"}
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: Dict[str, Any] = {
            "ts": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge any structured context fields
        context = getattr(record, "structured_context", {})
        payload.update(context)

        # Include exception traceback if present
        if record.exc_info:
            payload["traceback"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def get_logger(name: str, level: int = logging.INFO) -> StructuredLogger:
    """
    Factory function for obtaining a StructuredLogger.

    Preferred over direct instantiation so callers don't need to import
    the class — just import get_logger.

    Example:
        from infrastructure.logging import get_logger
        logger = get_logger(__name__)
    """
    return StructuredLogger(name, level)
