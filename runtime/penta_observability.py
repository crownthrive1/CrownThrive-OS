#!/usr/bin/env python3
"""Penta observability runtime: errors, structured logs, traces and metrics.

Stdlib-only, fail-closed primitives designed for CrownThrive/PENTA runtimes.
No provider authority is manufactured here: this module emits local evidence
and payloads that downstream certified routes may persist or deliver.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
import json
import re
import secrets
import threading
import time
from typing import Any, Callable, Iterator, Mapping, MutableMapping, TypeVar


REDACTED = "[REDACTED]"
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\b(?:sk|pk)-(?:live|test|proj)-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
)
_SECRET_KEYS = {
    "authorization", "proxy-authorization", "cookie", "set-cookie", "password",
    "passwd", "secret", "token", "client_secret", "api_key", "apikey", "access_token",
    "refresh_token", "id_token", "private_key", "stream_key", "webhook_secret",
}


class Severity(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    @classmethod
    def coerce(cls, value: "Severity | str | int") -> "Severity":
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        return cls[str(value).strip().upper()]


def _secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9_-]", "", key.casefold())
    if normalized in _SECRET_KEYS:
        return True
    return any(normalized.endswith(suffix) for suffix in ("_password", "_secret", "_token", "_api_key", "_private_key"))


def _redact_string(value: str) -> str:
    redacted = value
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.pattern.lower().startswith("(?i)\\b(bearer"):
            redacted = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", redacted)
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact(value: Any, *, max_depth: int = 8, _depth: int = 0) -> Any:
    """Return a JSON-safe, recursively redacted copy of ``value``."""
    if _depth >= max_depth:
        return "[MAX_DEPTH]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            out[key] = REDACTED if _secret_key(key) else redact(raw_value, max_depth=max_depth, _depth=_depth + 1)
        return out
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact(item, max_depth=max_depth, _depth=_depth + 1) for item in value]
    if isinstance(value, BaseException):
        return {"type": type(value).__name__, "message": _redact_string(str(value))}
    return _redact_string(repr(value))


@dataclass(frozen=True)
class TraceContext:
    trace_id: str = field(default_factory=lambda: secrets.token_hex(16))
    correlation_id: str = field(default_factory=lambda: secrets.token_hex(12))
    span_id: str = field(default_factory=lambda: secrets.token_hex(8))
    parent_span_id: str | None = None

    def child(self) -> "TraceContext":
        return TraceContext(
            trace_id=self.trace_id,
            correlation_id=self.correlation_id,
            parent_span_id=self.span_id,
        )

    def as_dict(self) -> dict[str, str | None]:
        return {
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
        }


_current_trace: ContextVar[TraceContext | None] = ContextVar("penta_trace", default=None)


def current_trace(*, create: bool = True) -> TraceContext | None:
    trace = _current_trace.get()
    if trace is None and create:
        trace = TraceContext()
        _current_trace.set(trace)
    return trace


@contextmanager
def bind_trace(trace: TraceContext | None = None, *, child: bool = False) -> Iterator[TraceContext]:
    selected = trace or current_trace() or TraceContext()
    if child:
        selected = selected.child()
    token = _current_trace.set(selected)
    try:
        yield selected
    finally:
        _current_trace.reset(token)


class PentaError(Exception):
    """Canonical safe error object for PENTA execution paths."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "PENTA_RUNTIME_ERROR",
        safe_message: str | None = None,
        severity: Severity | str | int = Severity.ERROR,
        retryable: bool = False,
        status_code: int | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        if not _ERROR_CODE.fullmatch(code):
            raise ValueError(f"invalid Penta error code: {code!r}")
        if status_code is not None and not 100 <= status_code <= 599:
            raise ValueError("status_code must be between 100 and 599")
        super().__init__(message)
        self.code = code
        self.safe_message = safe_message or "The operation could not be completed."
        self.severity = Severity.coerce(severity)
        self.retryable = bool(retryable)
        self.status_code = status_code
        self.context = dict(context or {})
        self.cause = cause

    def envelope(self, *, include_internal: bool = False, trace: TraceContext | None = None) -> dict[str, Any]:
        trace = trace or current_trace()
        payload: dict[str, Any] = {
            "schema": "ct.penta.error.v1",
            "code": self.code,
            "message": self.safe_message,
            "severity": self.severity.name.lower(),
            "retryable": self.retryable,
            "status_code": self.status_code,
            "trace": trace.as_dict() if trace else None,
            "context": redact(self.context),
        }
        if include_internal:
            payload["internal"] = {
                "message": _redact_string(str(self)),
                "type": type(self).__name__,
                "cause": redact(self.cause) if self.cause else None,
            }
        return payload


