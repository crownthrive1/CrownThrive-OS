#!/usr/bin/env python3
"""Validate CrownThrive homepage control-plane and pull-propagation invariants.

This validator is intentionally standard-library only. It supports the current
Phase 3 Production + Convergence homepage while preserving validation of the
older readiness-projection shape for historical branches.

A current production homepage must not be forced to re-project a superseded
Phase 2.99/Phase 3-entry token. Instead it must explicitly declare the Phase 3
production baseline, evidence-scoped promotion, and the fact that the old
blanket NO-GO homepage posture is superseded.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.mdx"
READINESS = ROOT / "technology/phase-3-readiness-gate.mdx"
DOCS_STANDARD = ROOT / "standards/documentation-source-of-truth-and-autonomous-governance.mdx"
NON_NEGOTIABLES = ROOT / "standards/non-negotiables.mdx"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"

PRODUCTION_H1 = "# CrownThrive OS // Production \\+ Convergence"
LEGACY_CONTROL_H1 = "# CrownThrive OS // Institutional Control Plane"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_markers(index: str, markers: dict[str, str], errors: list[str]) -> None:
    for label, marker in markers.items():
        if marker not in index:
            errors.append(f"Homepage missing {label}: {marker!r}")


def parse_readiness_decision(readiness: str, errors: list[str]) -> str | None:
    decision_match = re.search(
        r"\*\*Current decision:\s*(.+?)\*\*",
        readiness,
        flags=re.DOTALL,
    )
    if not decision_match:
        errors.append("Phase 3 readiness gate does not expose a parseable current decision")
        return None
    return decision_match.group(1).strip()


def validate_production_convergence(index: str, readiness: str, errors: list[str]) -> None:
    required = {
        "Production + Convergence H1": PRODUCTION_H1,
        "current production posture": "CURRENT OPERATING STATE — PRODUCTION \\+ CONVERGENCE.",
        "Penta operating model": "## The Penta Model",
        "institutional pulse": "## Current institutional pulse",
        "Phase 3 production baseline": "institutional_phase: phase_3_production_baseline",
        "evidence-scoped status promotion": "status_promotion_rule: evidence_scoped_fail_closed",
        "universal-activation warning": "**Production does not mean universal activation.**",
        "Phase 3 bootstrap lineage": "/changelog/2026-08-26-phase3-entry-bootstrap-v2",
        "superseded readiness posture": "old homepage posture that presented Phase 2.99 as the active state and Phase 3 as a blanket `NO-GO` is superseded",
        "evidence-over-appearance section": "## Evidence over appearance",
    }
    validate_markers(index, required, errors)

    # The old readiness artifact remains historical lineage and must stay
    # parseable, but its old decision token is deliberately not projected as
    # the live homepage state after Phase 3 production activation.
    parse_readiness_decision(readiness, errors)

    stale_for_production = {
        "legacy control-plane H1": LEGACY_CONTROL_H1,
        "obsolete live-pulse heading": "## Live institutional pulse",
        "obsolete pull-propagation homepage section": "## Every pull updates the institution",
    }
    for label, marker in stale_for_production.items():
        if marker in index:
            errors.append(f"Production homepage contains superseded {label}: {marker!r}")


def validate_legacy_projection(index: str, readiness: str, errors: list[str]) -> None:
    required_homepage_markers = {
        "control-plane H1": LEGACY_CONTROL_H1,
        "live pulse": "## Live institutional pulse",
        "pull propagation": "## Every pull updates the institution",
        "source-flow model": "SOURCE PULL / PR / LIVE EVIDENCE / AUTHORIZED DECISION",
        "docs impact contract": "docs_updated",
        "Phase 2.99 plan link": "/changelog/phase-2-99-plan",
        "Phase 3 readiness link": "/technology/phase-3-readiness-gate",
        "governance standard link": "/standards/documentation-source-of-truth-and-autonomous-governance",
    }
    validate_markers(index, required_homepage_markers, errors)

    decision_text = parse_readiness_decision(readiness, errors)
    if decision_text is None:
        return

    state_tokens = re.findall(r"`([^`]+)`", decision_text)
    if state_tokens:
        for token in state_tokens:
            if token not in index:
                errors.append(
                    "Homepage control state is stale: readiness gate decision token "
                    f"{token!r} is not projected on index.mdx"
                )
    else:
        decision_keyword = "PASS" if "PASS" in decision_text.upper() else "NO-GO"
        if decision_keyword not in index.upper():
            errors.append(
                "Homepage control state does not reflect readiness-gate decision "
                f"{decision_keyword!r}"
            )


def main() -> int:
    errors: list[str] = []

    required_files = [INDEX, READINESS, DOCS_STANDARD, NON_NEGOTIABLES, PR_TEMPLATE]
    for path in required_files:
        if not path.is_file():
            errors.append(f"Missing required control-plane file: {path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    index = read(INDEX)
    readiness = read(READINESS)
    docs_standard = read(DOCS_STANDARD)
    non_negotiables = read(NON_NEGOTIABLES)
    pr_template = read(PR_TEMPLATE)

    if PRODUCTION_H1 in index:
        mode = "phase_3_production_convergence"
        validate_production_convergence(index, readiness, errors)
    elif LEGACY_CONTROL_H1 in index:
        mode = "legacy_readiness_projection"
        validate_legacy_projection(index, readiness, errors)
    else:
        mode = "unknown"
        errors.append(
            "Homepage has neither the current Production + Convergence H1 nor the legacy control-plane H1"
        )

    forbidden_stale_homepage_markers = {
        "obsolete Phase 2.97 landing state": "**Current maturity:** Phase 2.97.1",
        "obsolete Phase 3 bypass language": "Phase 3 no longer needs to wait",
    }
    for label, marker in forbidden_stale_homepage_markers.items():
        if marker in index:
            errors.append(f"Homepage contains {label}: {marker!r}")

    if "## Homepage control-plane projection rule" not in docs_standard:
        errors.append("Documentation governance standard lacks homepage projection rule")
    if "## Pull-driven source propagation rule" not in docs_standard:
        errors.append("Documentation governance standard lacks pull-driven propagation rule")
    if "## 30. The homepage is a governed control surface" not in non_negotiables:
        errors.append("Non-negotiables lack governed-homepage rule")
    if "## 31. Pull requests propagate institutional meaning" not in non_negotiables:
        errors.append("Non-negotiables lack cross-record PR propagation rule")

    required_pr_fields = [
        "### Homepage, propagation, and control-plane state",
        "Homepage impact: `updated | no_change | delta_opened`",
        "Documentation impact: `docs_updated | docs_no_change | docs_delta_opened`",
        "Homepage control-state invariant passes",
    ]
    for marker in required_pr_fields:
        if marker not in pr_template:
            errors.append(f"Pull request template missing control-plane field: {marker!r}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"FAILED with {len(errors)} homepage/control-plane invariant error(s).")
        return 1

    print("CrownThrive homepage control-plane validation PASSED")
    print(f"- homepage mode: {mode}")
    if mode == "phase_3_production_convergence":
        print("- current homepage declares Phase 3 Production + Convergence")
        print("- legacy readiness decision remains historical lineage, not live homepage state")
        print("- evidence-scoped fail-closed promotion remains explicit")
    else:
        print("- legacy homepage projects the authoritative readiness decision")
    print("- pull/source propagation governance remains present")
    print("- PR template requires homepage and documentation impact")
    print("- stale Phase 2.97 / bypass language is absent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
