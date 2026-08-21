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
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.mdx"
READINESS = ROOT / "technology/phase-3-readiness-gate.mdx"
DOCS_STANDARD = ROOT / "standards/documentation-source-of-truth-and-autonomous-governance.mdx"
NON_NEGOTIABLES = ROOT / "standards/non-negotiables.mdx"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"
PROJECTION_MANIFEST = ROOT / "developers/manifests/homepage-projection.v1.json"
PROJECTION_RENDERER = ROOT / "scripts/render_homepage_projection.py"
PROJECTION_STANDARD = ROOT / "standards/dynamic-homepage-projection-standard.mdx"
PROJECTION_WORKFLOW = ROOT / ".github/workflows/hourly-homepage-projection.yml"
PLATFORM_MANIFEST = ROOT / "developers/manifests/ecosystem-platform-placement.v1.json"
PLATFORM_ATLAS = ROOT / "platforms/ecosystem-platform-placement-and-lineage-atlas.mdx"
TOOLING_MANIFEST = ROOT / "developers/manifests/monetizable-tooling-coordination.v1.json"
TOOLING_PAGE = ROOT / "developers/monetizable-tooling-coordination-and-release-gate.mdx"
AI_CHLOM_MAP = ROOT / "technology/ai-ml-chlom-protected-capability-and-vault-map.mdx"


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
        PROJECTION_MANIFEST,
        PROJECTION_RENDERER,
        PROJECTION_STANDARD,
        PROJECTION_WORKFLOW,
        PLATFORM_MANIFEST,
        PLATFORM_ATLAS,
        TOOLING_MANIFEST,
        TOOLING_PAGE,
        AI_CHLOM_MAP,
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
    projection_standard = read(PROJECTION_STANDARD)
    projection_workflow = read(PROJECTION_WORKFLOW)
    platform_atlas = read(PLATFORM_ATLAS)
    tooling_page = read(TOOLING_PAGE)
    ai_chlom_map = read(AI_CHLOM_MAP)

    try:
        projection_manifest = json.loads(read(PROJECTION_MANIFEST))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"Homepage projection manifest is invalid: {exc}")
        projection_manifest = {}

    try:
        platform_manifest = json.loads(read(PLATFORM_MANIFEST))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"Platform-placement manifest is invalid: {exc}")
        platform_manifest = {}

    try:
        tooling_manifest = json.loads(read(TOOLING_MANIFEST))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"Monetizable-tooling manifest is invalid: {exc}")
        tooling_manifest = {}

    required_homepage_markers = {
        "control-plane H1": "# CrownThrive OS // Institutional Control Plane",
        "live pulse": "## Live institutional pulse",
        "pull propagation": "## Every pull updates the institution",
        "source-flow model": "SOURCE PULL / PR / LIVE EVIDENCE / AUTHORIZED DECISION",
        "docs impact contract": "docs_updated",
        "Phase 2.99 plan link": "/changelog/phase-2-99-plan",
        "Phase 3 readiness link": "/technology/phase-3-readiness-gate",
        "governance standard link": "/standards/documentation-source-of-truth-and-autonomous-governance",
        "dynamic projection start": "<!-- HOMEPAGE_PROJECTION:START -->",
        "dynamic projection end": "<!-- HOMEPAGE_PROJECTION:END -->",
        "projection input digest": "projection_input_sha256:",
        "public-readback boundary": "PUBLIC READBACK BLOCKED",
    }
    for label, marker in required_homepage_markers.items():
        if marker not in index:
            errors.append(f"Homepage missing {label}: {marker!r}")

    for marker in ("<!-- HOMEPAGE_PROJECTION:START -->", "<!-- HOMEPAGE_PROJECTION:END -->"):
        if index.count(marker) != 1:
            errors.append(f"Homepage must contain exactly one projection marker: {marker!r}")

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
    if "# Dynamic Homepage Projection Standard" not in projection_standard:
        errors.append("Dynamic homepage projection standard lacks its canonical H1")
    if "# Ecosystem Platform Placement and Lineage Atlas" not in platform_atlas:
        errors.append("Platform-placement atlas lacks its canonical H1")
    if "# Monetizable tooling coordination and release gate" not in tooling_page:
        errors.append("Monetizable-tooling page lacks its canonical H1")
    if "# AI, ML, CHLOM Protected Capability and Vault Map" not in ai_chlom_map:
        errors.append("AI/ML/CHLOM protected map lacks its canonical H1")
    for marker in ("Candidate / HOLD", "proprietary", "Cryptographic"):
        if marker not in ai_chlom_map:
            errors.append(f"AI/ML/CHLOM map missing protected-boundary marker: {marker!r}")
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

    if projection_manifest:
        if projection_manifest.get("classification") != "public":
            errors.append("Homepage projection manifest must remain public")
        if projection_manifest.get("target_path") != "index.mdx":
            errors.append("Homepage projection manifest target must be index.mdx")
        automation = projection_manifest.get("automation", {})
        if automation.get("cadence") != "hourly":
            errors.append("Homepage projection cadence must remain hourly")
        if automation.get("direct_main_write") is not False:
            errors.append("Homepage projection must prohibit direct main writes")
        if automation.get("self_merge") is not False:
            errors.append("Homepage projection must prohibit self-merge")
        commerce = projection_manifest.get("commerce_state", {})
        if commerce.get("checkout_enabled") is not False:
            errors.append("Homepage projection must not activate checkout")
        if commerce.get("candidate_tool_count") != 6:
            errors.append("Homepage projection must preserve the six candidate tooling records")
        if commerce.get("baseline_minimum_credits") != 400:
            errors.append("Homepage projection must preserve the 400-credit candidate floor")
        for relative in projection_manifest.get("tracked_inputs", []):
            if not (ROOT / relative).is_file():
                errors.append(f"Homepage projection tracked input is missing: {relative}")

    if platform_manifest:
        cards = platform_manifest.get("cards", [])
        ordinals = [card.get("ordinal") for card in cards]
        card_ids = [card.get("card_id") for card in cards]
        slugs = [card.get("slug") for card in cards]
        markers = [card.get("observed_card_marker") for card in cards]
        type_total = sum(platform_manifest.get("counts_by_type", {}).values())
        if platform_manifest.get("classification") != "public":
            errors.append("Platform-placement manifest must remain public")
        if len(cards) != 90 or ordinals != list(range(1, 91)):
            errors.append("Platform-placement manifest must contain ordered card ordinals 1..90")
        if len(card_ids) != len(set(card_ids)) or len(slugs) != len(set(slugs)):
            errors.append("Platform-placement card IDs and slugs must be unique")
        if markers.count("unmarked") != 80 or markers.count("archived") != 10:
            errors.append("Platform-placement manifest must preserve 80 unmarked and 10 archived cards")
        if type_total != 90:
            errors.append("Platform-placement typed totals must reconcile to 90")
        if platform_manifest.get("source", {}).get("url") != "https://crownthrive.com/":
            errors.append("Platform-placement manifest source URL is not canonical")

    if tooling_manifest:
        tools = tooling_manifest.get("candidate_tools", [])
        tool_ids = [tool.get("tool_id") for tool in tools]
        live_state = tooling_manifest.get("live_object_state", {})
        live_true = [key for key, value in live_state.items() if value is True]
        dependency_prs = {
            item.get("number")
            for item in tooling_manifest.get("collision_and_lineage_dependencies", {}).get(
                "pull_requests", []
            )
        }
        if tooling_manifest.get("status") != "candidate_hold":
            errors.append("Monetizable-tooling manifest must remain candidate_hold")
        if tooling_manifest.get("authority") != "A1_prepare":
            errors.append("Monetizable-tooling authority must remain A1_prepare")
        if len(tools) != 6 or len(tool_ids) != len(set(tool_ids)):
            errors.append("Monetizable-tooling manifest must contain six unique stable tool IDs")
        if tooling_manifest.get("commerce", {}).get("baseline_minimum_credits") != 400:
            errors.append("Monetizable-tooling candidate baseline must remain 400 credits")
        if tooling_manifest.get("commerce", {}).get("price_records_included") is not False:
            errors.append("Monetizable-tooling manifest must not contain price records")
        if tooling_manifest.get("stripe", {}).get("state") != "GOVERNED_HOLD":
            errors.append("Monetizable-tooling Stripe state must remain GOVERNED_HOLD")
        if live_true:
            errors.append(
                "Monetizable-tooling manifest cannot activate live objects: "
                + ", ".join(sorted(live_true))
            )
        if dependency_prs != {133, 180, 189}:
            errors.append("Monetizable-tooling collision set must preserve PRs 133, 180 and 189")

    required_workflow_markers = [
        'cron: "17 * * * *"',
        "contents: write",
        "pull-requests: write",
        'canonical_sha="$(git rev-parse origin/main)"',
        'if [ "$canonical_sha" != "$GITHUB_SHA" ]',
        "git restore -- index.mdx",
        'preexisting_paths="$(git diff --name-only',
        "registered bot lineage",
        'pr_paths="$(git diff --name-only origin/main...HEAD)"',
        'if [ "$pr_paths" != "index.mdx" ]',
        "rollback_digest=",
        "provider does not report main as protected",
        "branch read-after-write head mismatch",
        "pull-request read-after-write head mismatch",
        'readback_paths="$(gh api --paginate',
        "git push origin \"HEAD:$CT_BRANCH\"",
        "gh pr create",
        "--draft",
    ]
    for marker in required_workflow_markers:
        if marker not in projection_workflow:
            errors.append(f"Hourly homepage workflow missing fail-closed control: {marker!r}")

    forbidden_workflow_markers = [
        "id-token: write",
        "git push origin main",
        "git push --force",
        "git push -f",
        "gh pr merge",
    ]
    for marker in forbidden_workflow_markers:
        if marker in projection_workflow:
            errors.append(f"Hourly homepage workflow contains prohibited operation: {marker!r}")

    render_check = subprocess.run(
        [sys.executable, str(PROJECTION_RENDERER), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if render_check.returncode != 0:
        detail = (render_check.stdout + render_check.stderr).strip()
        errors.append(f"Homepage projection render check failed: {detail}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"FAILED with {len(errors)} homepage/control-plane invariant error(s).")
        return 1

    print("CrownThrive homepage control-plane validation PASSED")
    print("- homepage projects the authoritative readiness decision")
    print("- pull/source propagation rules are present")
    print("- PR template requires homepage and documentation impact")
    print("- deterministic hourly projection and draft-PR controls are valid")
    print("- stale Phase 2.97 / Phase 3 bypass language is absent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
