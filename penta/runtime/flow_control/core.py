"""Deterministic provider-neutral flow control for CrownThrive factory work.

This reference runtime deliberately has no network, provider, credential,
payment, deployment, merge, or certification behavior.  Callers supply an
explicit clock and perform external effects through separately governed and
certified adapters after receiving a bounded lease.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any, Iterable, Mapping, Sequence


class FlowControlError(RuntimeError):
    """Base error for a fail-closed flow-control decision."""


class QueueCapacityError(FlowControlError):
    """The bounded resident queue has no admission capacity."""


class AdmissionConflict(FlowControlError):
    """An idempotency key was reused with a different request."""


class AuthorityError(FlowControlError):
    """The exact authority receipt is missing, expired, revoked, or out of scope."""


class StaleLoadError(FlowControlError):
    """No candidate route has fresh capacity evidence."""


class BackpressureError(FlowControlError):
    """Fresh candidate routes exist, but none has available capacity."""


class CostCeilingError(FlowControlError):
    """The route's internal resource-unit ceiling would be exceeded."""


class LeaseError(FlowControlError):
    """A lease is absent, expired, or fenced by a newer claim."""


class RetentionCapacityError(FlowControlError):
    """A bounded evidence or history store is full and must fail closed."""


MAX_UNIT = (1 << 63) - 1


class ImmutableJSONDict(dict[str, Any]):
    """A JSON-serializable mapping that rejects every post-build mutation."""

    @staticmethod
    def _immutable(*_args: Any, **_kwargs: Any) -> None:
        raise TypeError("immutable JSON mapping")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


class ImmutableJSONList(list[Any]):
    """A JSON-serializable sequence that rejects every post-build mutation."""

    @staticmethod
    def _immutable(*_args: Any, **_kwargs: Any) -> None:
        raise TypeError("immutable JSON sequence")

    __setitem__ = _immutable
    __delitem__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable


def _json_plain(value: Any, *, field_name: str = "value") -> Any:
    """Return a detached JSON value, rejecting ambiguous/non-finite inputs."""
    if isinstance(value, Mapping):
        plain: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} object keys must be strings")
            plain[key] = _json_plain(item, field_name=field_name)
        return plain
    if isinstance(value, (list, tuple)):
        return [_json_plain(item, field_name=field_name) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError(f"{field_name} must contain only finite JSON values")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_plain(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _nonempty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    value = value.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{field_name} may not contain control characters")
    if len(value) > 240:
        raise ValueError(f"{field_name} may not exceed 240 characters")
    return value


def _exact_scope(value: str, field_name: str = "scope") -> str:
    scope = _nonempty(value, field_name)
    if "*" in scope:
        raise ValueError(f"{field_name} must be exact; wildcard scope is not supported")
    return scope


def _integer(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _timestamp(value: int, field_name: str) -> int:
    return _integer(value, field_name)


def _unit(value: int, field_name: str) -> int:
    value = _integer(value, field_name)
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    if value > MAX_UNIT:
        raise OverflowError(f"{field_name} exceeds the signed 64-bit unit ceiling")
    return value


def _positive_int(value: int, field_name: str, *, maximum: int | None = None) -> int:
    value = _integer(value, field_name)
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field_name} must be no greater than {maximum}")
    return value


def _freeze_json(value: Any, *, field_name: str = "value") -> Any:
    """Deep-freeze a detached JSON value for immutable public/runtime custody."""
    plain = _json_plain(value, field_name=field_name)

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return ImmutableJSONDict({key: freeze(item[key]) for key in sorted(item)})
        if isinstance(item, list):
            return ImmutableJSONList(freeze(child) for child in item)
        return item

    return freeze(plain)


def _plain_json(value: Any) -> Any:
    """Return detached built-in JSON containers for contract serialization."""
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain_json(item) for item in value]
    return value


def _freeze_mapping(value: Mapping[str, Any], *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    frozen = _freeze_json(value, field_name=field_name)
    if not isinstance(frozen, Mapping):  # pragma: no cover - root check is defensive
        raise ValueError(f"{field_name} must be a mapping")
    return frozen


def _checked_add(left: int, right: int, field_name: str) -> int:
    result = left + right
    if result > MAX_UNIT:
        raise OverflowError(f"{field_name} exceeds the signed 64-bit unit ceiling")
    return result


def _checked_mul(left: int, right: int, field_name: str) -> int:
    result = left * right
    if result > MAX_UNIT:
        raise OverflowError(f"{field_name} exceeds the signed 64-bit unit ceiling")
    return result


@dataclass(frozen=True)
class AuthorityReceipt:
    """Time-bounded evidence bound to one configured issuer and environment.

    The binding digest protects the receipt fields in this controlled-test
    runtime.  It is not a signature and does not authenticate the issuer.
    """

    receipt_id: str
    subject_id: str
    scopes: tuple[str, ...]
    not_before: int
    expires_at: int
    evidence_ref: str
    issuer_id: str
    environment_id: str
    revoked_at: int | None = None
    revocation_reason: str | None = None
    evidence_binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        receipt_id = _nonempty(self.receipt_id, "receipt_id")
        subject_id = _nonempty(self.subject_id, "subject_id")
        evidence_ref = _nonempty(self.evidence_ref, "evidence_ref")
        issuer_id = _nonempty(self.issuer_id, "issuer_id")
        environment_id = _nonempty(self.environment_id, "environment_id")
        not_before = _timestamp(self.not_before, "not_before")
        expires_at = _timestamp(self.expires_at, "expires_at")
        if isinstance(self.scopes, (str, bytes)) or not isinstance(self.scopes, Sequence):
            raise ValueError("scopes must be a sequence of exact scope strings")
        if not self.scopes:
            raise ValueError("scopes must contain at least one exact non-empty scope")
        scopes = tuple(_exact_scope(scope) for scope in self.scopes)
        if len(set(scopes)) != len(scopes):
            raise ValueError("scopes must be unique")
        if expires_at <= not_before:
            raise ValueError("expires_at must be later than not_before")
        if self.revoked_at is not None:
            _timestamp(self.revoked_at, "revoked_at")
        if self.revoked_at is not None and not self.revocation_reason:
            raise ValueError("a revoked receipt requires a revocation_reason")
        if self.revoked_at is None and self.revocation_reason is not None:
            raise ValueError("revocation_reason requires revoked_at")
        if self.revocation_reason is not None:
            _nonempty(self.revocation_reason, "revocation_reason")
        object.__setattr__(self, "receipt_id", receipt_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "scopes", tuple(scopes))
        object.__setattr__(self, "evidence_ref", evidence_ref)
        object.__setattr__(self, "issuer_id", issuer_id)
        object.__setattr__(self, "environment_id", environment_id)
        object.__setattr__(
            self,
            "evidence_binding_digest",
            _sha256(
                {
                    "receipt_id": receipt_id,
                    "subject_id": subject_id,
                    "scopes": scopes,
                    "not_before": not_before,
                    "expires_at": expires_at,
                    "evidence_ref": evidence_ref,
                    "issuer_id": issuer_id,
                    "environment_id": environment_id,
                }
            ),
        )

    def permits(self, scope: str, now: int) -> bool:
        try:
            scope = _exact_scope(scope)
            now = _timestamp(now, "now")
        except ValueError:
            return False
        return (
            scope in self.scopes
            and self.not_before <= now < self.expires_at
            and (self.revoked_at is None or now < self.revoked_at)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ct.penta.runtime-flow-control.authority-receipt.v1",
            "receipt_id": self.receipt_id,
            "subject_id": self.subject_id,
            "scopes": list(self.scopes),
            "not_before": self.not_before,
            "expires_at": self.expires_at,
            "evidence_ref": self.evidence_ref,
            "issuer_id": self.issuer_id,
            "environment_id": self.environment_id,
            "evidence_binding_digest": self.evidence_binding_digest,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
        }


class AuthorityReceiptStore:
    """Environment/issuer-bound receipt registry; never an authority issuer."""

    def __init__(
        self,
        *,
        environment_id: str,
        trusted_issuer_ids: Sequence[str],
        max_receipts: int = 10_000,
    ) -> None:
        self.environment_id = _nonempty(environment_id, "environment_id")
        if isinstance(trusted_issuer_ids, (str, bytes)) or not isinstance(
            trusted_issuer_ids, Sequence
        ):
            raise ValueError("trusted_issuer_ids must be a sequence")
        issuers = tuple(sorted({_nonempty(item, "trusted_issuer_id") for item in trusted_issuer_ids}))
        if not issuers:
            raise ValueError("trusted_issuer_ids must contain at least one configured issuer")
        self.trusted_issuer_ids = issuers
        self._max_receipts = _positive_int(max_receipts, "max_receipts")
        self._receipts: dict[str, AuthorityReceipt] = {}
        self._lock = threading.RLock()

    @property
    def max_receipts(self) -> int:
        return self._max_receipts

    def register(self, receipt: AuthorityReceipt) -> AuthorityReceipt:
        if not isinstance(receipt, AuthorityReceipt):
            raise AuthorityError("authority receipt has an unsupported type")
        with self._lock:
            if receipt.environment_id != self.environment_id:
                raise AuthorityError("authority receipt environment does not match runtime")
            if receipt.issuer_id not in self.trusted_issuer_ids:
                raise AuthorityError("authority receipt issuer is not in the configured allowlist")
            prior = self._receipts.get(receipt.receipt_id)
            if prior is not None and prior != receipt:
                raise AuthorityError("authority receipt id conflicts with an existing record")
            if prior is None and len(self._receipts) >= self.max_receipts:
                raise RetentionCapacityError("bounded authority-receipt registry is full")
            self._receipts[receipt.receipt_id] = receipt
            return receipt

    def revoke(self, receipt_id: str, *, now: int, reason: str) -> AuthorityReceipt:
        receipt_id = _nonempty(receipt_id, "receipt_id")
        now = _timestamp(now, "now")
        reason = _nonempty(reason, "reason")
        with self._lock:
            receipt = self._receipts.get(receipt_id)
            if receipt is None:
                raise AuthorityError("authority receipt is unknown")
            if receipt.revoked_at is not None:
                return receipt
            revoked = replace(receipt, revoked_at=now, revocation_reason=reason)
            self._receipts[receipt_id] = revoked
            return revoked

    def require(self, receipt_id: str, *, subject_id: str, scope: str, now: int) -> AuthorityReceipt:
        receipt_id = _nonempty(receipt_id, "receipt_id")
        subject_id = _nonempty(subject_id, "subject_id")
        scope = _exact_scope(scope)
        now = _timestamp(now, "now")
        with self._lock:
            receipt = self._receipts.get(receipt_id)
            if receipt is None:
                raise AuthorityError("authority receipt is unknown")
            if receipt.subject_id != subject_id:
                raise AuthorityError("authority receipt subject does not match worker")
            if not receipt.permits(scope, now):
                raise AuthorityError("authority receipt is not currently valid for the exact scope")
            return receipt

    def summary(self) -> Mapping[str, Any]:
        with self._lock:
            return ImmutableJSONDict(
                {
                    "environment_id": self.environment_id,
                    "configured_issuer_count": len(self.trusted_issuer_ids),
                    "registered_receipt_count": len(self._receipts),
                    "max_receipts": self.max_receipts,
                    "revoked_receipt_count": sum(
                        receipt.revoked_at is not None for receipt in self._receipts.values()
                    ),
                    "issuer_authentication": False,
                    "production_authority": False,
                }
            )


@dataclass(frozen=True)
class LoadSnapshot:
    route_id: str
    capacity: int
    reported_inflight: int
    observed_at: int
    ttl_seconds: int
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", _nonempty(self.route_id, "route_id"))
        capacity = _unit(self.capacity, "capacity")
        reported_inflight = _unit(self.reported_inflight, "reported_inflight")
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at, "observed_at"))
        object.__setattr__(self, "ttl_seconds", _positive_int(self.ttl_seconds, "ttl_seconds"))
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        if reported_inflight > capacity:
            raise ValueError("reported_inflight may not exceed capacity")

    def fresh(self, now: int) -> bool:
        now = _timestamp(now, "now")
        return self.observed_at <= now < self.observed_at + self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ct.penta.runtime-flow-control.load-snapshot.v1",
            "route_id": self.route_id,
            "capacity": self.capacity,
            "reported_inflight": self.reported_inflight,
            "observed_at": self.observed_at,
            "ttl_seconds": self.ttl_seconds,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class RouteCapacity:
    route_id: str
    capacity: int
    used: int
    available: int
    observed_at: int

    @property
    def utilization(self) -> Fraction:
        if self.capacity == 0:
            return Fraction(1, 1)
        return Fraction(self.used, self.capacity)


