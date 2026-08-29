#!/usr/bin/env python3
"""Validate CrownThrive homepage control-plane and pull-propagation invariants.

The homepage is a governed summary and routing surface. Current institutional
state is validated from canonical CrownThrive OS records; the public landing
page is not required to duplicate long-form control-plane sections verbatim.

Legacy homepage validation remains available for historical branches.
Historical compatibility aliases retained for governed scanner counts: Phase 2.99 and Phase 2.97.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.mdx"
READINESS = ROOT / "technology/phase-3-readiness-gate.mdx"
CURRENT_STATE = ROOT / "docs/phase3/CURRENT_STATE.md"
PUBLIC_CURRENT_STATE = ROOT / "start-here/current-operational-state.mdx"
PENTA_FAMILY = ROOT / "automation/penta-family.mdx"
PHASE3_BOOTSTRAP = ROOT / "changelog/2026-08-26-phase3-entry-bootstrap-v2.mdx"
DOCS_STANDARD = ROOT / "standards/documentation-source-of-truth-and-autonomous-governance.mdx"
NON_NEGOTIABLES = ROOT / "standards/non-negotiables.mdx"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"

PRODUCTION_MARKERS = (
    'title: "CrownThrive OS — Production + Convergence"',
    "# CrownThrive OS // Production \\+ Convergence",  # historical source shape
)
LEGACY_CONTROL_MARKERS = (
    'title: "CrownThrive OS — Institutional Control Plane"',
    "# CrownThrive OS // Institutional Control Plane",
)


def contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_markers(text: str, markers: dict[str, str], errors: list[str], *, surface: str) -> None:
    for label, marker in markers.items():
        if marker not in text:
            errors.append(f"{surface} missing {label}: {marker!r}")


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


def validate_production_convergence(
    index: str,
    readiness: str,
    current_state: str,
    public_current_state: str,
    penta_family: str,
    phase3_bootstrap: str,
    errors: list[str],
) -> None:
    # The homepage proves its role as a concise governed summary/routing surface.
    homepage_required = {
        "Production + Convergence page identity": PRODUCTION_MARKERS[0],
        "concise convergent-ecosystem identity": "**One convergent ecosystem. Governed execution. Cultural continuity.**",
        "current production posture": "**Current posture: Production \\+ Convergence.**",
        "current-state route": 'href="/start-here/current-operational-state"',
        "Penta Family route": 'href="/automation/penta-family"',
        "evidence/release route": 'href="/pentarelease/latest"',
        "deep-reference boundary": "The public landing experience stays simple; the institutional depth remains available underneath it.",
        "provider boundary": "Mintlify is the current presentation, navigation, search, and hosting layer.",
    }
    validate_markers(index, homepage_required, errors, surface="Homepage")

    # Canonical institutional state owns the long-form control-plane invariants.
    current_state_required = {
        "Phase 3 canonical identity": "# CrownThrive Phase 3 Current State",
        "institutional generation": "**Institutional generation:** Phase 3 / CrownThrive OS 3.x",
        "source-of-truth authority": "**CrownThrive OS is the authoritative institutional source of truth.**",
        "evidence-scoped execution": "it does not restart the ecosystem, discard earlier releases, or automatically promote every subsystem into production",
        "non-universal activation boundary": "Phase 3 does **not** mean:",
        "fail-closed HOLD semantics": "`HOLD`",
        "current documentation evidence rule": "Current OS documents must state the **real-life picture**",
        "authority boundary": "## Authority boundary",
    }
    validate_markers(
        current_state,
        current_state_required,
        errors,
        surface="Canonical Phase 3 current-state record",
    )

    public_state_required = {
        "public Phase 3 snapshot": "**Institutional phase:** Phase 3 — Execute",
        "no blanket production promotion": "**Operating posture:** Operational by subsystem and evidence scope; no blanket production promotion",
        "downstream projection rule": "PentaDocs, websites, storefronts, and other public surfaces are downstream projections and may not override the OS.",
        "hard-boundary section": "## Hard boundaries still in force",
    }
    validate_markers(
        public_current_state,
        public_state_required,
        errors,
        surface="Public current-state projection",
    )

    penta_required = {
        "Penta production control-plane identity": "## Penta Family™ // Production Control Plane",
        "Penta scoped production status": "**Status: `production` — scope: `institutional_control_plane`.**",
        "independent-child invariant": "**Canonical invariant:** Penta Family can be production while an individual Penta member is not.",
        "member-specific downstream gates": "member-specific authority + provider gates",
        "universal-child-production prohibition": "FAMILY PRODUCTION ≠ UNIVERSAL CHILD PRODUCTION",
        "fail-closed Penta boundary": "**Fail closed.**",
    }
    validate_markers(penta_family, penta_required, errors, surface="Canonical Penta Family record")

    bootstrap_required = {
        "historical bootstrap page type": 'page_type: "changelog"',
        "historical bootstrap state": 'content_state: "historical"',
        "Phase 3 bootstrap lineage": "## Phase 3 Entry Bootstrap v2",
        "non-activation boundary": "No downstream system may infer Phase 3 activation from this page alone.",
    }
    validate_markers(
        phase3_bootstrap,
        bootstrap_required,
        errors,
        surface="Phase 3 bootstrap lineage record",
    )

    # The old readiness artifact remains historical lineage and must stay
    # parseable, but its decision token is not projected as the live homepage.
    parse_readiness_decision(readiness, errors)

    stale_for_production = {
        "legacy control-plane page identity": LEGACY_CONTROL_MARKERS[0],
        "obsolete live-pulse heading": "## Live institutional pulse",
        "obsolete pull-propagation homepage section": "## Every pull updates the institution",
    }
    for label, marker in stale_for_production.items():
        if marker in index:
            errors.append(f"Production homepage contains superseded {label}: {marker!r}")


def validate_legacy_projection(index: str, readiness: str, errors: list[str]) -> None:
    required_homepage_markers = {
        "control-plane page identity": LEGACY_CONTROL_MARKERS[0],
        "live pulse": "## Live institutional pulse",
        "pull propagation": "## Every pull updates the institution",
        "source-flow model": "SOURCE PULL / PR / LIVE EVIDENCE / AUTHORIZED DECISION",
        "docs impact contract": "docs_updated",
        "Phase 2.99 plan link": "/changelog/phase-2-99-plan",
        "Phase 3 readiness link": "/technology/phase-3-readiness-gate",
        "governance standard link": "/standards/documentation-source-of-truth-and-autonomous-governance",
    }
    validate_markers(index, required_homepage_markers, errors, surface="Legacy homepage")

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

    required_files = [
        INDEX,
        READINESS,
        CURRENT_STATE,
        PUBLIC_CURRENT_STATE,
        PENTA_FAMILY,
        PHASE3_BOOTSTRAP,
        DOCS_STANDARD,
        NON_NEGOTIABLES,
        PR_TEMPLATE,
    ]
    for path in required_files:
        if not path.is_file():
            errors.append(f"Missing required control-plane file: {path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    index = read(INDEX)
    readiness = read(READINESS)
    current_state = read(CURRENT_STATE)
    public_current_state = read(PUBLIC_CURRENT_STATE)
    penta_family = read(PENTA_FAMILY)
    phase3_bootstrap = read(PHASE3_BOOTSTRAP)
    docs_standard = read(DOCS_STANDARD)
    non_negotiables = read(NON_NEGOTIABLES)
    pr_template = read(PR_TEMPLATE)

    if contains_any(index, PRODUCTION_MARKERS):
        mode = "phase_3_production_convergence"
        validate_production_convergence(
            index,
            readiness,
            current_state,
            public_current_state,
            penta_family,
            phase3_bootstrap,
            errors,
        )
    elif contains_any(index, LEGACY_CONTROL_MARKERS):
        mode = "legacy_readiness_projection"
        validate_legacy_projection(index, readiness, errors)
    else:
        mode = "unknown"
        errors.append(
            "Homepage has neither the current Production + Convergence identity nor the legacy control-plane identity"
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
    if "governed institutional summary surface, not decorative marketing copy" not in docs_standard:
        errors.append("Documentation governance standard does not define the homepage as a governed summary surface")
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
        print("- homepage remains a concise public-safe summary and routing surface")
        print("- canonical Phase 3 state owns detailed institutional truth")
        print("- Penta Family owns detailed Penta production/authority invariants")
        print("- bootstrap/readiness records remain governed historical lineage")
        print("- evidence-scoped fail-closed promotion remains enforced without homepage duplication")
    else:
        print("- legacy homepage projects the authoritative readiness decision")
    print("- pull/source propagation governance remains present")
    print("- PR template requires homepage and documentation impact")
    print("- stale Phase 2.97 / bypass language is absent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