def normalize_error(
    exc: BaseException,
    *,
    code: str = "PENTA_UNHANDLED_ERROR",
    context: Mapping[str, Any] | None = None,
) -> PentaError:
    if isinstance(exc, PentaError):
        if context:
            exc.context.update(context)
        return exc
    return PentaError(
        str(exc) or type(exc).__name__,
        code=code,
        safe_message="An internal operation failed.",
        severity=Severity.ERROR,
        retryable=False,
        context=context,
        cause=exc,
    )


Sink = Callable[[str], None]


class PentaLogger:
    """Structured JSON-line logger with mandatory redaction and trace binding."""

    def __init__(
        self,
        *,
        service: str,
        penta_member: str | None = None,
        environment: str = "production",
        minimum_severity: Severity | str | int = Severity.INFO,
        sink: Sink | None = None,
        base_context: Mapping[str, Any] | None = None,
    ) -> None:
        if not service.strip():
            raise ValueError("service is required")
        self.service = service.strip()
        self.penta_member = penta_member
        self.environment = environment
        self.minimum_severity = Severity.coerce(minimum_severity)
        self.sink = sink or print
        self.base_context = dict(base_context or {})

    def child(self, **context: Any) -> "PentaLogger":
        merged = {**self.base_context, **context}
        return PentaLogger(
            service=self.service,
            penta_member=self.penta_member,
            environment=self.environment,
            minimum_severity=self.minimum_severity,
            sink=self.sink,
            base_context=merged,
        )

    def emit(
        self,
        severity: Severity | str | int,
        message: str,
        *,
        event: str = "runtime.event",
        context: Mapping[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> dict[str, Any] | None:
        level = Severity.coerce(severity)
        if level < self.minimum_severity:
            return None
        trace = current_trace()
        merged_context = {**self.base_context, **dict(context or {})}
        payload: dict[str, Any] = {
            "schema": "ct.penta.log.v1",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "severity": level.name.lower(),
            "event": event,
            "message": _redact_string(str(message)),
            "service": self.service,
            "penta_member": self.penta_member,
            "environment": self.environment,
            "trace": trace.as_dict() if trace else None,
            "context": redact(merged_context),
        }
        if error is not None:
            normalized = normalize_error(error)
            payload["error"] = normalized.envelope(include_internal=True, trace=trace)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.sink(line)
        return payload

    def debug(self, message: str, **kwargs: Any): return self.emit(Severity.DEBUG, message, **kwargs)
    def info(self, message: str, **kwargs: Any): return self.emit(Severity.INFO, message, **kwargs)
    def warning(self, message: str, **kwargs: Any): return self.emit(Severity.WARNING, message, **kwargs)
    def error(self, message: str, **kwargs: Any): return self.emit(Severity.ERROR, message, **kwargs)
    def critical(self, message: str, **kwargs: Any): return self.emit(Severity.CRITICAL, message, **kwargs)


class MetricRegistry:
    """Thread-safe in-process metric evidence; export is delegated downstream."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: MutableMapping[str, float] = {}
        self._gauges: MutableMapping[str, float] = {}
        self._observations: MutableMapping[str, list[float]] = {}

    @staticmethod
    def _name(name: str) -> str:
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.-]{0,127}", name):
            raise ValueError(f"invalid metric name: {name!r}")
        return name

    def increment(self, name: str, value: float = 1.0) -> float:
        name = self._name(name)
        if value < 0:
            raise ValueError("counter increments cannot be negative")
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + float(value)
            return self._counters[name]

    def gauge(self, name: str, value: float) -> float:
        name = self._name(name)
        with self._lock:
            self._gauges[name] = float(value)
            return self._gauges[name]

    def observe(self, name: str, value: float) -> None:
        name = self._name(name)
        with self._lock:
            self._observations.setdefault(name, []).append(float(value))

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - started)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            observations = {
                name: {
                    "count": len(values),
                    "sum": sum(values),
                    "min": min(values) if values else None,
                    "max": max(values) if values else None,
                    "avg": (sum(values) / len(values)) if values else None,
                }
                for name, values in self._observations.items()
            }
            return {
                "schema": "ct.penta.metrics.v1",
                "counters": dict(sorted(self._counters.items())),
                "gauges": dict(sorted(self._gauges.items())),
                "observations": dict(sorted(observations.items())),
            }


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    retryable_codes: frozenset[str] = frozenset()

    def allows(self, error: PentaError, attempt: int) -> bool:
        if attempt < 1:
            raise ValueError("attempt is 1-based")
        if attempt >= self.max_attempts:
            return False
        return error.retryable and (not self.retryable_codes or error.code in self.retryable_codes)


T = TypeVar("T")


def guard_call(
    logger: PentaLogger,
    operation: str,
    func: Callable[..., T],
    *args: Any,
    metrics: MetricRegistry | None = None,
    **kwargs: Any,
) -> T:
    """Run one operation with trace/log/metric evidence and normalized failure."""
    with bind_trace(current_trace()):
        started = time.perf_counter()
        logger.info("operation started", event="operation.start", context={"operation": operation})
        try:
            result = func(*args, **kwargs)
        except BaseException as exc:
            err = normalize_error(exc, context={"operation": operation})
            if metrics:
                metrics.increment("penta.operations.failed")
                metrics.observe("penta.operations.duration_seconds", time.perf_counter() - started)
            logger.error("operation failed", event="operation.failure", context={"operation": operation}, error=err)
            raise err from exc
        if metrics:
            metrics.increment("penta.operations.succeeded")
            metrics.observe("penta.operations.duration_seconds", time.perf_counter() - started)
        logger.info("operation completed", event="operation.success", context={"operation": operation})
        return result


def dead_letter_payload(operation: str, payload: Any, error: BaseException) -> dict[str, Any]:
    normalized = normalize_error(error, context={"operation": operation})
    trace = current_trace()
    return {
        "schema": "ct.penta.dead-letter.v1",
        "operation": operation,
        "trace": trace.as_dict() if trace else None,
        "error": normalized.envelope(include_internal=False, trace=trace),
        "payload": redact(payload),
    }


def self_test() -> dict[str, Any]:
    lines: list[str] = []
    logger = PentaLogger(service="penta-observability-self-test", penta_member="penta.logger", sink=lines.append)
    metrics = MetricRegistry()
    checks: dict[str, bool] = {}
    with bind_trace(TraceContext(correlation_id="self-test-correlation")) as trace:
        logger.info("probe", event="self_test.probe", context={"api_key": "do-not-leak", "safe": "ok"})
        parsed = json.loads(lines[-1])
        checks["structured_log"] = parsed["schema"] == "ct.penta.log.v1"
        checks["redaction"] = parsed["context"]["api_key"] == REDACTED and "do-not-leak" not in lines[-1]
        checks["trace"] = parsed["trace"]["correlation_id"] == trace.correlation_id
        checks["guard"] = guard_call(logger, "self-test", lambda: 42, metrics=metrics) == 42
        err = PentaError("provider timed out", code="PENTA_PROVIDER_TIMEOUT", retryable=True, context={"token": "secret"})
        checks["error_envelope"] = err.envelope()["context"]["token"] == REDACTED
        checks["retry"] = RetryPolicy(max_attempts=3).allows(err, 1) and not RetryPolicy(max_attempts=1).allows(err, 1)
        dlq = dead_letter_payload("self-test", {"password": "secret"}, err)
        checks["dead_letter_redaction"] = dlq["payload"]["password"] == REDACTED
        checks["metrics"] = metrics.snapshot()["counters"]["penta.operations.succeeded"] == 1.0
    return {
        "schema": "ct.penta.observability.self-test.v1",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Penta observability runtime")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