class PentaLoad:
    """Freshness-gated route capacity and local in-flight reservations."""

    def __init__(self, *, max_routes: int = 1_000) -> None:
        self._max_routes = _positive_int(max_routes, "max_routes")
        self._snapshots: dict[str, LoadSnapshot] = {}
        self._local_inflight: dict[str, int] = {}
        self._lock = threading.RLock()

    @property
    def max_routes(self) -> int:
        return self._max_routes

    def observe(self, snapshot: LoadSnapshot) -> None:
        if not isinstance(snapshot, LoadSnapshot):
            raise ValueError("snapshot must be a LoadSnapshot")
        with self._lock:
            prior = self._snapshots.get(snapshot.route_id)
            if prior is None and len(self._snapshots) >= self.max_routes:
                raise RetentionCapacityError("bounded load-snapshot registry is full")
            if prior is not None and snapshot.observed_at < prior.observed_at:
                raise StaleLoadError("older load evidence cannot replace a newer snapshot")
            if (
                prior is not None
                and snapshot.observed_at == prior.observed_at
                and snapshot != prior
            ):
                raise StaleLoadError(
                    "conflicting load evidence at the same route timestamp fails closed"
                )
            self._snapshots[snapshot.route_id] = snapshot

    def eligible(self, route_ids: Iterable[str], *, now: int) -> tuple[RouteCapacity, ...]:
        now = _timestamp(now, "now")
        routes = tuple(sorted({_nonempty(route_id, "route_id") for route_id in route_ids}))
        if not routes:
            raise StaleLoadError("job has no candidate routes")
        fresh_seen = False
        available: list[RouteCapacity] = []
        with self._lock:
            for route_id in routes:
                snapshot = self._snapshots.get(route_id)
                if snapshot is None or not snapshot.enabled or not snapshot.fresh(now):
                    continue
                fresh_seen = True
                used = snapshot.reported_inflight + self._local_inflight.get(route_id, 0)
                free = max(0, snapshot.capacity - used)
                if free:
                    available.append(
                        RouteCapacity(route_id, snapshot.capacity, used, free, snapshot.observed_at)
                    )
        if not fresh_seen:
            raise StaleLoadError("all candidate route capacity evidence is missing, disabled, or stale")
        if not available:
            raise BackpressureError("all fresh candidate routes are at capacity")
        return tuple(available)

    def acquire(self, route_id: str, *, now: int) -> None:
        route_id = _nonempty(route_id, "route_id")
        now = _timestamp(now, "now")
        with self._lock:
            eligible = {item.route_id: item for item in self.eligible((route_id,), now=now)}
            if route_id not in eligible:
                raise BackpressureError("selected route has no available capacity")
            self._local_inflight[route_id] = self._local_inflight.get(route_id, 0) + 1

    def release(self, route_id: str) -> None:
        route_id = _nonempty(route_id, "route_id")
        with self._lock:
            count = self._local_inflight.get(route_id, 0)
            if count <= 0:
                return
            if count == 1:
                self._local_inflight.pop(route_id, None)
            else:
                self._local_inflight[route_id] = count - 1

    def local_inflight(self, route_id: str) -> int:
        route_id = _nonempty(route_id, "route_id")
        with self._lock:
            return self._local_inflight.get(route_id, 0)

    def summary(self) -> Mapping[str, int]:
        with self._lock:
            return ImmutableJSONDict(
                {
                    "snapshot_count": len(self._snapshots),
                    "max_routes": self.max_routes,
                    "enabled_snapshot_count": sum(item.enabled for item in self._snapshots.values()),
                    "local_inflight_total": sum(self._local_inflight.values()),
                    "local_inflight_route_count": len(self._local_inflight),
                }
            )


class PentaBalancer:
    """Deterministic least-utilized route selection with stable hash ties."""

    @staticmethod
    def choose(job_id: str, routes: Sequence[RouteCapacity]) -> RouteCapacity:
        job_id = _nonempty(job_id, "job_id")
        if not routes:
            raise BackpressureError("balancer received no eligible route")

        def key(route: RouteCapacity) -> tuple[Fraction, int, str, str]:
            tie = hashlib.sha256(f"{job_id}\0{route.route_id}".encode("utf-8")).hexdigest()
            return (route.utilization, -route.available, tie, route.route_id)

        return min(routes, key=key)


@dataclass(frozen=True)
class PentaRate:
    """Immutable versioned internal-unit rate book."""

    immutable = True
    money_movement = False

    rate_book_id: str
    version: str
    effective_at: int
    rates: tuple[tuple[str, int], ...]
    evidence_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "rate_book_id", _nonempty(self.rate_book_id, "rate_book_id"))
        object.__setattr__(self, "version", _nonempty(self.version, "version"))
        object.__setattr__(self, "evidence_ref", _nonempty(self.evidence_ref, "evidence_ref"))
        object.__setattr__(self, "effective_at", _timestamp(self.effective_at, "effective_at"))
        if not self.rates:
            raise ValueError("rates must contain at least one operation")
        if isinstance(self.rates, (str, bytes)) or not isinstance(self.rates, Sequence):
            raise ValueError("rates must be a canonical sequence")
        operations: list[str] = []
        canonical_rates: list[tuple[str, int]] = []
        for operation, units in self.rates:
            operation = _nonempty(operation, "operation")
            units = _unit(units, "rate units")
            operations.append(operation)
            canonical_rates.append((operation, units))
        if len(set(operations)) != len(operations):
            raise ValueError("rate operations must be unique")
        canonical = tuple(canonical_rates)
        if tuple(sorted(canonical)) != canonical:
            raise ValueError("rates must be stored in canonical operation order")
        object.__setattr__(self, "rates", canonical)

    @classmethod
    def create(
        cls,
        *,
        rate_book_id: str,
        version: str,
        effective_at: int,
        rates: Mapping[str, int],
        evidence_ref: str,
    ) -> "PentaRate":
        if not isinstance(rates, Mapping):
            raise ValueError("rates must be a mapping")
        canonical = tuple(
            sorted(
                (
                    _nonempty(operation, "operation"),
                    _unit(units, "rate units"),
                )
                for operation, units in rates.items()
            )
        )
        return cls(rate_book_id, version, effective_at, canonical, evidence_ref)

    @property
    def digest(self) -> str:
        return _sha256(
            {
                "rate_book_id": self.rate_book_id,
                "version": self.version,
                "effective_at": self.effective_at,
                "rates": self.rates,
                "evidence_ref": self.evidence_ref,
            }
        )

    def units_for(self, operation: str) -> int:
        operation = _nonempty(operation, "operation")
        try:
            return dict(self.rates)[operation]
        except KeyError as exc:
            raise CostCeilingError("operation is absent from the exact rate-book version") from exc

    def estimate(self, operation: str, quantity: int) -> int:
        quantity = _unit(quantity, "quantity")
        return _checked_mul(self.units_for(operation), quantity, "estimated cost units")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ct.penta.runtime-flow-control.rate-book.v1",
            "rate_book_id": self.rate_book_id,
            "version": self.version,
            "effective_at": self.effective_at,
            "rates": [
                {"operation": operation, "units": units}
                for operation, units in self.rates
            ],
            "evidence_ref": self.evidence_ref,
            "digest": self.digest,
            "immutable": True,
            "money_movement": False,
        }


