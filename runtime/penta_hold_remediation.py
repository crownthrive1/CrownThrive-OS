#!/usr/bin/env python3
"""Penta HOLD self-remediation control loop.

This module closes the gap between a governed CI HOLD and the PentaPR lifecycle.
It is deliberately fail-closed: it classifies and routes only known bounded failure
signatures, records an append-only DAIL event chain, deduplicates retries by exact
PR head/check/signature, rejects stale heads, caps retry attempts, and never turns
remediation evidence into merge authority.

PentaCrawler -> detects failed governed checks
PentaFlows   -> classifies/routes bounded work
PentaHelper  -> produces an explicit remediation instruction
DAIL         -> append-only causal evidence
PentaPR      -> receives a handoff only after the exact current head is green
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence


class EventType(str, Enum):
    HOLD_DETECTED = "HOLD_DETECTED"
    HOLD_CLASSIFIED = "HOLD_CLASSIFIED"
    REMEDIATION_ROUTED = "REMEDIATION_ROUTED"
    REMEDIATION_STARTED = "REMEDIATION_STARTED"
    REMEDIATION_COMPLETED = "REMEDIATION_COMPLETED"
    RETEST_REQUESTED = "RETEST_REQUESTED"
    HOLD_CLEARED = "HOLD_CLEARED"
    REMEDIATION_ESCALATED = "REMEDIATION_ESCALATED"
    STALE_SUPERSEDED = "STALE_SUPERSEDED"
    PENTAPR_HANDOFF_READY = "PENTAPR_HANDOFF_READY"


@dataclass(frozen=True)
class CheckFailure:
    name: str
    conclusion: str
    summary: str = ""

    def normalized_signature(self) -> str:
        material = f"{self.name}\n{self.conclusion}\n{self.summary}".casefold()
        material = re.sub(r"\b[0-9a-f]{7,64}\b", "<sha>", material)
        material = re.sub(r"\b\d{4}-\d{2}-\d{2}t[^\s]+", "<time>", material)
        material = re.sub(r"\s+", " ", material).strip()
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PullRequestState:
    repository: str
    number: int
    head_sha: str
    current_head_sha: str
    draft: bool
    failures: tuple[CheckFailure, ...] = ()
    required_checks_total: int = 0
    required_checks_successful: int = 0

    @property
    def exact_head(self) -> bool:
        return self.head_sha == self.current_head_sha

    @property
    def governed_green(self) -> bool:
        return (
            self.exact_head
            and not self.failures
            and self.required_checks_total > 0
            and self.required_checks_successful == self.required_checks_total
        )


@dataclass(frozen=True)
class Route:
    route_id: str
    owner_penta: str
    helper_action: str
    safe_to_autoremediate: bool
    patterns: tuple[re.Pattern[str], ...]

    def matches(self, failure: CheckFailure) -> bool:
        haystack = f"{failure.name}\n{failure.summary}".casefold()
        return any(pattern.search(haystack) for pattern in self.patterns)


DEFAULT_ROUTES: tuple[Route, ...] = (
    Route(
        route_id="family-interoperability",
        owner_penta="PentaInterOps",
        helper_action=(
            "Reconcile runtime/component inventory with the Penta Family primary-child map; "
            "modify only the authoritative registries required to make discovered identities "
            "unambiguous, then run family/interoperability validators."
        ),
        safe_to_autoremediate=True,
        patterns=(
            re.compile(r"collision governance"),
            re.compile(r"penta interoperability"),
            re.compile(r"penta runtime suite"),
            re.compile(r"child[- ]member"),
            re.compile(r"family[- ]census"),
            re.compile(r"penta[._ -]?evi[-_ ]?builder"),
            re.compile(r"penta[._ -]?immune"),
        ),
    ),
    Route(
        route_id="provider-convergence",
        owner_penta="PentaBind",
        helper_action=(
            "Refresh provider-custody/readback evidence from the authoritative provider; "
            "reconcile migration/provider drift without fabricating evidence or changing "
            "provider authority, then rerun the convergence validator."
        ),
        safe_to_autoremediate=False,
        patterns=(
            re.compile(r"governed merge gate"),
            re.compile(r"supabase.*convergence"),
            re.compile(r"provider.*custody"),
            re.compile(r"migration[- ]count.*drift"),
        ),
    ),
    Route(
        route_id="documentation-governance",
        owner_penta="PentaDocs",
        helper_action=(
            "Reconcile governed documentation source/manifest drift, preserve immutable historical "
            "baselines, run PentaDocs quality/MDX/link validators, and publish only exact-source evidence."
        ),
        safe_to_autoremediate=True,
        patterns=(
            re.compile(r"documentation governance"),
            re.compile(r"pentadocs"),
            re.compile(r"mintlify"),
            re.compile(r"mdx"),
        ),
    ),
)


@dataclass(frozen=True)
class Remediation:
    fingerprint: str
    repository: str
    pr_number: int
    head_sha: str
    check_name: str
    failure_signature: str
    route_id: str
    owner_penta: str
    helper_action: str
    safe_to_autoremediate: bool
    disposition: str
    attempt: int


@dataclass
class DAILRecord:
    sequence: int
    event_type: EventType
    fingerprint: str
    repository: str
    pr_number: int
    head_sha: str
    payload: Mapping[str, object]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_hash: str = "GENESIS"
    record_hash: str = ""

    def seal(self) -> "DAILRecord":
        material = {
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "fingerprint": self.fingerprint,
            "repository": self.repository,
            "pr_number": self.pr_number,
            "head_sha": self.head_sha,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
        }
        object.__setattr__(
            self,
            "record_hash",
            hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        )
        return self


class DAILLedger:
    """In-memory append-only ledger with hash chaining; serialize as JSONL for transport."""

    def __init__(self) -> None:
        self.records: list[DAILRecord] = []

    def append(
        self,
        event_type: EventType,
        *,
        fingerprint: str,
        pr: PullRequestState,
        payload: Mapping[str, object] | None = None,
    ) -> DAILRecord:
        previous_hash = self.records[-1].record_hash if self.records else "GENESIS"
        record = DAILRecord(
            sequence=len(self.records) + 1,
            event_type=event_type,
            fingerprint=fingerprint,
            repository=pr.repository,
            pr_number=pr.number,
            head_sha=pr.head_sha,
            payload=payload or {},
            previous_hash=previous_hash,
        ).seal()
        self.records.append(record)
        return record

    def verify(self) -> bool:
        previous = "GENESIS"
        for index, record in enumerate(self.records, start=1):
            if record.sequence != index or record.previous_hash != previous:
                return False
            existing = record.record_hash
            record.seal()
            if record.record_hash != existing:
                return False
            previous = existing
        return True

    def write_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for record in self.records:
                payload = asdict(record)
                payload["event_type"] = record.event_type.value
                handle.write(json.dumps(payload, sort_keys=True) + "\n")


class PentaHoldRemediator:
    """Deterministic, bounded remediation coordinator."""

    def __init__(
        self,
        *,
        routes: Sequence[Route] = DEFAULT_ROUTES,
        max_attempts: int = 3,
        attempt_store: MutableMapping[str, int] | None = None,
        ledger: DAILLedger | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.routes = tuple(routes)
        self.max_attempts = max_attempts
        self.attempt_store = attempt_store if attempt_store is not None else {}
        self.ledger = ledger or DAILLedger()

    @staticmethod
    def fingerprint(pr: PullRequestState, failure: CheckFailure) -> str:
        material = (
            f"{pr.repository.casefold()}|{pr.number}|{pr.head_sha}|"
            f"{failure.name.casefold()}|{failure.normalized_signature()}"
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def classify(self, failure: CheckFailure) -> Route | None:
        matches = [route for route in self.routes if route.matches(failure)]
        if len(matches) != 1:
            return None
        return matches[0]

    def evaluate(self, pr: PullRequestState) -> list[Remediation]:
        if not pr.exact_head:
            fingerprint = hashlib.sha256(
                f"{pr.repository}|{pr.number}|{pr.head_sha}|stale".encode()
            ).hexdigest()
            self.ledger.append(
                EventType.STALE_SUPERSEDED,
                fingerprint=fingerprint,
                pr=pr,
                payload={"current_head_sha": pr.current_head_sha},
            )
            return []

        if pr.governed_green:
            fingerprint = hashlib.sha256(
                f"{pr.repository}|{pr.number}|{pr.head_sha}|green".encode()
            ).hexdigest()
            self.ledger.append(EventType.HOLD_CLEARED, fingerprint=fingerprint, pr=pr)
            self.ledger.append(
                EventType.PENTAPR_HANDOFF_READY,
                fingerprint=fingerprint,
                pr=pr,
                payload={"merge_authority_granted": False, "exact_head_green": True},
            )
            return []

        plans: list[Remediation] = []
        for failure in pr.failures:
            fingerprint = self.fingerprint(pr, failure)
            self.ledger.append(
                EventType.HOLD_DETECTED,
                fingerprint=fingerprint,
                pr=pr,
                payload={"check": failure.name, "conclusion": failure.conclusion},
            )
            route = self.classify(failure)
            if route is None:
                self.ledger.append(
                    EventType.REMEDIATION_ESCALATED,
                    fingerprint=fingerprint,
                    pr=pr,
                    payload={"reason": "unclassified_or_ambiguous", "check": failure.name},
                )
                continue

            self.ledger.append(
                EventType.HOLD_CLASSIFIED,
                fingerprint=fingerprint,
                pr=pr,
                payload={"route_id": route.route_id, "owner_penta": route.owner_penta},
            )
            attempt = self.attempt_store.get(fingerprint, 0) + 1
            if attempt > self.max_attempts:
                self.ledger.append(
                    EventType.REMEDIATION_ESCALATED,
                    fingerprint=fingerprint,
                    pr=pr,
                    payload={"reason": "attempt_cap", "max_attempts": self.max_attempts},
                )
                continue
            self.attempt_store[fingerprint] = attempt
            disposition = "AUTO_REMEDIATE" if route.safe_to_autoremediate else "EVIDENCE_REQUIRED"
            self.ledger.append(
                EventType.REMEDIATION_ROUTED,
                fingerprint=fingerprint,
                pr=pr,
                payload={
                    "route_id": route.route_id,
                    "owner_penta": route.owner_penta,
                    "disposition": disposition,
                    "attempt": attempt,
                },
            )
            plans.append(
                Remediation(
                    fingerprint=fingerprint,
                    repository=pr.repository,
                    pr_number=pr.number,
                    head_sha=pr.head_sha,
                    check_name=failure.name,
                    failure_signature=failure.normalized_signature(),
                    route_id=route.route_id,
                    owner_penta=route.owner_penta,
                    helper_action=route.helper_action,
                    safe_to_autoremediate=route.safe_to_autoremediate,
                    disposition=disposition,
                    attempt=attempt,
                )
            )
        return plans

    def record_completion(self, pr: PullRequestState, plan: Remediation, *, evidence: Mapping[str, object]) -> None:
        self.ledger.append(
            EventType.REMEDIATION_COMPLETED,
            fingerprint=plan.fingerprint,
            pr=pr,
            payload={"owner_penta": plan.owner_penta, "evidence": dict(evidence)},
        )
        self.ledger.append(
            EventType.RETEST_REQUESTED,
            fingerprint=plan.fingerprint,
            pr=pr,
            payload={"exact_head_required": True, "waiver_allowed": False},
        )


def _load_pr(path: Path) -> PullRequestState:
    raw = json.loads(path.read_text(encoding="utf-8"))
    failures = tuple(CheckFailure(**failure) for failure in raw.get("failures", []))
    return PullRequestState(
        repository=raw["repository"],
        number=int(raw["number"]),
        head_sha=raw["head_sha"],
        current_head_sha=raw.get("current_head_sha", raw["head_sha"]),
        draft=bool(raw.get("draft", False)),
        failures=failures,
        required_checks_total=int(raw.get("required_checks_total", 0)),
        required_checks_successful=int(raw.get("required_checks_successful", 0)),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Penta HOLD self-remediation planner")
    parser.add_argument("--input", type=Path, required=True, help="PR/check-state JSON")
    parser.add_argument("--plan", type=Path, required=True, help="remediation plan JSON")
    parser.add_argument("--ledger", type=Path, required=True, help="DAIL JSONL output")
    args = parser.parse_args(argv)

    pr = _load_pr(args.input)
    remediator = PentaHoldRemediator()
    plans = remediator.evaluate(pr)
    args.plan.parent.mkdir(parents=True, exist_ok=True)
    args.plan.write_text(json.dumps([asdict(plan) for plan in plans], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    remediator.ledger.write_jsonl(args.ledger)
    if not remediator.ledger.verify():
        raise RuntimeError("DAIL ledger verification failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
