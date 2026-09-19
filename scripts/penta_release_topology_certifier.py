#!/usr/bin/env python3
"""Deterministic fail-closed verifier for CrownThrive mandatory release topology.

This verifier consumes evidence only. It never creates authority, rights, credentials,
provider writes, legal commitments, money movement, or certification evidence.

The mandatory topology has two distinct verification points:

PRE_RELEASE:
Build -> security scan -> threat model -> tests -> PentaSecurity -> CHLOM rights/authority
-> applicable CIE -> independent PentaCertifier -> release eligibility.

POST_RELEASE:
The same exact-head pre-release chain -> independent release execution -> exact outcome
readback.

DAIL Human/Hybrid/Machine remain the canonical lane projections. The evidence,
decision, and execution values checked here are semantic stages, not token classes.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from penta_d3_approval import evaluate as evaluate_d3_approval  # noqa: E402

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

EVIDENCE_STAGES = ("build", "security_scan", "threat_model", "tests")
PHASES = ("pre_release", "post_release")


def _fail(check: str, reason: str) -> dict[str, str]:
    return {"check": check, "status": "FAIL", "reason": reason}


def _pass(check: str) -> dict[str, str]:
    return {"check": check, "status": "PASS"}


def _receipt_checks(
    checks: list[dict[str, str]],
    *,
    name: str,
    receipt: Any,
    release_sha: str,
    semantic_stage: str,
    decision_field: str = "state",
    expected_decision: str = "PASS",
) -> str | None:
    if not isinstance(receipt, dict):
        checks.append(_fail(name, f"{name} receipt is missing"))
        return None

    actor_id = str(receipt.get("actor_id") or "").strip()
    if receipt.get(decision_field) != expected_decision:
        checks.append(
            _fail(
                f"{name}.decision",
                f"expected {decision_field}={expected_decision!r}, got {receipt.get(decision_field)!r}",
            )
        )
    else:
        checks.append(_pass(f"{name}.decision"))

    if receipt.get("exact_version_ref") != release_sha:
        checks.append(_fail(f"{name}.exact_version", "receipt does not bind the exact release head"))
    else:
        checks.append(_pass(f"{name}.exact_version"))

    if receipt.get("semantic_stage") != semantic_stage:
        checks.append(
            _fail(
                f"{name}.semantic_stage",
                f"expected semantic_stage={semantic_stage!r}; DAIL lane identity is not replaced by this stage",
            )
        )
    else:
        checks.append(_pass(f"{name}.semantic_stage"))

    evidence_ref = str(receipt.get("evidence_ref") or "").strip()
    evidence_sha = str(receipt.get("evidence_sha256") or "")
    if not evidence_ref or not _HEX64.fullmatch(evidence_sha):
        checks.append(_fail(f"{name}.integrity", "evidence_ref and lowercase SHA-256 are required"))
    else:
        checks.append(_pass(f"{name}.integrity"))

    if not actor_id:
        checks.append(_fail(f"{name}.actor", "actor_id is required"))
        return None
    checks.append(_pass(f"{name}.actor"))
    return actor_id


def _verify_pre_release(
    bundle: dict[str, Any], *, now: datetime | None = None
) -> tuple[list[dict[str, str]], dict[str, str | None]]:
    """Verify all authority/evidence gates that must pass before release execution."""
    checks: list[dict[str, str]] = []
    actors: dict[str, str | None] = {
        "originator": None,
        "penta_security": None,
        "chlom": None,
        "cie": None,
        "penta_certifier": None,
    }
    release = bundle.get("release") if isinstance(bundle.get("release"), dict) else {}
    release_sha = str(release.get("commit_sha") or "")
    risk_class = str(release.get("risk_class") or "").upper()
    originator_id = str(bundle.get("originator_id") or "").strip()
    producer_ids = {str(x).strip() for x in bundle.get("producer_ids", []) if str(x).strip()}

    if release.get("repository") != "crownthrive1/CrownThrive-OS" or not _HEX40.fullmatch(release_sha):
        checks.append(
            _fail(
                "release.exact_head",
                "canonical repository and lowercase 40-character commit SHA are required",
            )
        )
    else:
        checks.append(_pass("release.exact_head"))

    if risk_class not in {"D0", "D1", "D2", "D3"}:
        checks.append(_fail("release.risk_class", "risk_class must be D0, D1, D2, or D3"))
    else:
        checks.append(_pass("release.risk_class"))

    if not originator_id:
        checks.append(_fail("originator", "originator_id is required"))
    else:
        checks.append(_pass("originator"))
        producer_ids.add(originator_id)
        actors["originator"] = originator_id

    stages = bundle.get("stages") if isinstance(bundle.get("stages"), dict) else {}
    for stage in EVIDENCE_STAGES:
        actor = _receipt_checks(
            checks,
            name=f"stage.{stage}",
            receipt=stages.get(stage),
            release_sha=release_sha,
            semantic_stage="evidence",
        )
        if actor:
            producer_ids.add(actor)

    security_actor = _receipt_checks(
        checks,
        name="penta_security",
        receipt=bundle.get("penta_security_decision"),
        release_sha=release_sha,
        semantic_stage="decision",
        decision_field="decision",
    )
    actors["penta_security"] = security_actor
    if security_actor and security_actor in producer_ids:
        checks.append(
            _fail(
                "penta_security.independence",
                "PentaSecurity decision actor must be independent of originator/build producers",
            )
        )
    elif security_actor:
        checks.append(_pass("penta_security.independence"))

    chlom = bundle.get("chlom_authority_rights_decision")
    chlom_actor = _receipt_checks(
        checks,
        name="chlom_authority_rights",
        receipt=chlom,
        release_sha=release_sha,
        semantic_stage="decision",
        decision_field="decision",
    )
    actors["chlom"] = chlom_actor
    if isinstance(chlom, dict):
        if chlom.get("rights_check") != "PASS" or chlom.get("authority_check") != "PASS":
            checks.append(
                _fail(
                    "chlom_authority_rights.scope",
                    "both rights_check and authority_check must PASS",
                )
            )
        else:
            checks.append(_pass("chlom_authority_rights.scope"))
        if chlom.get("authority_expansion") is not False:
            checks.append(
                _fail(
                    "chlom_authority_rights.authority_expansion",
                    "release evidence may not manufacture authority expansion",
                )
            )
        else:
            checks.append(_pass("chlom_authority_rights.authority_expansion"))
        if chlom.get("final_legal_or_rights_commitment") is not False:
            checks.append(
                _fail(
                    "chlom_authority_rights.final_commitment",
                    "final legal/rights commitments remain separately gated",
                )
            )
        else:
            checks.append(_pass("chlom_authority_rights.final_commitment"))
    if chlom_actor and chlom_actor in producer_ids:
        checks.append(
            _fail(
                "chlom_authority_rights.independence",
                "CHLOM authority/rights decision actor must be independent of the originator/build producers",
            )
        )
    elif chlom_actor:
        checks.append(_pass("chlom_authority_rights.independence"))

    cie = bundle.get("cie") if isinstance(bundle.get("cie"), dict) else {}
    cie_required = bool(cie.get("required"))
    cie_actor: str | None = None
    if cie_required:
        cie_actor = _receipt_checks(
            checks,
            name="cie",
            receipt=cie.get("decision"),
            release_sha=release_sha,
            semantic_stage="decision",
            decision_field="decision",
        )
        if cie_actor and cie_actor in producer_ids:
            checks.append(
                _fail(
                    "cie.independence",
                    "applicable CIE decision must be independent of originator/build producers",
                )
            )
        elif cie_actor:
            checks.append(_pass("cie.independence"))
    else:
        checks.append(_pass("cie.not_applicable"))
    actors["cie"] = cie_actor

    certifier = bundle.get("penta_certifier_receipt")
    certifier_actor = _receipt_checks(
        checks,
        name="penta_certifier",
        receipt=certifier,
        release_sha=release_sha,
        semantic_stage="decision",
        decision_field="decision",
    )
    actors["penta_certifier"] = certifier_actor
    prohibited_certifier_ids = set(producer_ids)
    prohibited_certifier_ids.update(x for x in (security_actor, chlom_actor, cie_actor) if x)
    if certifier_actor and certifier_actor in prohibited_certifier_ids:
        checks.append(
            _fail(
                "penta_certifier.independence",
                "PentaCertifier cannot be the originator, builder, PentaSecurity, CHLOM, or applicable CIE decision actor",
            )
        )
    elif certifier_actor:
        checks.append(_pass("penta_certifier.independence"))

    rollback = bundle.get("rollback") if isinstance(bundle.get("rollback"), dict) else {}
    rollback_ref = str(rollback.get("rollback_ref") or "")
    if not _HEX40.fullmatch(rollback_ref) or rollback.get("bounded") is not True:
        checks.append(_fail("rollback.boundary", "bounded rollback_ref commit SHA is required"))
    else:
        checks.append(_pass("rollback.boundary"))
    if rollback.get("tested") is not True or rollback.get("readback_verified") is not True:
        checks.append(
            _fail(
                "rollback.readback",
                "rollback test and exact readback evidence are required",
            )
        )
    else:
        checks.append(_pass("rollback.readback"))

    if risk_class == "D3":
        d3_bundle = bundle.get("d3_approval")
        if not isinstance(d3_bundle, dict):
            checks.append(
                _fail(
                    "d3.approval",
                    "D3 is human-reserved; exact current approval evidence is required",
                )
            )
        else:
            d3_result = evaluate_d3_approval(d3_bundle, now=now)
            if d3_result.get("decision") != "RELEASE_ELIGIBLE":
                checks.append(_fail("d3.approval", "D3 approval evaluator remains HOLD"))
            else:
                checks.append(_pass("d3.approval"))
            candidate = (
                d3_bundle.get("candidate")
                if isinstance(d3_bundle.get("candidate"), dict)
                else {}
            )
            if candidate.get("exact_version_ref") != release_sha:
                checks.append(
                    _fail(
                        "d3.exact_release",
                        "D3 candidate must bind the exact release commit",
                    )
                )
            else:
                checks.append(_pass("d3.exact_release"))
    else:
        checks.append(_pass("d3.not_applicable"))

    token_model = bundle.get("token_model")
    if token_model not in (None, {}, "UNRESOLVED"):
        checks.append(
            _fail(
                "token_model",
                "this verifier does not authorize or infer CHLOM token classes from DAIL semantic stages",
            )
        )
    else:
        checks.append(_pass("token_model"))

    return checks, actors


def verify(
    bundle: dict[str, Any],
    *,
    phase: str = "pre_release",
    now: datetime | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Verify the requested topology phase without collapsing pre/post-release authority."""
    if phase not in PHASES:
        raise ValueError(f"unsupported release verification phase: {phase}")

    checks, actors = _verify_pre_release(bundle, now=now)
    release = bundle.get("release") if isinstance(bundle.get("release"), dict) else {}
    release_sha = str(release.get("commit_sha") or "")
    execution = bundle.get("release_execution")

    if phase == "pre_release":
        if execution is not None:
            checks.append(
                _fail(
                    "release_execution.premature",
                    "pre-release eligibility must be decided before release execution exists",
                )
            )
        else:
            checks.append(_pass("release_execution.not_yet_executed"))
        decision = (
            "PRE_RELEASE_ELIGIBLE"
            if not any(item["status"] == "FAIL" for item in checks)
            else "RELEASE_HOLD"
        )
        return decision, checks

    execution_actor = _receipt_checks(
        checks,
        name="release_execution",
        receipt=execution,
        release_sha=release_sha,
        semantic_stage="execution",
        decision_field="state",
    )
    certifier_actor = actors.get("penta_certifier")
    originator_id = actors.get("originator")
    if execution_actor and certifier_actor and execution_actor == certifier_actor:
        checks.append(
            _fail(
                "release_execution.independence",
                "PentaCertifier cannot also execute the release",
            )
        )
    elif execution_actor:
        checks.append(_pass("release_execution.independence"))
    if execution_actor and originator_id and execution_actor == originator_id:
        checks.append(
            _fail(
                "release_execution.originator",
                "originator cannot execute its own final release in this topology",
            )
        )
    elif execution_actor:
        checks.append(_pass("release_execution.originator"))

    decision = (
        "POST_RELEASE_VERIFIED"
        if not any(item["status"] == "FAIL" for item in checks)
        else "RELEASE_HOLD"
    )
    return decision, checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="JSON release evidence bundle")
    parser.add_argument(
        "--phase",
        choices=PHASES,
        default="pre_release",
        help="verification point: pre-release eligibility or post-release outcome readback",
    )
    parser.add_argument("--report", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"RELEASE_HOLD: unable to read evidence bundle: {exc}", file=sys.stderr)
        return 2

    decision, checks = verify(bundle, phase=args.phase)
    report = {
        "decision": decision,
        "phase": args.phase,
        "release_commit": (bundle.get("release") or {}).get("commit_sha"),
        "checks": checks,
        "authority_created": False,
        "token_model_inferred": False,
    }
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    success_decision = (
        "PRE_RELEASE_ELIGIBLE" if args.phase == "pre_release" else "POST_RELEASE_VERIFIED"
    )
    return 0 if decision == success_decision else 1


if __name__ == "__main__":
    raise SystemExit(main())
