#!/usr/bin/env python3
"""Deterministic CrownThrive OS governance and activation readiness diagnostic.

This tool evaluates a supplied, already-governed snapshot. It performs no provider
writes, creates no authority, and never represents its output as independent
certification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

CONTRACT_KEY = "ct.product.penta-os-readiness-diagnostic.v1"
POLICY_KEY = "ct.penta.pr-terminalization-policy.v2"
SENSITIVE_KEY_PARTS = (
    "secret",
    "token",
    "password",
    "private_key",
    "api_key",
    "credential",
    "authorization",
    "cookie",
)
HEX40 = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
PASS_VALUES = {"PASS", "N/A", "NOT_APPLICABLE"}
HOLD_VALUES = {"HOLD", "FAIL", "FAILED", "DENY", "DENIED", "BLOCK", "BLOCKED"}


@dataclass(frozen=True)
class DomainResult:
    key: str
    state: str
    score: int
    max_score: int
    findings: tuple[str, ...]


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def redact(value: Any) -> Any:
    """Recursively remove secret-like values before hashing or reporting."""
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _is_sensitive_key(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    return value


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _mapping(snapshot: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = snapshot.get(key, {})
    return value if isinstance(value, Mapping) else {}


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _domain(key: str, holds: Iterable[str], unknowns: Iterable[str]) -> DomainResult:
    hold_list = tuple(holds)
    unknown_list = tuple(unknowns)
    if hold_list:
        return DomainResult(key, "HOLD", 0, 20, hold_list + unknown_list)
    if unknown_list:
        return DomainResult(key, "UNKNOWN", 5, 20, unknown_list)
    return DomainResult(key, "PASS", 20, 20, ())


def evaluate_source(snapshot: Mapping[str, Any]) -> DomainResult:
    source = _mapping(snapshot, "source")
    holds: list[str] = []
    unknowns: list[str] = []
    main_sha = source.get("main_sha")
    deployment_sha = source.get("deployment_sha")
    registry_version = source.get("registry_version")
    registry_count = _nonnegative_int(source.get("registry_count"))
    registry_blob_sha = source.get("registry_blob_sha")

    if not isinstance(main_sha, str) or not HEX40.fullmatch(main_sha):
        unknowns.append("source.main_sha is absent or not an exact 40-character commit SHA")
    if not isinstance(deployment_sha, str) or not HEX40.fullmatch(deployment_sha):
        unknowns.append("source.deployment_sha is absent or not an exact 40-character commit SHA")
    if isinstance(main_sha, str) and isinstance(deployment_sha, str) and main_sha != deployment_sha:
        holds.append("production deployment does not match protected main")
    if not isinstance(registry_version, str) or not registry_version.strip():
        unknowns.append("source.registry_version is missing")
    if registry_count is None or registry_count == 0:
        unknowns.append("source.registry_count is missing or zero")
    if not isinstance(registry_blob_sha, str) or not HEX40.fullmatch(registry_blob_sha):
        unknowns.append("source.registry_blob_sha is missing or invalid")
    return _domain("source_deployment_alignment", holds, unknowns)


def evaluate_pr(snapshot: Mapping[str, Any]) -> DomainResult:
    pr = _mapping(snapshot, "pr")
    holds: list[str] = []
    unknowns: list[str] = []
    if pr.get("policy_key") != POLICY_KEY:
        holds.append("terminalization policy is not ct.penta.pr-terminalization-policy.v2")
    if pr.get("provider_sync_stale") is True:
        holds.append("PR provider synchronization is stale")
    elif pr.get("provider_sync_stale") is not False:
        unknowns.append("pr.provider_sync_stale is not explicitly false")

    for field in ("unclassified_v2", "overdue"):
        value = _nonnegative_int(pr.get(field))
        if value is None:
            unknowns.append(f"pr.{field} is missing")
        elif value > 0:
            holds.append(f"pr.{field}={value} requires remediation")
    return _domain("pr_terminalization_hygiene", holds, unknowns)


def evaluate_identity(snapshot: Mapping[str, Any]) -> DomainResult:
    identity = _mapping(snapshot, "identity")
    holds: list[str] = []
    unknowns: list[str] = []
    registry_count = _nonnegative_int(identity.get("registry_count"))
    if registry_count is None or registry_count == 0:
        unknowns.append("identity.registry_count is missing or zero")
    if identity.get("projection_drift") is True:
        holds.append("Identity Fabric projection drift is present")
    elif identity.get("projection_drift") is not False:
        unknowns.append("identity.projection_drift is not explicitly false")
    source_digest = identity.get("source_sha256")
    if not isinstance(source_digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", source_digest):
        unknowns.append("identity.source_sha256 is missing or invalid")
    return _domain("identity_fabric", holds, unknowns)


def evaluate_dnd(snapshot: Mapping[str, Any]) -> DomainResult:
    dnd = _mapping(snapshot, "dnd")
    holds: list[str] = []
    unknowns: list[str] = []
    if dnd.get("canonical_identity") != "penta.dnd":
        holds.append("canonical PentaDND identity is not penta.dnd")
    if dnd.get("runtime_present") is not True:
        unknowns.append("PentaDND runtime presence is not proven")
    if dnd.get("pm_execution_eligible") is not False:
        holds.append("PentaDND unexpectedly has PentaPM execution eligibility")
    if dnd.get("authority_created") is not False:
        holds.append("PentaDND scope state does not prove authority_created=false")
    active_scope_kinds = _nonnegative_int(dnd.get("active_scope_kinds"))
    if active_scope_kinds is None or active_scope_kinds == 0:
        unknowns.append("no active registered PentaDND scope kinds were proven")
    return _domain("penta_dnd_authority_safety", holds, unknowns)


def evaluate_gates(snapshot: Mapping[str, Any]) -> DomainResult:
    gates = _mapping(snapshot, "gates")
    holds: list[str] = []
    unknowns: list[str] = []
    for key in ("penta_security", "chlom", "cie", "penta_certifier"):
        raw = gates.get(key)
        value = str(raw).strip().upper() if raw is not None else "UNKNOWN"
        if value in HOLD_VALUES:
            holds.append(f"gate {key} is {value}")
        elif value not in PASS_VALUES:
            unknowns.append(f"gate {key} is {value}")
    return _domain("independent_gate_chain", holds, unknowns)


def evaluate(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    safe_input = redact(snapshot)
    domains = (
        evaluate_source(safe_input),
        evaluate_pr(safe_input),
        evaluate_identity(safe_input),
        evaluate_dnd(safe_input),
        evaluate_gates(safe_input),
    )
    states = {item.state for item in domains}
    if "HOLD" in states:
        disposition = "HOLD_REMEDIATION_REQUIRED"
    elif "UNKNOWN" in states:
        disposition = "UNKNOWN_EVIDENCE_INCOMPLETE"
    else:
        disposition = "READY_FOR_INDEPENDENT_REVIEW"

    remediation = [finding for item in domains if item.state != "PASS" for finding in item.findings]
    result = {
        "contract_key": CONTRACT_KEY,
        "schema_version": "1.0.0",
        "observed_at": safe_input.get("observed_at"),
        "input_digest_sha256": canonical_digest(safe_input),
        "disposition": disposition,
        "score": sum(item.score for item in domains),
        "max_score": sum(item.max_score for item in domains),
        "domains": [asdict(item) for item in domains],
        "remediation": remediation,
        "authority_created": False,
        "provider_writes_performed": False,
        "independent_certification": "NOT_PERFORMED",
        "notice": "Diagnostic evidence only. This output is not certification, approval, a rights grant, or release authority.",
    }
    result["result_digest_sha256"] = canonical_digest(result)
    return result


def render_markdown(result: Mapping[str, Any]) -> str:
    rows = [
        "# CrownThrive OS Governance & Activation Readiness Diagnostic",
        "",
        f"- **Disposition:** `{result['disposition']}`",
        f"- **Readiness score:** `{result['score']}/{result['max_score']}`",
        f"- **Input digest:** `{result['input_digest_sha256']}`",
        f"- **Result digest:** `{result['result_digest_sha256']}`",
        "- **Independent certification:** `NOT_PERFORMED`",
        "",
        "## Domain results",
        "",
    ]
    for domain in result["domains"]:
        rows.append(f"### {domain['key']} — {domain['state']} ({domain['score']}/{domain['max_score']})")
        if domain["findings"]:
            rows.extend(f"- {finding}" for finding in domain["findings"])
        else:
            rows.append("- No blocking or unknown predicate was found in the supplied snapshot.")
        rows.append("")
    rows.extend(("## Boundary", "", str(result["notice"]), ""))
    return "\n".join(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Governed input snapshot JSON")
    parser.add_argument("--json-output", required=True, type=Path, help="Machine-readable result path")
    parser.add_argument("--markdown-output", required=True, type=Path, help="Operator report path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"diagnostic input error: {exc.__class__.__name__}", file=sys.stderr)
        return 2
    if not isinstance(snapshot, Mapping):
        print("diagnostic input error: root JSON value must be an object", file=sys.stderr)
        return 2

    result = evaluate(snapshot)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