@dataclass(frozen=True)
class UsageRecord:
    record_id: str
    idempotency_key: str
    operation: str
    quantity: int
    rate_book_id: str
    rate_version: str
    rate_digest: str
    estimated_cost_units: int
    evidence_ref: str
    observed_at: int
    job_id: str
    route_id: str
    fencing_token: int
    reservation_id: str
    result_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ct.penta.runtime-flow-control.usage.v1",
            **self.__dict__,
            "append_only": True,
        }


class PentaMeter:
    """Append-only idempotent operational usage meter."""

    append_only = True
    money_movement = False

    def __init__(self, *, max_records: int = 10_000) -> None:
        self._max_records = _positive_int(max_records, "max_records")
        self._records: list[UsageRecord] = []
        self._idempotency: dict[str, tuple[str, UsageRecord]] = {}
        self._lock = threading.RLock()

    @property
    def max_records(self) -> int:
        return self._max_records

    def record(
        self,
        *,
        idempotency_key: str,
        operation: str,
        quantity: int,
        rate: PentaRate,
        evidence_ref: str,
        observed_at: int,
        job_id: str,
        route_id: str,
        fencing_token: int,
        reservation_id: str,
        result_digest: str,
    ) -> UsageRecord:
        idempotency_key = _nonempty(idempotency_key, "idempotency_key")
        operation = _nonempty(operation, "operation")
        evidence_ref = _nonempty(evidence_ref, "evidence_ref")
        job_id = _nonempty(job_id, "job_id")
        route_id = _nonempty(route_id, "route_id")
        fencing_token = _positive_int(fencing_token, "fencing_token")
        reservation_id = _nonempty(reservation_id, "reservation_id")
        result_digest = _nonempty(result_digest, "result_digest")
        if not re.fullmatch(r"[0-9a-f]{64}", result_digest):
            raise ValueError("result_digest must be a lowercase SHA-256 digest")
        observed_at = _timestamp(observed_at, "observed_at")
        if not isinstance(rate, PentaRate):
            raise ValueError("rate must be an immutable PentaRate")
        quantity = _unit(quantity, "quantity")
        estimated = rate.estimate(operation, quantity)
        request = {
            "operation": operation,
            "quantity": quantity,
            "rate_digest": rate.digest,
            "evidence_ref": evidence_ref,
            "observed_at": observed_at,
            "job_id": job_id,
            "route_id": route_id,
            "fencing_token": fencing_token,
            "reservation_id": reservation_id,
            "result_digest": result_digest,
        }
        request_hash = _sha256(request)
        with self._lock:
            prior = self._idempotency.get(idempotency_key)
            if prior is not None:
                if prior[0] != request_hash:
                    raise AdmissionConflict("meter idempotency key reused with different usage")
                return prior[1]
            if len(self._records) >= self.max_records:
                raise RetentionCapacityError("bounded usage meter is full")
            record = UsageRecord(
                record_id=f"usage-{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()}",
                idempotency_key=idempotency_key,
                operation=operation,
                quantity=quantity,
                rate_book_id=rate.rate_book_id,
                rate_version=rate.version,
                rate_digest=rate.digest,
                estimated_cost_units=estimated,
                evidence_ref=evidence_ref,
                observed_at=observed_at,
                job_id=job_id,
                route_id=route_id,
                fencing_token=fencing_token,
                reservation_id=reservation_id,
                result_digest=result_digest,
            )
            self._records.append(record)
            self._idempotency[idempotency_key] = (request_hash, record)
            return record

    def records(self) -> tuple[UsageRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def summary(self) -> Mapping[str, int]:
        with self._lock:
            return ImmutableJSONDict(
                {"record_count": len(self._records), "max_records": self.max_records}
            )


@dataclass(frozen=True)
class CostLedgerEntry:
    entry_id: str
    idempotency_key: str
    sequence: int
    event_type: str
    route_id: str
    job_id: str
    reservation_id: str
    units: int
    evidence_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ct.penta.runtime-flow-control.cost-ledger-entry.v1",
            **self.__dict__,
            "append_only": True,
            "accounting_source_of_truth": False,
            "treasury_source_of_truth": False,
        }


class PentaCostLedger:
    """Append-only operational entries; never accounting or treasury truth."""

    append_only = True
    accounting_source_of_truth = False
    treasury_source_of_truth = False
    money_movement = False

    def __init__(self, *, max_entries: int = 30_000) -> None:
        self._max_entries = _positive_int(max_entries, "max_entries")
        self._entries: list[CostLedgerEntry] = []
        self._idempotency: dict[str, tuple[str, CostLedgerEntry]] = {}
        self._lock = threading.RLock()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @staticmethod
    def _prepare_record(
        *,
        idempotency_key: str,
        event_type: str,
        route_id: str,
        job_id: str,
        reservation_id: str,
        units: int,
        evidence_ref: str,
    ) -> tuple[str, dict[str, Any], str]:
        idempotency_key = _nonempty(idempotency_key, "idempotency_key")
        request = {
            "event_type": _nonempty(event_type, "event_type"),
            "route_id": _nonempty(route_id, "route_id"),
            "job_id": _nonempty(job_id, "job_id"),
            "reservation_id": _nonempty(reservation_id, "reservation_id"),
            "units": _unit(units, "ledger units"),
            "evidence_ref": _nonempty(evidence_ref, "evidence_ref"),
        }
        return idempotency_key, request, _sha256(request)

    def preflight_record(self, **kwargs: Any) -> CostLedgerEntry | None:
        """Validate an exact append without mutating the bounded ledger."""
        idempotency_key, _, request_hash = self._prepare_record(**kwargs)
        with self._lock:
            prior = self._idempotency.get(idempotency_key)
            if prior is not None:
                if prior[0] != request_hash:
                    raise AdmissionConflict(
                        "cost-ledger idempotency key reused with a different entry"
                    )
                return prior[1]
            if len(self._entries) >= self.max_entries:
                raise RetentionCapacityError("bounded operational cost ledger is full")
            return None

    def record(
        self,
        *,
        idempotency_key: str,
        event_type: str,
        route_id: str,
        job_id: str,
        reservation_id: str,
        units: int,
        evidence_ref: str,
    ) -> CostLedgerEntry:
        idempotency_key, request, request_hash = self._prepare_record(
            idempotency_key=idempotency_key,
            event_type=event_type,
            route_id=route_id,
            job_id=job_id,
            reservation_id=reservation_id,
            units=units,
            evidence_ref=evidence_ref,
        )
        with self._lock:
            prior = self._idempotency.get(idempotency_key)
            if prior is not None:
                if prior[0] != request_hash:
                    raise AdmissionConflict("cost-ledger idempotency key reused with a different entry")
                return prior[1]
            if len(self._entries) >= self.max_entries:
                raise RetentionCapacityError("bounded operational cost ledger is full")
            entry = CostLedgerEntry(
                entry_id=f"cost-entry-{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()}",
                idempotency_key=idempotency_key,
                sequence=len(self._entries) + 1,
                **request,
            )
            self._entries.append(entry)
            self._idempotency[idempotency_key] = (request_hash, entry)
            return entry

    def entries(self) -> tuple[CostLedgerEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def summary(self) -> Mapping[str, int]:
        with self._lock:
            return ImmutableJSONDict(
                {"entry_count": len(self._entries), "max_entries": self.max_entries}
            )


@dataclass(frozen=True)
class ForecastResult:
    method: str
    sample_count: int
    periods: int
    projected_cost_units: int
    advisory_only: bool = True
    authorizes_spend: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ct.penta.runtime-flow-control.forecast.v1",
            **self.__dict__,
        }


class PentaForecast:
    """Integer-only advisory projection with no budget or spend effect."""

    advisory_only = True
    authorizes_spend = False

    @staticmethod
    def project(samples: Sequence[int], *, periods: int) -> ForecastResult:
        periods = _unit(periods, "periods")
        if periods == 0:
            return ForecastResult("ceiling_mean_v1", len(samples), periods, 0)
        if not samples:
            raise ValueError("at least one sample is required for a non-zero forecast")
        total = 0
        for sample in samples:
            total = _checked_add(total, _unit(sample, "sample units"), "forecast sample total")
        mean_ceiling = total // len(samples) + int(total % len(samples) != 0)
        projected = _checked_mul(mean_ceiling, periods, "forecast projection")
        return ForecastResult("ceiling_mean_v1", len(samples), periods, projected)


