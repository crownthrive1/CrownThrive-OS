#!/usr/bin/env python3
"""Fail-closed evaluator for the CrownThrive D3 Founder approval window.

The Founder window satisfies only the reserved human-approval predicate.  It
never manufactures technical, security, independent-verifier, rollback,
provider, rights, financial, credential, legal, privacy, or commercial proof.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


FOUNDER_REF = "ct.person.founder.kavonte-jones-sr"
RISK_CLASS = "D3"
APPROVAL_EFFECT = "human_approval_predicate_only"

ELIGIBLE_ACTION_CLASSES = {
    "commercial_release",
    "monetization_activation",
    "production_gap_closure",
    "production_hardening",
    "production_release",
    "provider_activation",
}

BASE_RELEASE_GATES = {
    "commercial_readiness",
    "exact_snapshot",
    "independent_verification",
    "monetization_readiness",
    "observability",
    "post_release_readback",
    "production_readiness",
    "rollback_readback",
    "security",
    "technical_tests",
}

EFFECT_GATES = {
    "contract_or_legal_commitment": {"legal_signatory_authority"},
    "credential_mutation": {"credential_custody"},
    "license_grant": {"rights_authority"},
    "money_movement": {"money_movement_authority"},
    "payment": {"money_movement_authority"},
    "personal_data": {"privacy_compliance"},
    "provider_write": {"provider_write_certification"},
    "rights_disposition": {"rights_authority"},
    "settlement": {"money_movement_authority"},
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _check(name: str, passed: bool, reason: str) -> dict[str, str]:
    result = {"check": name, "status": "PASS" if passed else "FAIL"}
    if not passed:
        result["reason"] = reason
    return result


def _evidence_passes(
    gate_key: str,
    evidence: Any,
    *,
    exact_version_ref: str,
    content_sha256: str,
) -> tuple[bool, str]:
    if not isinstance(evidence, dict):
        return False, "gate evidence is missing"
    if evidence.get("state") != "PASS":
        return False, "gate state must be PASS"
    if not isinstance(evidence.get("evidence_ref"), str) or not evidence["evidence_ref"].strip():
        return False, "evidence_ref is required"
    if not _HEX64.fullmatch(str(evidence.get("evidence_sha256", ""))):
        return False, "evidence_sha256 must be a lowercase SHA-256"
    if evidence.get("exact_version_ref") != exact_version_ref:
        return False, "gate exact_version_ref does not match the candidate"
    if evidence.get("content_sha256") != content_sha256:
        return False, "gate content_sha256 does not match the candidate"
    if not isinstance(evidence.get("verified_by"), str) or not evidence["verified_by"].strip():
        return False, "verified_by is required"
    if _parse_utc(evidence.get("verified_at")) is None:
        return False, "verified_at must be an offset-aware timestamp"
    if gate_key == "rollback_readback":
        if evidence.get("rollback_tested") is not True:
            return False, "rollback must be tested"
        baseline = str(evidence.get("baseline_sha256", ""))
        post = str(evidence.get("post_rollback_sha256", ""))
        if not _HEX64.fullmatch(baseline) or post != baseline:
            return False, "post-rollback readback must match the SHA-256 baseline"
    return True, ""


def evaluate(bundle: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Evaluate human approval and full release eligibility independently."""

    evaluated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    window = bundle.get("window") if isinstance(bundle.get("window"), dict) else {}
    candidate = bundle.get("candidate") if isinstance(bundle.get("candidate"), dict) else {}
    gates = bundle.get("gates") if isinstance(bundle.get("gates"), dict) else {}
    checks: list[dict[str, str]] = []

    starts_at = _parse_utc(window.get("starts_at"))
    expires_at = _parse_utc(window.get("expires_at"))
    duration_ok = bool(starts_at and expires_at and expires_at - starts_at == timedelta(days=14))
    active = bool(starts_at and expires_at and starts_at <= evaluated_at < expires_at)

    checks.extend(
        [
            _check("window.id", bool(window.get("window_id")), "window_id is required"),
            _check(
                "window.founder",
                window.get("founder_ref") == FOUNDER_REF,
                "the canonical Founder reference is required",
            ),
            _check(
                "window.risk_class",
                window.get("risk_class") == RISK_CLASS,
                "the window must be D3",
            ),
            _check(
                "window.effect",
                window.get("approval_effect") == APPROVAL_EFFECT,
                "the window may satisfy only the human-approval predicate",
            ),
            _check("window.duration", duration_ok, "the window must be exactly fourteen days"),
            _check("window.active", active, "the window is not active at evaluation time"),
            _check(
                "window.nonrenewing",
                window.get("nonrenewing") is True,
                "the window must be nonrenewing",
            ),
            _check(
                "window.exact_candidate",
                window.get("exact_candidate_required") is True,
                "exact-candidate binding is required",
            ),
            _check(
                "window.independent_evidence",
                window.get("independent_evidence_required") is True
                and window.get("independent_evidence_substitution_allowed") is False,
                "independent evidence must remain required and non-substitutable",
            ),
            _check(
                "window.revocation",
                window.get("revoked") is False,
                "the approval window is revoked or revocation state is missing",
            ),
        ]
    )

    action_class = candidate.get("action_class")
    exact_version_ref = candidate.get("exact_version_ref")
    content_sha256 = candidate.get("content_sha256")
    producer_ref = candidate.get("producer_ref")
    requested_effects = candidate.get("requested_effects", [])

    checks.extend(
        [
            _check(
                "candidate.action_class",
                action_class in ELIGIBLE_ACTION_CLASSES,
                "action_class is outside the approved production scope",
            ),
            _check(
                "candidate.risk_class",
                candidate.get("risk_class") == RISK_CLASS,
                "candidate risk_class must be D3",
            ),
            _check(
                "candidate.environment",
                candidate.get("environment") == "production",
                "only production candidates are eligible",
            ),
            _check(
                "candidate.subject_ref",
                isinstance(candidate.get("subject_ref"), str) and bool(candidate["subject_ref"].strip()),
                "subject_ref is required",
            ),
            _check(
                "candidate.exact_version_ref",
                isinstance(exact_version_ref, str) and bool(exact_version_ref.strip()),
                "exact_version_ref is required",
            ),
            _check(
                "candidate.content_sha256",
                isinstance(content_sha256, str) and bool(_HEX64.fullmatch(content_sha256)),
                "content_sha256 must be a lowercase SHA-256",
            ),
            _check(
                "candidate.producer_ref",
                isinstance(producer_ref, str) and bool(producer_ref.strip()),
                "producer_ref is required",
            ),
            _check(
                "candidate.requested_effects",
                isinstance(requested_effects, list)
                and all(isinstance(item, str) and item in EFFECT_GATES for item in requested_effects),
                "requested_effects must contain only governed effect keys",
            ),
        ]
    )

    human_checks = [item for item in checks if item["check"].startswith(("window.", "candidate."))]
    human_approval_satisfied = not any(item["status"] == "FAIL" for item in human_checks)

    required_gates = set(BASE_RELEASE_GATES)
    if isinstance(requested_effects, list):
        for effect in requested_effects:
            required_gates.update(EFFECT_GATES.get(effect, set()))

    if isinstance(exact_version_ref, str) and isinstance(content_sha256, str):
        for gate_key in sorted(required_gates):
            passed, reason = _evidence_passes(
                gate_key,
                gates.get(gate_key),
                exact_version_ref=exact_version_ref,
                content_sha256=content_sha256,
            )
            checks.append(_check(f"gate.{gate_key}", passed, reason))
    else:
        checks.append(_check("gate.exact_candidate", False, "candidate snapshot is invalid"))

    independent = gates.get("independent_verification", {})
    independent_separated = bool(
        isinstance(independent, dict)
        and independent.get("verified_by")
        and producer_ref
        and independent.get("verified_by") != producer_ref
    )
    checks.append(
        _check(
            "gate.independent_separation",
            independent_separated,
            "independent verifier must differ from the producer",
        )
    )

    release_eligible = human_approval_satisfied and not any(
        item["status"] == "FAIL" for item in checks if item["check"].startswith("gate.")
    )
    return {
        "decision": "RELEASE_ELIGIBLE" if release_eligible else "HOLD",
        "human_approval_state": "APPROVED_BY_WINDOW" if human_approval_satisfied else "NOT_APPROVED",
        "human_approval_effect": APPROVAL_EFFECT,
        "release_authority_created": False,
        "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z"),
        "required_gates": sorted(required_gates),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="JSON D3 approval/release evidence bundle")
    parser.add_argument("--report", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"HOLD: unable to read evidence bundle: {exc}", file=sys.stderr)
        return 2
    report = evaluate(bundle)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["decision"] == "RELEASE_ELIGIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
