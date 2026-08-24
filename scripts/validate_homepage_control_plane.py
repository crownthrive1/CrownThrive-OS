#!/usr/bin/env python3
"""Validate CrownThrive homepage control-plane and pull-propagation invariants.

This validator is intentionally standard-library only. It keeps the public-safe
homepage synchronized with the authoritative Phase 3 readiness decision and
requires the governance standard / PR template to treat homepage propagation as
part of every material change.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.mdx"
READINESS = ROOT / "technology/phase-3-readiness-gate.mdx"
DOCS_STANDARD = ROOT / "standards/documentation-source-of-truth-and-autonomous-governance.mdx"
NON_NEGOTIABLES = ROOT / "standards/non-negotiables.mdx"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"
MANIFEST = ROOT / "developers/manifests/homepage-projection.v2.json"
MINTLIFY_REGISTRY = ROOT / "platforms/mintlify-documentation-service-registry.mdx"
README = ROOT / "README.md"
SOURCE_REGISTER = ROOT / "knowledge/source-register.mdx"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    required_files = [
        INDEX,
        READINESS,
        DOCS_STANDARD,
        NON_NEGOTIABLES,
        PR_TEMPLATE,
        MANIFEST,
        MINTLIFY_REGISTRY,
        README,
        SOURCE_REGISTER,
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
    docs_standard = read(DOCS_STANDARD)
    non_negotiables = read(NON_NEGOTIABLES)
    pr_template = read(PR_TEMPLATE)
    mintlify_registry = read(MINTLIFY_REGISTRY)
    readme = read(README)
    source_register = read(SOURCE_REGISTER)

    manifest: dict = {}
    try:
        manifest = json.loads(read(MANIFEST))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"Homepage projection manifest is not readable JSON: {exc}")

    expected_endpoint = "https://crown-thrive.mintlify.site/index"
    expected_projection = {
        "current_default_endpoint": expected_endpoint,
        "current_default_host": "crown-thrive.mintlify.site",
        "entry_path": "/index",
        "readback_state": "verified_rendered_readback",
        "custom_domain_target": "docs.crownthrive.io",
        "custom_domain_state": "governed_deferred",
        "legacy_host_state": "superseded_for_default_readback",
        "readback_scope": "anonymous_rendered_page",
        "indexing_state": "unverified",
    }
    projection = manifest.get("public_projection", {})
    for field, expected in expected_projection.items():
        actual = projection.get(field)
        if actual != expected:
            errors.append(
                "Homepage projection manifest has stale Mintlify endpoint field "
                f"{field!r}: expected {expected!r}, found {actual!r}"
            )
    if projection.get("root_also_rendered") is not True:
        errors.append("Homepage projection manifest must record the rendered provider root")
    if projection.get("source_acceptance_separate") is not True:
        errors.append("Mintlify reachability must remain separate from source acceptance")
    for label, source in {
        "Mintlify service registry": mintlify_registry,
        "documentation governance standard": docs_standard,
        "repository README": readme,
        "institutional source register": source_register,
    }.items():
        if expected_endpoint not in source:
            errors.append(f"{label} does not project the current default Mintlify endpoint")

    required_homepage_markers = {
        "control-plane H1": "# CrownThrive OS // Institutional Control Plane",
        "live pulse": "## Live institutional pulse",
        "pull propagation": "## Every pull updates the institution",
        "source-flow model": "SOURCE PULL / PR / LIVE EVIDENCE / AUTHORIZED DECISION",
        "docs impact contract": "docs_updated",
        "Phase 2.99 plan link": "/changelog/phase-2-99-plan",
        "Phase 3 readiness link": "/technology/phase-3-readiness-gate",
        "governance standard link": "/standards/documentation-source-of-truth-and-autonomous-governance",
    }
    for label, marker in required_homepage_markers.items():
        if marker not in index:
            errors.append(f"Homepage missing {label}: {marker!r}")

    forbidden_stale_homepage_markers = {
        "obsolete Phase 2.97 landing state": "**Current maturity:** Phase 2.97.1",
        "obsolete Phase 3 bypass language": "Phase 3 no longer needs to wait",
    }
    for label, marker in forbidden_stale_homepage_markers.items():
        if marker in index:
            errors.append(f"Homepage contains {label}: {marker!r}")

    decision_match = re.search(
        r"\*\*Current decision:\s*(.+?)\*\*",
        readiness,
        flags=re.DOTALL,
    )
    if not decision_match:
        errors.append("Phase 3 readiness gate does not expose a parseable current decision")
    else:
        decision_text = decision_match.group(1).strip()
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
    print("- homepage projects the authoritative readiness decision")
    print("- pull/source propagation rules are present")
    print("- PR template requires homepage and documentation impact")
    print("- stale Phase 2.97 / Phase 3 bypass language is absent")
    print("- default Mintlify public endpoint is manifest-bound and institutionally projected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