@dataclass
class _CostBudget:
    ceiling_units: int
    accounted_units: int = 0
    reserved_units: int = 0


@dataclass(frozen=True)
class CostReservation:
    reservation_id: str
    job_id: str
    fencing_token: int
    route_id: str
    units: int
    state: str


class PentaBudget:
    """Atomic internal estimate-unit budget; never payment or accounting truth."""

    money_movement = False
    authorizes_spend = False

    def __init__(
        self,
        *,
        max_routes: int = 1_000,
        max_reservations: int = 10_000,
        max_ledger_entries: int | None = None,
    ) -> None:
        self._max_routes = _positive_int(max_routes, "max_routes")
        self._max_reservations = _positive_int(max_reservations, "max_reservations")
        if max_ledger_entries is None:
            max_ledger_entries = _checked_mul(
                self.max_reservations, 3, "max_ledger_entries"
            )
        self._budgets: dict[str, _CostBudget] = {}
        self._reservations: dict[str, CostReservation] = {}
        self.ledger = PentaCostLedger(max_entries=max_ledger_entries)
        self._lock = threading.RLock()

    @property
    def max_routes(self) -> int:
        return self._max_routes

    @property
    def max_reservations(self) -> int:
        return self._max_reservations

    def configure(self, route_id: str, *, ceiling_units: int) -> None:
        route_id = _nonempty(route_id, "route_id")
        ceiling_units = _unit(ceiling_units, "ceiling_units")
        with self._lock:
            current = self._budgets.get(route_id)
            if current is not None and ceiling_units < current.accounted_units + current.reserved_units:
                raise CostCeilingError("new ceiling is below already accounted and reserved units")
            if current is None:
                if len(self._budgets) >= self.max_routes:
                    raise RetentionCapacityError("bounded route-budget registry is full")
                self._budgets[route_id] = _CostBudget(ceiling_units)
            else:
                current.ceiling_units = ceiling_units

    def reserve(self, *, job_id: str, fencing_token: int, route_id: str, units: int) -> CostReservation:
        job_id = _nonempty(job_id, "job_id")
        fencing_token = _positive_int(fencing_token, "fencing_token")
        route_id = _nonempty(route_id, "route_id")
        units = _unit(units, "estimated cost units")
        reservation_id = f"{job_id}:{fencing_token}"
        with self._lock:
            prior = self._reservations.get(reservation_id)
            if prior is not None:
                if (
                    prior.job_id != job_id
                    or prior.fencing_token != fencing_token
                    or prior.route_id != route_id
                    or prior.units != units
                ):
                    raise CostCeilingError("cost reservation id conflicts with an existing estimate")
                if prior.state != "reserved":
                    raise CostCeilingError(
                        "a released or accounted reservation cannot be reused for a new claim"
                    )
                return prior
            if len(self._reservations) >= self.max_reservations:
                raise RetentionCapacityError("bounded cost-reservation history is full")
            budget = self._budgets.get(route_id)
            if budget is None:
                raise CostCeilingError("route has no explicit cost ceiling")
            occupied = _checked_add(
                budget.accounted_units, budget.reserved_units, "occupied budget units"
            )
            requested = _checked_add(occupied, units, "requested budget units")
            if requested > budget.ceiling_units:
                raise CostCeilingError("estimated resource cost would exceed route ceiling")
            reservation = CostReservation(
                reservation_id, job_id, fencing_token, route_id, units, "reserved"
            )
            self.ledger.record(
                idempotency_key=f"{reservation_id}:reserved",
                event_type="reservation_created",
                route_id=route_id,
                job_id=job_id,
                reservation_id=reservation_id,
                units=units,
                evidence_ref=f"runtime:{reservation_id}",
            )
            budget.reserved_units += units
            self._reservations[reservation_id] = reservation
            return reservation

    def require_active(
        self,
        reservation_id: str,
        *,
        job_id: str,
        fencing_token: int,
        route_id: str,
        units: int,
    ) -> CostReservation:
        reservation_id = _nonempty(reservation_id, "reservation_id")
        job_id = _nonempty(job_id, "job_id")
        fencing_token = _positive_int(fencing_token, "fencing_token")
        route_id = _nonempty(route_id, "route_id")
        units = _unit(units, "estimated cost units")
        with self._lock:
            reservation = self._reservations.get(reservation_id)
            if reservation is None or reservation.state != "reserved":
                raise CostCeilingError("claim has no active cost reservation")
            if (
                reservation.job_id != job_id
                or reservation.fencing_token != fencing_token
                or reservation.route_id != route_id
                or reservation.units != units
            ):
                raise CostCeilingError("claim fields do not match the active cost reservation")
            return reservation

    @staticmethod
    def _transition_ledger_args(
        reservation: CostReservation, target_state: str
    ) -> dict[str, Any]:
        if target_state == "accounted":
            suffix = "accounted"
            event_type = "runtime_units_accounted"
        elif target_state == "released":
            suffix = "released"
            event_type = "reservation_released"
        else:  # pragma: no cover - private caller invariant
            raise ValueError("unsupported cost reservation target state")
        return {
            "idempotency_key": f"{reservation.reservation_id}:{suffix}",
            "event_type": event_type,
            "route_id": reservation.route_id,
            "job_id": reservation.job_id,
            "reservation_id": reservation.reservation_id,
            "units": reservation.units,
            "evidence_ref": f"runtime:{reservation.reservation_id}",
        }

    def preflight_transition(
        self, reservation_id: str, *, target_state: str
    ) -> CostReservation:
        """Validate reservation and bounded-ledger transition without mutation."""
        reservation_id = _nonempty(reservation_id, "reservation_id")
        with self._lock:
            reservation = self._reservations.get(reservation_id)
            if reservation is None:
                raise CostCeilingError("cost reservation is unknown")
            if reservation.state == target_state:
                return reservation
            if reservation.state != "reserved":
                raise CostCeilingError(
                    f"{reservation.state} cost reservation cannot become {target_state}"
                )
            self.ledger.preflight_record(
                **self._transition_ledger_args(reservation, target_state)
            )
            return reservation

    def finalize(self, reservation_id: str) -> CostReservation:
        reservation_id = _nonempty(reservation_id, "reservation_id")
        with self._lock:
            reservation = self.preflight_transition(
                reservation_id, target_state="accounted"
            )
            if reservation.state == "accounted":
                return reservation
            final = replace(reservation, state="accounted")
            self.ledger.record(**self._transition_ledger_args(reservation, "accounted"))
            budget = self._budgets[reservation.route_id]
            budget.reserved_units -= reservation.units
            budget.accounted_units += reservation.units
            self._reservations[reservation_id] = final
            return final

    def release(self, reservation_id: str) -> CostReservation | None:
        reservation_id = _nonempty(reservation_id, "reservation_id")
        with self._lock:
            reservation = self._reservations.get(reservation_id)
            if reservation is None or reservation.state == "released":
                return reservation
            if reservation.state == "accounted":
                return reservation
            self.preflight_transition(reservation_id, target_state="released")
            released = replace(reservation, state="released")
            self.ledger.record(**self._transition_ledger_args(reservation, "released"))
            budget = self._budgets[reservation.route_id]
            budget.reserved_units -= reservation.units
            self._reservations[reservation_id] = released
            return released

    def status(self, route_id: str) -> Mapping[str, Any]:
        route_id = _nonempty(route_id, "route_id")
        with self._lock:
            budget = self._budgets.get(route_id)
            if budget is None:
                raise CostCeilingError("route has no explicit cost ceiling")
            return ImmutableJSONDict(
                {
                    "schema": "ct.penta.runtime-flow-control.budget-status.v1",
                    "route_id": route_id,
                    "ceiling_units": budget.ceiling_units,
                    "accounted_units": budget.accounted_units,
                    "reserved_units": budget.reserved_units,
                    "available_units": (
                        budget.ceiling_units - budget.accounted_units - budget.reserved_units
                    ),
                    "money_movement": False,
                }
            )

    def summary(self) -> Mapping[str, Any]:
        with self._lock:
            states: dict[str, int] = {"reserved": 0, "accounted": 0, "released": 0}
            for reservation in self._reservations.values():
                states[reservation.state] = states.get(reservation.state, 0) + 1
            return ImmutableJSONDict(
                {
                    "route_budget_count": len(self._budgets),
                    "max_routes": self.max_routes,
                    "reservation_count": len(self._reservations),
                    "max_reservations": self.max_reservations,
                    "reservation_states": ImmutableJSONDict(states),
                    "accounted_estimate_units": sum(
                        budget.accounted_units for budget in self._budgets.values()
                    ),
                    "reserved_estimate_units": sum(
                        budget.reserved_units for budget in self._budgets.values()
                    ),
                    "ledger": self.ledger.summary(),
                }
            )


