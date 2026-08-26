"""PentaError public runtime surface."""
from penta_observability import PentaError, Severity, normalize_error, dead_letter_payload, redact
__all__ = ["PentaError", "Severity", "normalize_error", "dead_letter_payload", "redact"]
