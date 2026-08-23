#!/usr/bin/env python3
"""Render the bounded CrownThrive homepage control-state projection.

The renderer deliberately separates source acceptance from Mintlify/public
projection availability. It never writes directly to main and never treats a
login-gated, unindexed, custom-domain-pending, or temporarily unavailable docs
projection as a standalone reason to hold an otherwise governance-eligible
source candidate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/homepage-projection.v2.json"
START = "{/*  HOMEPAGE_PROJECTION:START  */}"
END = "{/*  HOMEPAGE_PROJECTION:END  */}"


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser.parse_args()


def load_manifest() -> dict:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("manifest_version") != "2.0.0":
        raise ValueError("homepage manifest must be version 2.0.0")
    if data.get("classification") != "public":
        raise ValueError("homepage projection must remain public-safe")
    if data.get("target_path") != "index.mdx":
        raise ValueError("homepage projection target must remain index.mdx")
    automation = data.get("automation", {})
    if automation.get("direct_main_write") is not False:
        raise ValueError("homepage renderer may not authorize direct main writes")
    if automation.get("candidate_diff_invariant") != "index.mdx_only":
        raise ValueError("homepage candidate must remain index.mdx-only")
    if automation.get("mintlify_public_access_is_merge_blocker") is not False:
        raise ValueError("Mintlify public accessibility cannot be a standalone source-merge blocker")
    if data.get("governance", {}).get("projection_availability") != "separate_state_dimension":
        raise ValueError("projection availability must remain a separate state dimension")
    return data


def current_gate(readiness: str) -> str:
    match = re.search(r"\*\*Current decision:\s*(.+?)\*\*", readiness, flags=re.DOTALL)
    if match:
        tokens = re.findall(r"`([^`]+)`", match.group(1))
        if tokens:
            return tokens[0]
        text = match.group(1).strip()
        if "PASS" in text.upper():
            return "PASS"
        if "NO-GO" in text.upper():
            return "NO-GO"
    match = re.search(r"\*\*Current Phase 3 entry state:\*\*\s*`([^`]+)`", readiness)
    if match:
        return match.group(1)
    raise ValueError("unable to resolve Phase 3 entry state from readiness gate")


def render(manifest: dict) -> str:
    readiness_path = ROOT / manifest["phase_gate_path"]
    gate = current_gate(readiness_path.read_text(encoding="utf-8"))
    automation = manifest["automation"]
    governance = manifest["governance"]
    return "\n".join(
        [
            START,
            "",
            "## Governed automated projection",
            "",
            "This bounded region is generated from the current readiness gate and the homepage projection policy. Hourly no-op runs are heartbeats and do not churn documentation.",
            "",
            "```yaml",
            f"projection_version: {manifest['manifest_version']}",
            f"phase_3_entry: {gate}",
            f"source_acceptance: {governance['source_acceptance']}",
            f"projection_availability: {governance['projection_availability']}",
            f"mintlify_public_access_is_merge_blocker: {str(automation['mintlify_public_access_is_merge_blocker']).lower()}",
            f"custom_domain_is_merge_blocker: {str(automation['custom_domain_is_merge_blocker']).lower()}",
            f"indexing_is_merge_blocker: {str(automation['indexing_is_merge_blocker']).lower()}",
            f"projection_claims_require_separate_evidence: {str(automation['projection_claims_require_separate_evidence']).lower()}",
            f"homepage_refresh: {automation['cadence']}_on_change",
            f"candidate_diff: {automation['candidate_diff_invariant']}",
            f"automatic_promotion: {automation['automatic_promotion']}",
            f"direct_main_write: {str(automation['direct_main_write']).lower()}",
            "```",
            "",
            "<Note>",
            "  Source acceptance and documentation reachability are independent. A login-gated or temporarily unavailable Mintlify projection can block a public-deployment or indexing claim, but it cannot by itself manufacture a source-governance HOLD after the exact-head required gates pass.",
            "</Note>",
            "",
            END,
        ]
    )


def replace_region(index: str, generated: str) -> str:
    start_count = index.count(START)
    end_count = index.count(END)
    if start_count == 0 and end_count == 0:
        anchor = "## How truth moves"
        if anchor not in index:
            raise ValueError(f"homepage insertion anchor missing: {anchor}")
        return index.replace(anchor, generated + "\n\n" + anchor, 1)
    if start_count != 1 or end_count != 1:
        raise ValueError("homepage projection markers must each occur exactly once")
    start = index.index(START)
    end = index.index(END, start) + len(END)
    return index[:start] + generated + index[end:]


def main() -> int:
    parsed = args()
    manifest = load_manifest()
    target = ROOT / manifest["target_path"]
    current = target.read_text(encoding="utf-8")
    expected = replace_region(current, render(manifest))
    if parsed.check:
        if current != expected:
            print("ERROR: homepage projection is stale; run render_homepage_projection.py --write")
            return 1
        print("Homepage governed projection is current.")
        return 0
    if current == expected:
        print("Homepage governed projection already current; no content churn.")
        return 0
    target.write_text(expected, encoding="utf-8")
    print("Updated index.mdx governed projection.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