class PentaCosts(PentaBudget):
    """Compatibility facade for the PentaCosts operational family.

    Existing budget methods remain unchanged.  Metering and advisory forecasting
    are exposed as composed family members; rate books remain immutable values.
    """

    def __init__(
        self,
        *,
        max_routes: int = 1_000,
        max_reservations: int = 10_000,
        max_usage_records: int = 10_000,
        registered_rates: Sequence[PentaRate] = (),
    ) -> None:
        super().__init__(max_routes=max_routes, max_reservations=max_reservations)
        self.meter = PentaMeter(max_records=max_usage_records)
        self.forecast = PentaForecast()
        self._rates: dict[tuple[str, str], PentaRate] = {}
        for rate in registered_rates:
            self.register_rate(rate)

    def register_rate(self, rate: PentaRate) -> PentaRate:
        """Configure immutable controlled-test rate evidence before execution."""
        if not isinstance(rate, PentaRate):
            raise ValueError("rate must be an immutable PentaRate")
        key = (rate.rate_book_id, rate.version)
        with self._lock:
            prior = self._rates.get(key)
            if prior is not None and prior.digest != rate.digest:
                raise AdmissionConflict(
                    "rate-book id/version conflicts with configured immutable evidence"
                )
            self._rates[key] = rate
            return rate

    def require_rate(self, rate: PentaRate, *, now: int) -> PentaRate:
        if not isinstance(rate, PentaRate):
            raise ValueError("rate must be an immutable PentaRate")
        now = _timestamp(now, "now")
        with self._lock:
            configured = self._rates.get((rate.rate_book_id, rate.version))
            if configured is None or configured.digest != rate.digest:
                raise CostCeilingError(
                    "completion rate is not the configured immutable version"
                )
            if configured.effective_at > now:
                raise CostCeilingError("completion rate is not yet effective")
            return configured

    def summary(self) -> Mapping[str, Any]:
        summary = dict(super().summary())
        summary["configured_rate_count"] = len(self._rates)
        return ImmutableJSONDict(summary)


@dataclass(frozen=True)
class ExceptionEvidence:
    evidence_id: str
    exception_class: str
    code: str
    message: str
    evidence_ref: str
    observed_at: int


class ExceptionLedger:
    """Append-only raw exceptions plus deterministic redundant-event grouping."""

    _UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.IGNORECASE)
    _HEX = re.compile(r"\b[0-9a-f]{16,}\b", re.IGNORECASE)
    _NUMBER = re.compile(r"\b\d+\b")
    _HTTP_STATUS = re.compile(
        r"(\b(?:http(?:/\d(?:\.\d)?)?|status(?:\s+code)?)\s*[:=]?\s*)([1-5]\d\d)\b",
        re.IGNORECASE,
    )
    _BEARER = re.compile(r"\bbearer\s+[a-z0-9._~+/=-]+", re.IGNORECASE)
    _PASSWORD = re.compile(
        r"\b(password|passwd|pwd)\s*([:=]\s*|\s+)[^\s,;]+", re.IGNORECASE
    )
    _EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    _SIGNED_PARAMETER = re.compile(
        r"([?&](?:x-amz-signature|x-amz-credential|signature|sig|token|access_token|api_key|secret)=)[^&#\s]+",
        re.IGNORECASE,
    )

    def __init__(self, *, max_records: int = 10_000) -> None:
        self._max_records = _positive_int(max_records, "max_records")
        self._evidence: list[ExceptionEvidence] = []
        self._lock = threading.RLock()

    @property
    def max_records(self) -> int:
        return self._max_records

    @classmethod
    def _redact(cls, value: str) -> str:
        safe = cls._BEARER.sub("Bearer <redacted>", value)
        safe = cls._PASSWORD.sub(lambda match: f"{match.group(1)}=<redacted>", safe)
        safe = cls._EMAIL.sub("<redacted-email>", safe)
        safe = cls._SIGNED_PARAMETER.sub(lambda match: f"{match.group(1)}<redacted>", safe)
        return safe

    @classmethod
    def _normalized_message(cls, message: str) -> str:
        value = cls._redact(message).casefold()
        value = cls._HTTP_STATUS.sub(
            lambda match: (
                f"{match.group(1)}<http-status-"
                + "".join(chr(ord("a") + int(digit)) for digit in match.group(2))
                + ">"
            ),
            value,
        )
        value = cls._UUID.sub("<uuid>", value)
        value = cls._HEX.sub("<hex>", value)
        value = cls._NUMBER.sub("<n>", value)
        return " ".join(value.split())

    @classmethod
    def fingerprint(cls, exception_class: str, code: str, message: str) -> str:
        return _sha256(
            {
                "exception_class": exception_class.casefold().strip(),
                "code": code.casefold().strip(),
                "normalized_message": cls._normalized_message(message),
            }
        )

    def record(
        self,
        *,
        exception_class: str,
        code: str,
        message: str,
        evidence_ref: str,
        observed_at: int,
    ) -> ExceptionEvidence:
        exception_class = _nonempty(exception_class, "exception_class")
        code = _nonempty(code, "code")
        message = _nonempty(message, "message")
        evidence_ref = _nonempty(evidence_ref, "evidence_ref")
        observed_at = _timestamp(observed_at, "observed_at")
        with self._lock:
            if len(self._evidence) >= self.max_records:
                raise RetentionCapacityError("bounded exception-evidence ledger is full")
            item = ExceptionEvidence(
                evidence_id=f"evidence-{len(self._evidence) + 1:08d}",
                exception_class=exception_class,
                code=code,
                message=message,
                evidence_ref=evidence_ref,
                observed_at=observed_at,
            )
            self._evidence.append(item)
            return item

    def report(self) -> Mapping[str, Any]:
        with self._lock:
            raw = list(self._evidence)
        groups: dict[str, list[ExceptionEvidence]] = {}
        for item in raw:
            key = self.fingerprint(item.exception_class, item.code, item.message)
            groups.setdefault(key, []).append(item)
        consolidated = []
        for fingerprint, items in sorted(groups.items()):
            ordered = sorted(items, key=lambda item: (item.observed_at, item.evidence_id))
            consolidated.append(
                {
                    "fingerprint": fingerprint,
                    "exception_class": "redacted-exception-class",
                    "exception_class_digest": hashlib.sha256(
                        ordered[0].exception_class.encode("utf-8")
                    ).hexdigest(),
                    "code": "redacted-exception-code",
                    "code_digest": hashlib.sha256(
                        ordered[0].code.encode("utf-8")
                    ).hexdigest(),
                    "normalized_message": self._normalized_message(ordered[0].message),
                    "raw_evidence_count": len(ordered),
                    "first_observed_at": ordered[0].observed_at,
                    "last_observed_at": ordered[-1].observed_at,
                    "evidence_refs": [self._redact(item.evidence_ref) for item in ordered],
                    "evidence_ref_digests": [
                        hashlib.sha256(item.evidence_ref.encode("utf-8")).hexdigest()
                        for item in ordered
                    ],
                }
            )
        safe_raw = []
        for item in raw:
            safe_message = self._redact(item.message)
            safe_ref = self._redact(item.evidence_ref)
            safe_raw.append(
                {
                    "evidence_id": item.evidence_id,
                    "exception_class": "redacted-exception-class",
                    "exception_class_digest": hashlib.sha256(
                        item.exception_class.encode("utf-8")
                    ).hexdigest(),
                    "code": "redacted-exception-code",
                    "code_digest": hashlib.sha256(item.code.encode("utf-8")).hexdigest(),
                    "message": safe_message,
                    "message_digest": hashlib.sha256(item.message.encode("utf-8")).hexdigest(),
                    "evidence_ref": safe_ref,
                    "evidence_ref_digest": hashlib.sha256(
                        item.evidence_ref.encode("utf-8")
                    ).hexdigest(),
                    "redacted": True,
                    "observed_at": item.observed_at,
                }
            )
        return _freeze_mapping(
            {
                "schema": "ct.penta.runtime-flow-control.exceptions.v1",
                "raw_evidence_count": len(raw),
                "max_raw_evidence_records": self.max_records,
                "fingerprint_count": len(consolidated),
                "groups": consolidated,
                "raw_evidence": safe_raw,
            },
            field_name="exception report",
        )


@dataclass
class _Job:
    job_id: str
    idempotency_key: str
    request_hash: str
    payload: Mapping[str, Any]
    priority: int
    route_candidates: tuple[str, ...]
    required_scope: str
    estimated_cost_units: int
    max_attempts: int
    admitted_at: int
    sequence: int
    available_at: int
    state: str = "queued"
    attempts: int = 0
    fencing_token: int = 0
    lease_owner: str | None = None
    lease_route: str | None = None
    lease_expires_at: int | None = None
    reservation_id: str | None = None
    authority_receipt_id: str | None = None
    result: Mapping[str, Any] | None = None
    result_digest: str | None = None
    completion_claim_digest: str | None = None
    completion_input_digest: str | None = None
    completion_response: Mapping[str, Any] | None = None
    completed_at: int | None = None


@dataclass(frozen=True)
class _JobView:
    job_id: str
    payload: Mapping[str, Any]
    priority: int
    route_candidates: tuple[str, ...]
    required_scope: str
    estimated_cost_units: int
    max_attempts: int
    admitted_at: int
    sequence: int
    available_at: int
    state: str
    attempts: int
    fencing_token: int
    lease_owner: str | None
    lease_route: str | None
    lease_expires_at: int | None
    reservation_id: str | None
    authority_receipt_id: str | None
    result: Mapping[str, Any] | None
    result_digest: str | None
    completion_claim_digest: str | None
    completion_input_digest: str | None
    completion_response: Mapping[str, Any] | None
    completed_at: int | None


@dataclass(frozen=True)
class AdmissionResult:
    job_id: str
    state: str
    idempotent_replay: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ct.penta.runtime-flow-control.admission-result.v1",
            **self.__dict__,
        }


