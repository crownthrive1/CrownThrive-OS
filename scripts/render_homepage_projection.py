#!/usr/bin/env python3
"""Deterministically render the governed CrownThrive homepage projection.

Only the marker-bounded region is generated. The renderer intentionally omits a
wall-clock timestamp: hourly no-op runs are heartbeats, not content changes.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers/manifests/homepage-projection.v1.json"
START_MARKER = "<!-- HOMEPAGE_PROJECTION:START -->"
END_MARKER = "<!-- HOMEPAGE_PROJECTION:END -->"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail when index.mdx is stale.")
    mode.add_argument("--write", action="store_true", help="Write the generated region.")
    return parser.parse_args()


def load_manifest() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != "1.0.0":
        raise ValueError("homepage projection manifest version must be 1.0.0")
    if manifest.get("classification") != "public":
        raise ValueError("homepage projection manifest must remain public-safe")
    if manifest.get("target_path") != "index.mdx":
        raise ValueError("homepage projection target must remain index.mdx")
    if manifest.get("automation", {}).get("direct_main_write") is not False:
        raise ValueError("homepage automation must not write directly to main")
    if manifest.get("commerce_state", {}).get("checkout_enabled") is not False:
        raise ValueError("homepage projection cannot activate checkout")
    cards = manifest.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("homepage projection must declare at least one card")
    for card in cards:
        for field in ("title", "icon", "href", "state", "description"):
            if not isinstance(card.get(field), str) or not card[field].strip():
                raise ValueError(f"homepage card field must be a non-empty string: {field}")
        if not card["href"].startswith("/") or card["href"].startswith("//"):
            raise ValueError("homepage card hrefs must be root-relative documentation routes")
    return manifest


def input_digest(manifest: dict) -> str:
    digest = hashlib.sha256()
    tracked_inputs = manifest.get("tracked_inputs", [])
    if not isinstance(tracked_inputs, list) or not all(
        isinstance(item, str) and item for item in tracked_inputs
    ):
        raise ValueError("homepage projection tracked inputs must be non-empty path strings")
    if len(tracked_inputs) != len(set(tracked_inputs)):
        raise ValueError("homepage projection tracked inputs must be unique")
    root = ROOT.resolve()
    for relative in tracked_inputs:
        path = (ROOT / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"tracked homepage input escapes repository root: {relative}") from exc
        if not path.is_file():
            raise FileNotFoundError(f"tracked homepage input is missing: {relative}")
        payload = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def render(manifest: dict) -> str:
    digest = input_digest(manifest)
    control = manifest["control_state"]
    publication = manifest["publication_state"]
    recovery = manifest["recovery_state"]
    portfolio = manifest["portfolio_observation"]
    capability = manifest["capability_state"]
    commerce = manifest["commerce_state"]
    automation = manifest["automation"]

    lines = [
        START_MARKER,
        "## Governed dynamic projection",
        "",
        "This region is rendered from public-safe machine records. It changes only when a canonical input changes; hourly no-op runs leave a workflow heartbeat without rewriting the page.",
        "",
        "```yaml",
        f"projection_version: {manifest['manifest_version']}",
        f"projection_input_sha256: {digest}",
        f"program_phase: {control['program_phase']}",
        f"phase_3_entry: {control['phase_3_entry']}",
        f"public_readback: {publication['public_readback']}",
        f"mintlify_access_observation: {publication['access_observation']}",
        f"homepage_refresh: {automation['cadence']}_on_change",
        f"direct_main_write: {str(automation['direct_main_write']).lower()}",
        f"recovery_v1_titles: {recovery['v1_unique_title_records']}",
        f"recovery_v1_bodies: {recovery['v1_body_state']}",
        f"public_card_census: {portfolio['public_card_count']}_mixed_entity_cards",
        f"public_card_unmarked: {portfolio['unmarked_card_count']}",
        f"public_card_archived: {portfolio['archived_card_count']}",
        f"governed_framework_count: {capability['framework_count']}",
        f"proprietary_algorithm_state: {capability['proprietary_algorithm_state']}",
        f"cryptographic_capability_state: {capability['cryptographic_state']}",
        f"candidate_monetizable_tools: {commerce['candidate_tool_count']}",
        f"candidate_credit_floor: {commerce['baseline_minimum_credits']}_credits_not_a_price",
        f"stripe_activation: {commerce['stripe_state']}",
        "```",
        "",
        "<Warning>",
        f"  **PUBLIC READBACK BLOCKED.** As observed {publication['observed_at']}, the active default Mintlify URL redirects to authentication. Repository generation and CI can pass while public reachability, indexing, sitemap, robots and machine-ingestion readback remain unverified.",
        "</Warning>",
        "",
        "<CardGroup cols={2}>",
    ]
    for card in manifest.get("cards", []):
        title = html.escape(card["title"], quote=True)
        state = html.escape(card["state"], quote=True)
        icon = html.escape(card["icon"], quote=True)
        href = html.escape(card["href"], quote=True)
        description = html.escape(card["description"], quote=False)
        lines.extend(
            [
                f"  <Card title=\"{title} — {state}\" icon=\"{icon}\" href=\"{href}\">",
                f"    {description}",
                "  </Card>",
                "",
            ]
        )
    if lines[-1] == "":
        lines.pop()
    lines.extend(
        [
            "</CardGroup>",
            "",
            "<Note>",
            "  The 795-record v1 recovery corpus proves titles and hierarchy only; its bodies remain `reconstruction_required`. Detached v2 evidence remains a separate generation on `HOLD` and is not silently merged into v1. Candidate algorithms and tools are not production, legal, security, performance or commercial claims.",
            "</Note>",
            END_MARKER,
        ]
    )
    return "\n".join(lines)


def replace_region(index: str, generated: str) -> str:
    start_count = index.count(START_MARKER)
    end_count = index.count(END_MARKER)
    if start_count == 0 and end_count == 0:
        anchor = "## How truth moves"
        if anchor not in index:
            raise ValueError(f"homepage insertion anchor is missing: {anchor}")
        return index.replace(anchor, generated + "\n\n" + anchor, 1)
    if start_count != 1 or end_count != 1:
        raise ValueError("homepage projection markers must each occur exactly once")
    start = index.index(START_MARKER)
    end = index.index(END_MARKER, start) + len(END_MARKER)
    return index[:start] + generated + index[end:]


def main() -> int:
    args = parse_args()
    manifest = load_manifest()
    target = ROOT / manifest["target_path"]
    current = target.read_text(encoding="utf-8")
    expected = replace_region(current, render(manifest))

    if args.check:
        if current != expected:
            print("ERROR: index.mdx dynamic projection is stale; run scripts/render_homepage_projection.py --write")
            return 1
        print("CrownThrive homepage dynamic projection is current.")
        return 0

    if current == expected:
        print("CrownThrive homepage dynamic projection already current; no content churn.")
        return 0
    target.write_text(expected, encoding="utf-8")
    print(f"Updated {target.relative_to(ROOT)} from {MANIFEST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
