#!/usr/bin/env python3
"""Validate CrownThrive homepage governance and pull-propagation invariants.

The homepage has two recognized generations:
1. the historical Phase 3-entry/readiness projection; and
2. the current Phase 3 Production + Convergence projection.

The current projection must not be forced to reproduce retired Phase 2.99/NO-GO
state merely because historical readiness evidence remains preserved in the repo.
This validator is standard-library only and fails closed on mixed/stale posture.
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
LEGACY_H1 = "# CrownThrive OS // Institutional Control Plane"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require_markers(errors: list[str], body: str, markers: dict[str, str], surface: str) -> None:
    for label, marker in markers.items():
        if marker not in body:
            errors.append(f"{surface} missing {label}: {marker!r}")


def validate_legacy_readiness_projection(errors: list[str], index: str, readiness: str) -> None:
    decision_match = re.search(
        r"\*\*Current decision:\s*(.+?)\*\*",
        readiness,
        flags=re.DOTALL,
    )
    if not decision_match:
        errors.append("Phase 3 readiness gate does not expose a parseable current decision")
        return

    decision_text = decision_match.group(1).strip()
    state_tokens = re.findall(r"`([^`]+)`", decision_text)
    if state_tokens:
        for token in state_tokens:
            if token not in index:
                errors.append(
                    "Legacy homepage control state is stale: readiness gate decision token "
                    f"{token!r} is not projected on index.mdx"
                )
    else:
        decision_keyword = "PASS" if "PASS" in decision_text.upper() else "NO-GO"
        if decision_keyword not in index.upper():
            errors.append(
                "Legacy homepage control state does not reflect readiness-gate decision "
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

    production_convergence = PRODUCTION_H1 in index
    legacy_control_plane = LEGACY_H1 in index

    if production_convergence and legacy_control_plane:
        errors.append("Homepage mixes current Production + Convergence and legacy control-plane H1 generations")

    if production_convergence:
        required_homepage_markers = {
            "Production + Convergence H1": PRODUCTION_H1,
            "production/convergence explanation": "## What “Production \\+ Convergence” means",
            "Penta operating model": "## The Penta Model",
            "bounded authority model": "## Authority model: autonomy without authority manufacture",
            "current institutional pulse": "## Current institutional pulse",
            "production posture token": "operating_posture: production_and_convergence",
            "Phase 3 production baseline token": "institutional_phase: phase_3_production_baseline",
        }
        require_markers(errors, index, required_homepage_markers, "Homepage")

        current_posture_markers = [
            "old homepage posture",
            "superseded",
            "Production \\+ Convergence",
            "Production does not mean universal activation",
        ]
        for marker in current_posture_markers:
            if marker not in index:
                errors.append(f"Homepage lacks Production + Convergence boundary marker: {marker!r}")

        forbidden_current_markers = {
            "retired control-plane H1": LEGACY_H1,
            "retired Phase 2.99 blocked token": "blocked_pending_phase_2_99_hard_exit",
            "obsolete Phase 2.97 landing state": "**Current maturity:** Phase 2.97.1",
            "obsolete Phase 3 bypass language": "Phase 3 no longer needs to wait",
        }
        for label, marker in forbidden_current_markers.items():
            if marker in index:
                errors.append(f"Homepage contains {label}: {marker!r}")

        # Historical readiness evidence remains valid as archive/evidence, but it is
        # no longer the homepage's current-state projection authority after the
        # explicit Production + Convergence supersession. Do not require its old
        # decision token or Phase 2.99 links to be repeated on the current homepage.
    elif legacy_control_plane:
        required_homepage_markers = {
            "control-plane H1": LEGACY_H1,
            "live pulse": "## Live institutional pulse",
            "pull propagation": "## Every pull updates the institution",
            "source-flow model": "SOURCE PULL / PR / LIVE EVIDENCE / AUTHORIZED DECISION",
            "docs impact contract": "docs_updated",
            "Phase 2.99 plan link": "/changelog/phase-2-99-plan",
            "Phase 3 readiness link": "/technology/phase-3-readiness-gate",
            "governance standard link": "/standards/documentation-source-of-truth-and-autonomous-governance",
        }
        require_markers(errors, index, required_homepage_markers, "Homepage")
        validate_legacy_readiness_projection(errors, index, readiness)
    else:
        errors.append(
            "Homepage has no recognized governed generation: expected current Production + Convergence "
            "or legacy Institutional Control Plane H1"
        )

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
        print(f"FAILED with {len(errors)} homepage/governance invariant error(s).")
        return 1

    posture = "production_and_convergence" if production_convergence else "legacy_readiness_projection"
    print("CrownThrive homepage governance validation PASSED")
    print(f"- homepage posture: {posture}")
    if production_convergence:
        print("- retired Phase 2.99/readiness decision tokens are preserved as evidence, not required as current homepage state")
    else:
        print("- homepage projects the authoritative readiness decision")
    print("- pull/source propagation governance remains present")
    print("- PR template still requires homepage and documentation impact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