@dataclass(frozen=True)
class ClaimResult:
    job_id: str
    worker_id: str
    route_id: str
    fencing_token: int
    lease_expires_at: int
    attempt: int
    payload: Mapping[str, Any]
    authority_receipt_id: str
    cost_reservation_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", _nonempty(self.job_id, "job_id"))
        object.__setattr__(self, "worker_id", _nonempty(self.worker_id, "worker_id"))
        object.__setattr__(self, "route_id", _nonempty(self.route_id, "route_id"))
        object.__setattr__(
            self, "fencing_token", _positive_int(self.fencing_token, "fencing_token")
        )
        object.__setattr__(
            self, "lease_expires_at", _timestamp(self.lease_expires_at, "lease_expires_at")
        )
        object.__setattr__(self, "attempt", _positive_int(self.attempt, "attempt"))
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, field_name="payload"))
        object.__setattr__(
            self,
            "authority_receipt_id",
            _nonempty(self.authority_receipt_id, "authority_receipt_id"),
        )
        object.__setattr__(
            self,
            "cost_reservation_id",
            _nonempty(self.cost_reservation_id, "cost_reservation_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ct.penta.runtime-flow-control.claim.v1",
            "job_id": self.job_id,
            "worker_id": self.worker_id,
            "route_id": self.route_id,
            "fencing_token": self.fencing_token,
            "lease_expires_at": self.lease_expires_at,
            "attempt": self.attempt,
            "payload": _plain_json(self.payload),
            "authority_receipt_id": self.authority_receipt_id,
            "cost_reservation_id": self.cost_reservation_id,
        }


class PentaQueue:
    """Bounded queue with detached immutable views and retained-history caps."""

    def __init__(
        self, *, max_resident_jobs: int, max_retained_jobs: int | None = None
    ) -> None:
        self._max_resident_jobs = _positive_int(max_resident_jobs, "max_resident_jobs")
        if max_retained_jobs is None:
            max_retained_jobs = _checked_mul(
                self.max_resident_jobs, 4, "max_retained_jobs"
            )
        self._max_retained_jobs = _positive_int(max_retained_jobs, "max_retained_jobs")
        if self.max_retained_jobs < self.max_resident_jobs:
            raise ValueError("max_retained_jobs may not be below max_resident_jobs")
        self._jobs: dict[str, _Job] = {}
        self._idempotency: dict[str, str] = {}
        self._sequence = 0
        self._admission_enabled = True
        self._stop_receipt: Mapping[str, Any] | None = None
        self._lock = threading.RLock()

    @property
    def max_resident_jobs(self) -> int:
        return self._max_resident_jobs

    @property
    def max_retained_jobs(self) -> int:
        return self._max_retained_jobs

    @staticmethod
    def _view(job: _Job) -> _JobView:
        return _JobView(
            job_id=job.job_id,
            payload=job.payload,
            priority=job.priority,
            route_candidates=job.route_candidates,
            required_scope=job.required_scope,
            estimated_cost_units=job.estimated_cost_units,
            max_attempts=job.max_attempts,
            admitted_at=job.admitted_at,
            sequence=job.sequence,
            available_at=job.available_at,
            state=job.state,
            attempts=job.attempts,
            fencing_token=job.fencing_token,
            lease_owner=job.lease_owner,
            lease_route=job.lease_route,
            lease_expires_at=job.lease_expires_at,
            reservation_id=job.reservation_id,
            authority_receipt_id=job.authority_receipt_id,
            result=job.result,
            result_digest=job.result_digest,
            completion_claim_digest=job.completion_claim_digest,
            completion_input_digest=job.completion_input_digest,
            completion_response=job.completion_response,
            completed_at=job.completed_at,
        )

    def admit(
        self,
        *,
        idempotency_key: str,
        payload: Mapping[str, Any],
        priority: int,
        route_candidates: Sequence[str],
        required_scope: str,
        estimated_cost_units: int,
        max_attempts: int,
        now: int,
    ) -> AdmissionResult:
        idempotency_key = _nonempty(idempotency_key, "idempotency_key")
        required_scope = _exact_scope(required_scope, "required_scope")
        if not isinstance(route_candidates, Sequence) or isinstance(route_candidates, (str, bytes)):
            raise ValueError("route_candidates must be a sequence")
        routes = tuple(sorted({_nonempty(route, "route_id") for route in route_candidates}))
        if not routes:
            raise ValueError("route_candidates must contain non-empty route ids")
        payload = _freeze_mapping(payload, field_name="payload")
        priority = _integer(priority, "priority")
        if not 0 <= priority <= 100:
            raise ValueError("priority must be between 0 and 100")
        estimated_cost_units = _unit(estimated_cost_units, "estimated_cost_units")
        max_attempts = _positive_int(max_attempts, "max_attempts", maximum=100)
        now = _timestamp(now, "now")
        request_hash = _sha256(
            {
                "payload": payload,
                "priority": priority,
                "route_candidates": routes,
                "required_scope": required_scope,
                "estimated_cost_units": estimated_cost_units,
                "max_attempts": max_attempts,
            }
        )
        with self._lock:
            if not self._admission_enabled:
                raise QueueCapacityError(
                    "new admission is stopped by fail-closed recovery control"
                )
            existing_id = self._idempotency.get(idempotency_key)
            if existing_id is not None:
                existing = self._jobs[existing_id]
                if existing.request_hash != request_hash:
                    raise AdmissionConflict("idempotency key reused with a different request")
                return AdmissionResult(existing.job_id, existing.state, True)
            resident = sum(job.state in {"queued", "leased"} for job in self._jobs.values())
            if resident >= self.max_resident_jobs:
                raise QueueCapacityError("bounded resident queue is full")
            if len(self._jobs) >= self.max_retained_jobs:
                raise RetentionCapacityError(
                    "bounded queue/idempotency history is full; rotate through governed custody"
                )
            self._sequence += 1
            job_id = f"job-{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()}"
            if job_id in self._jobs:
                raise AdmissionConflict("deterministic job id collides with an existing admission")
            job = _Job(
                job_id=job_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                payload=payload,
                priority=priority,
                route_candidates=routes,
                required_scope=required_scope,
                estimated_cost_units=estimated_cost_units,
                max_attempts=max_attempts,
                admitted_at=now,
                sequence=self._sequence,
                available_at=now,
            )
            self._jobs[job_id] = job
            self._idempotency[idempotency_key] = job_id
            return AdmissionResult(job_id, job.state, False)

    def stop_admission(
        self, *, reason: str, evidence_ref: str, now: int
    ) -> Mapping[str, Any]:
        reason = _nonempty(reason, "reason")
        evidence_ref = _nonempty(evidence_ref, "evidence_ref")
        now = _timestamp(now, "now")
        with self._lock:
            if self._stop_receipt is None:
                self._admission_enabled = False
                self._stop_receipt = _freeze_mapping(
                    {
                        "schema": "ct.penta.runtime-flow-control.stop-receipt.v1",
                        "stopped_at": now,
                        "reason": reason,
                        "evidence_ref": evidence_ref,
                        "new_admission_enabled": False,
                        "failure_and_reap_enabled": True,
                        "external_effects_enabled": False,
                    },
                    field_name="stop receipt",
                )
            return self._stop_receipt

    def candidates(self, *, now: int) -> tuple[_JobView, ...]:
        now = _timestamp(now, "now")
        with self._lock:
            jobs = [
                job
                for job in self._jobs.values()
                if job.state == "queued" and job.available_at <= now
            ]
            ordered = sorted(
                jobs,
                key=lambda job: (-job.priority, job.admitted_at, job.sequence, job.job_id),
            )
            return tuple(self._view(job) for job in ordered)

    def lease(
        self,
        job_id: str,
        *,
        worker_id: str,
        route_id: str,
        lease_seconds: int,
        reservation_id: str,
        authority_receipt_id: str,
        now: int,
    ) -> _JobView:
        job_id = _nonempty(job_id, "job_id")
        worker_id = _nonempty(worker_id, "worker_id")
        route_id = _nonempty(route_id, "route_id")
        lease_seconds = _positive_int(lease_seconds, "lease_seconds")
        reservation_id = _nonempty(reservation_id, "reservation_id")
        authority_receipt_id = _nonempty(authority_receipt_id, "authority_receipt_id")
        now = _timestamp(now, "now")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state != "queued" or job.available_at > now:
                raise LeaseError("job is not currently claimable")
            if route_id not in job.route_candidates:
                raise LeaseError("lease route is outside the admitted route candidates")
            if job.attempts >= job.max_attempts:
                job.state = "dead_letter"
                raise LeaseError("job exhausted its bounded attempt count")
            job.attempts += 1
            job.fencing_token += 1
            job.state = "leased"
            job.lease_owner = worker_id
            job.lease_route = route_id
            job.lease_expires_at = now + lease_seconds
            job.reservation_id = reservation_id
            job.authority_receipt_id = authority_receipt_id
            return self._view(job)

    def require_active_lease(
        self, job_id: str, *, fencing_token: int, now: int
    ) -> _JobView:
        job_id = _nonempty(job_id, "job_id")
        fencing_token = _positive_int(fencing_token, "fencing_token")
        now = _timestamp(now, "now")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state != "leased":
                raise LeaseError("job has no active lease")
            if job.fencing_token != fencing_token:
                raise LeaseError("lease fencing token is stale")
            if job.lease_expires_at is None or now >= job.lease_expires_at:
                raise LeaseError("lease has expired")
            return self._view(job)

    @staticmethod
    def _clear_lease(job: _Job) -> None:
        job.lease_owner = None
        job.lease_route = None
        job.lease_expires_at = None
        job.reservation_id = None
        job.authority_receipt_id = None

    def complete(
        self,
        job_id: str,
        *,
        fencing_token: int,
        result: Mapping[str, Any],
        result_digest: str,
        completion_claim_digest: str,
        completion_input_digest: str,
        completion_response: Mapping[str, Any],
        now: int,
    ) -> _JobView:
        result = _freeze_mapping(result, field_name="result")
        completion_response = _freeze_mapping(
            completion_response, field_name="completion_response"
        )
        now = _timestamp(now, "now")
        with self._lock:
            active = self.require_active_lease(job_id, fencing_token=fencing_token, now=now)
            job = self._jobs[active.job_id]
            job.state = "implementation_verified"
            job.result = result
            job.result_digest = result_digest
            job.completion_claim_digest = completion_claim_digest
            job.completion_input_digest = completion_input_digest
            job.completion_response = completion_response
            job.completed_at = now
            self._clear_lease(job)
            return self._view(job)

    def fail(
        self,
        job_id: str,
        *,
        fencing_token: int,
        retry_delay_seconds: int,
        now: int,
    ) -> _JobView:
        retry_delay_seconds = _unit(retry_delay_seconds, "retry_delay_seconds")
        now = _timestamp(now, "now")
        with self._lock:
            active = self.require_active_lease(job_id, fencing_token=fencing_token, now=now)
            job = self._jobs[active.job_id]
            job.state = "dead_letter" if job.attempts >= job.max_attempts else "queued"
            job.available_at = now + retry_delay_seconds
            self._clear_lease(job)
            return self._view(job)

    def expired(self, *, now: int) -> tuple[_JobView, ...]:
        now = _timestamp(now, "now")
        with self._lock:
            return tuple(
                self._view(job)
                for job in self._jobs.values()
                if job.state == "leased"
                and job.lease_expires_at is not None
                and now >= job.lease_expires_at
            )

    def expire(
        self,
        job_id: str,
        *,
        fencing_token: int,
        retry_delay_seconds: int,
        now: int,
    ) -> _JobView:
        job_id = _nonempty(job_id, "job_id")
        fencing_token = _positive_int(fencing_token, "fencing_token")
        retry_delay_seconds = _unit(retry_delay_seconds, "retry_delay_seconds")
        now = _timestamp(now, "now")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state != "leased" or job.fencing_token != fencing_token:
                raise LeaseError("expired lease was already replaced")
            if job.lease_expires_at is None or now < job.lease_expires_at:
                raise LeaseError("lease has not expired")
            job.state = "dead_letter" if job.attempts >= job.max_attempts else "queued"
            job.available_at = now + retry_delay_seconds
            self._clear_lease(job)
            return self._view(job)

    def view(self, job_id: str) -> _JobView:
        job_id = _nonempty(job_id, "job_id")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise LeaseError("job is unknown")
            return self._view(job)

    def snapshot(self, job_id: str) -> Mapping[str, Any]:
        job = self.view(job_id)
        return _freeze_mapping(
            {
                "job_id": job.job_id,
                "state": job.state,
                "priority": job.priority,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
                "fencing_token": job.fencing_token,
                "lease_owner": job.lease_owner,
                "lease_route": job.lease_route,
                "lease_expires_at": job.lease_expires_at,
                "available_at": job.available_at,
                "result_digest": job.result_digest,
            },
            field_name="job snapshot",
        )

    def summary(self) -> Mapping[str, Any]:
        with self._lock:
            states: dict[str, int] = {}
            for job in self._jobs.values():
                states[job.state] = states.get(job.state, 0) + 1
            return ImmutableJSONDict(
                {
                    "resident_job_count": sum(
                        job.state in {"queued", "leased"} for job in self._jobs.values()
                    ),
                    "max_resident_jobs": self.max_resident_jobs,
                    "retained_job_count": len(self._jobs),
                    "retained_idempotency_count": len(self._idempotency),
                    "max_retained_jobs": self.max_retained_jobs,
                    "new_admission_enabled": self._admission_enabled,
                    "stop_receipt": self._stop_receipt,
                    "state_counts": ImmutableJSONDict(states),
                }
            )


class PentaFlowControl:
    """Fail-closed CONTROLLED_TEST composition; no external effect adapter."""

    def __init__(
        self,
        *,
        max_resident_jobs: int,
        max_retained_jobs: int | None = None,
        max_history_records: int = 10_000,
        environment_id: str = "controlled-test",
        trusted_authority_issuers: Sequence[str] = ("controlled-test-configured-issuer",),
        registered_rates: Sequence[PentaRate] = (),
    ) -> None:
        max_history_records = _positive_int(max_history_records, "max_history_records")
        self.queue = PentaQueue(
            max_resident_jobs=max_resident_jobs, max_retained_jobs=max_retained_jobs
        )
        self.load = PentaLoad(max_routes=max_history_records)
        self.balancer = PentaBalancer()
        self.costs = PentaCosts(
            max_reservations=max_history_records,
            max_usage_records=max_history_records,
            registered_rates=registered_rates,
        )
        self.authority = AuthorityReceiptStore(
            environment_id=environment_id,
            trusted_issuer_ids=trusted_authority_issuers,
            max_receipts=max_history_records,
        )
        self.exceptions = ExceptionLedger(max_records=max_history_records)
        self._lock = threading.RLock()

    def stop(self, *, reason: str, evidence_ref: str, now: int) -> Mapping[str, Any]:
        """Irreversibly stop new admission for this runtime instance."""
        with self._lock:
            return self.queue.stop_admission(
                reason=reason, evidence_ref=evidence_ref, now=now
            )

    @staticmethod
    def _claim_digest(claim: ClaimResult) -> str:
        return _sha256(
            {
                "job_id": claim.job_id,
                "worker_id": claim.worker_id,
                "route_id": claim.route_id,
                "fencing_token": claim.fencing_token,
                "lease_expires_at": claim.lease_expires_at,
                "attempt": claim.attempt,
                "payload": claim.payload,
                "authority_receipt_id": claim.authority_receipt_id,
                "cost_reservation_id": claim.cost_reservation_id,
            }
        )

    def _validate_claim_active(self, claim: ClaimResult, *, now: int) -> _JobView:
        if not isinstance(claim, ClaimResult):
            raise LeaseError("claim has an unsupported type")
        now = _timestamp(now, "now")
        job = self.queue.require_active_lease(
            claim.job_id, fencing_token=claim.fencing_token, now=now
        )
        exact = (
            job.lease_owner == claim.worker_id
            and job.lease_route == claim.route_id
            and job.lease_expires_at == claim.lease_expires_at
            and job.attempts == claim.attempt
            and _sha256(job.payload) == _sha256(claim.payload)
            and job.authority_receipt_id == claim.authority_receipt_id
            and job.reservation_id == claim.cost_reservation_id
        )
        if not exact:
            raise LeaseError("claim fields do not exactly match the active lease")
        self.authority.require(
            claim.authority_receipt_id,
            subject_id=claim.worker_id,
            scope=job.required_scope,
            now=now,
        )
        self.costs.require_active(
            claim.cost_reservation_id,
            job_id=claim.job_id,
            fencing_token=claim.fencing_token,
            route_id=claim.route_id,
            units=job.estimated_cost_units,
        )
        return job

    def claim(
        self,
        *,
        worker_id: str,
        authority_receipt_id: str,
        lease_seconds: int,
        now: int,
    ) -> ClaimResult | None:
        worker_id = _nonempty(worker_id, "worker_id")
        authority_receipt_id = _nonempty(authority_receipt_id, "authority_receipt_id")
        lease_seconds = _positive_int(lease_seconds, "lease_seconds")
        now = _timestamp(now, "now")
        failures: list[FlowControlError] = []
        with (
            self._lock,
            self.queue._lock,
            self.authority._lock,
            self.load._lock,
            self.costs._lock,
            self.costs.ledger._lock,
        ):
            for job in self.queue.candidates(now=now):
                try:
                    receipt = self.authority.require(
                        authority_receipt_id,
                        subject_id=worker_id,
                        scope=job.required_scope,
                        now=now,
                    )
                    routes = self.load.eligible(job.route_candidates, now=now)
                    route = self.balancer.choose(job.job_id, routes)
                    next_token = job.fencing_token + 1
                    reservation = self.costs.reserve(
                        job_id=job.job_id,
                        fencing_token=next_token,
                        route_id=route.route_id,
                        units=job.estimated_cost_units,
                    )
                    try:
                        self.load.acquire(route.route_id, now=now)
                        try:
                            leased = self.queue.lease(
                                job.job_id,
                                worker_id=worker_id,
                                route_id=route.route_id,
                                lease_seconds=min(lease_seconds, receipt.expires_at - now),
                                reservation_id=reservation.reservation_id,
                                authority_receipt_id=receipt.receipt_id,
                                now=now,
                            )
                        except Exception:
                            self.load.release(route.route_id)
                            raise
                    except Exception:
                        self.costs.release(reservation.reservation_id)
                        raise
                    return ClaimResult(
                        job_id=leased.job_id,
                        worker_id=worker_id,
                        route_id=route.route_id,
                        fencing_token=leased.fencing_token,
                        lease_expires_at=leased.lease_expires_at or now,
                        attempt=leased.attempts,
                        payload=leased.payload,
                        authority_receipt_id=receipt.receipt_id,
                        cost_reservation_id=reservation.reservation_id,
                    )
                except FlowControlError as exc:
                    failures.append(exc)
            if failures:
                raise failures[0]
            return None

    def validate_claim(self, claim: ClaimResult, *, now: int) -> Mapping[str, Any]:
        """Validate custody only; this controlled-test pack cannot authorize effects."""
        with self._lock:
            self._validate_claim_active(claim, now=now)
            return ImmutableJSONDict(
                {
                    "job_id": claim.job_id,
                    "fencing_token": claim.fencing_token,
                    "authority_receipt_id": claim.authority_receipt_id,
                    "controlled_test_preflight_valid": True,
                    "effect_may_be_considered": False,
                    "external_effects_enabled": False,
                    "provider_authority_inherited": False,
                }
            )

    def complete(
        self,
        claim: ClaimResult,
        *,
        result: Mapping[str, Any],
        operation: str,
        quantity: int,
        rate: PentaRate,
        usage_evidence_ref: str,
        now: int,
    ) -> Mapping[str, Any]:
        if not isinstance(claim, ClaimResult):
            raise LeaseError("claim has an unsupported type")
        result = _freeze_mapping(result, field_name="result")
        result_digest = _sha256(result)
        operation = _nonempty(operation, "operation")
        quantity = _unit(quantity, "quantity")
        usage_evidence_ref = _nonempty(usage_evidence_ref, "usage_evidence_ref")
        now = _timestamp(now, "now")
        configured_rate = self.costs.require_rate(rate, now=now)
        estimated_actual_units = configured_rate.estimate(operation, quantity)
        claim_digest = self._claim_digest(claim)
        completion_input_digest = _sha256(
            {
                "result_digest": result_digest,
                "operation": operation,
                "quantity": quantity,
                "rate_digest": configured_rate.digest,
                "usage_evidence_ref": usage_evidence_ref,
            }
        )
        usage_key = f"completion:{claim.job_id}:{claim.fencing_token}"
        usage_record_id = f"usage-{hashlib.sha256(usage_key.encode('utf-8')).hexdigest()}"
        response = _freeze_mapping(
            {
                "job_id": claim.job_id,
                "state": "implementation_verified",
                "result": result,
                "result_digest": result_digest,
                "usage_record_id": usage_record_id,
                "metered_actual_estimate_units": estimated_actual_units,
                "certification_effect": False,
                "provider_effect": False,
                "money_movement": False,
            },
            field_name="completion response",
        )
        with (
            self._lock,
            self.queue._lock,
            self.authority._lock,
            self.load._lock,
            self.costs._lock,
            self.costs.meter._lock,
            self.costs.ledger._lock,
        ):
            prior = self.queue.view(claim.job_id)
            if prior.state == "implementation_verified":
                if (
                    prior.completion_claim_digest != claim_digest
                    or prior.completion_input_digest != completion_input_digest
                ):
                    raise AdmissionConflict(
                        "completed claim replay must reproduce the exact claim, result, and usage"
                    )
                if prior.completion_response is None:  # pragma: no cover - internal invariant
                    raise LeaseError("completed job is missing its immutable response")
                return prior.completion_response

            job = self._validate_claim_active(claim, now=now)
            if now < job.admitted_at:
                raise LeaseError("completion timestamp precedes admission")
            if estimated_actual_units > job.estimated_cost_units:
                raise CostCeilingError(
                    "metered completion estimate exceeds the admitted reservation"
                )
            self.costs.preflight_transition(
                claim.cost_reservation_id, target_state="accounted"
            )
            usage_record = self.costs.meter.record(
                idempotency_key=usage_key,
                operation=operation,
                quantity=quantity,
                rate=configured_rate,
                evidence_ref=usage_evidence_ref,
                observed_at=now,
                job_id=claim.job_id,
                route_id=claim.route_id,
                fencing_token=claim.fencing_token,
                reservation_id=claim.cost_reservation_id,
                result_digest=result_digest,
            )
            if usage_record.record_id != usage_record_id:  # pragma: no cover - digest invariant
                raise AdmissionConflict("usage record id does not match deterministic completion id")
            self.costs.finalize(claim.cost_reservation_id)
            self.queue.complete(
                job.job_id,
                fencing_token=claim.fencing_token,
                result=result,
                result_digest=result_digest,
                completion_claim_digest=claim_digest,
                completion_input_digest=completion_input_digest,
                completion_response=response,
                now=now,
            )
            self.load.release(claim.route_id)
            return response

    def fail(
        self,
        claim: ClaimResult,
        *,
        exception_class: str,
        code: str,
        message: str,
        evidence_ref: str,
        retry_delay_seconds: int,
        now: int,
    ) -> Mapping[str, Any]:
        exception_class = _nonempty(exception_class, "exception_class")
        code = _nonempty(code, "code")
        message = _nonempty(message, "message")
        evidence_ref = _nonempty(evidence_ref, "evidence_ref")
        retry_delay_seconds = _unit(retry_delay_seconds, "retry_delay_seconds")
        now = _timestamp(now, "now")
        with (
            self._lock,
            self.queue._lock,
            self.authority._lock,
            self.load._lock,
            self.costs._lock,
            self.costs.ledger._lock,
            self.exceptions._lock,
        ):
            job = self._validate_claim_active(claim, now=now)
            self.costs.preflight_transition(
                claim.cost_reservation_id, target_state="released"
            )
            if len(self.exceptions._evidence) >= self.exceptions.max_records:
                raise RetentionCapacityError("bounded exception-evidence ledger is full")
            self.exceptions.record(
                exception_class=exception_class,
                code=code,
                message=message,
                evidence_ref=evidence_ref,
                observed_at=now,
            )
            self.costs.release(claim.cost_reservation_id)
            failed = self.queue.fail(
                job.job_id,
                fencing_token=claim.fencing_token,
                retry_delay_seconds=retry_delay_seconds,
                now=now,
            )
            self.load.release(claim.route_id)
            return ImmutableJSONDict(
                {"job_id": failed.job_id, "state": failed.state, "attempts": failed.attempts}
            )

    def reap_expired(
        self, *, retry_delay_seconds: int, now: int
    ) -> tuple[Mapping[str, Any], ...]:
        retry_delay_seconds = _unit(retry_delay_seconds, "retry_delay_seconds")
        now = _timestamp(now, "now")
        reaped: list[Mapping[str, Any]] = []
        with (
            self._lock,
            self.queue._lock,
            self.load._lock,
            self.costs._lock,
            self.costs.ledger._lock,
            self.exceptions._lock,
        ):
            jobs = self.queue.expired(now=now)
            if len(self.exceptions._evidence) + len(jobs) > self.exceptions.max_records:
                raise RetentionCapacityError(
                    "bounded exception evidence cannot retain the full reap batch"
                )
            needed_ledger_entries = 0
            for job in jobs:
                if job.reservation_id is None or job.lease_route is None:
                    raise LeaseError("expired claim is missing reservation or route custody")
                self.costs.require_active(
                    job.reservation_id,
                    job_id=job.job_id,
                    fencing_token=job.fencing_token,
                    route_id=job.lease_route,
                    units=job.estimated_cost_units,
                )
                self.costs.preflight_transition(
                    job.reservation_id, target_state="released"
                )
                release_key = f"{job.reservation_id}:released"
                needed_ledger_entries += release_key not in self.costs.ledger._idempotency
            if (
                len(self.costs.ledger._entries) + needed_ledger_entries
                > self.costs.ledger.max_entries
            ):
                raise RetentionCapacityError(
                    "bounded cost ledger cannot retain the full reap batch"
                )
            for job in jobs:
                token = job.fencing_token
                self.exceptions.record(
                    exception_class="LeaseExpired",
                    code="lease_expired",
                    message=f"lease expired for {job.job_id} attempt {job.attempts}",
                    evidence_ref=f"queue:{job.job_id}:fence:{token}",
                    observed_at=now,
                )
                self.costs.release(job.reservation_id or "")
                expired = self.queue.expire(
                    job.job_id,
                    fencing_token=token,
                    retry_delay_seconds=retry_delay_seconds,
                    now=now,
                )
                self.load.release(job.lease_route or "")
                reaped.append(
                    ImmutableJSONDict(
                        {"job_id": expired.job_id, "state": expired.state, "fencing_token": token}
                    )
                )
        return tuple(reaped)

    def report(self) -> Mapping[str, Any]:
        with self._lock:
            cost_summary = dict(self.costs.summary())
            cost_summary["meter"] = self.costs.meter.summary()
            return _freeze_mapping(
                {
                    "schema": "ct.penta.runtime-flow-control.report.v1",
                    "capability_pack": "crownthrive.penta.runtime-flow-control.v1",
                    "lifecycle_state": "CONTROLLED_TEST",
                    "durable_store_bound": False,
                    "external_effect_adapter_bound": False,
                    "external_effects_enabled": False,
                    "issuer_authentication": False,
                    "quorum_eligible": False,
                    "vote_eligible": False,
                    "certification_effect": False,
                    "money_movement": False,
                    "queue": self.queue.summary(),
                    "load": self.load.summary(),
                    "authority": self.authority.summary(),
                    "costs": cost_summary,
                    "exceptions": self.exceptions.report(),
                },
                field_name="flow-control report",
            )
