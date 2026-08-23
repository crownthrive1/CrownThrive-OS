#!/usr/bin/env python3
"""Build the first bounded substantive-rebuild wave from the completed 795-title candidate map.

This script intentionally does not reconstruct missing historical bodies or accept terminal
article dispositions. It identifies P0 legacy rows whose current successor documentation is
already substantive enough to support machine-verified parent-review readiness, while
holding D3/high-risk legal, economic, patent, securities, franchise, token and restricted
material outside the automated acceptance lane.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
POLICY_PATH = ROOT / "data/documentation/substantive-rebuild-wave-1-policy.v1.json"
sys.path.insert(0, str(SCRIPTS))

BUILDERS = [
    ("legal_depot", "build_help_center_legal_depot_crosswalk"),
    ("chlom", "build_help_center_chlom_crosswalk"),
    ("convergent_ecosystem", "build_help_center_convergent_ecosystem_crosswalk"),
    ("final_94", "build_help_center_final_94_crosswalk"),
]
LINK_RE = re.compile(r"\]\((/[^) #]+)(?:#[^)]+)?\)")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def route_to_path(route: str) -> Path:
    normalized = route.split("#", 1)[0].strip("/")
    direct = ROOT / normalized
    mdx = ROOT / f"{normalized}.mdx"
    if mdx.is_file():
        return mdx
    if direct.is_file():
        return direct
    raise FileNotFoundError(route)


def route_quality(route: str) -> dict[str, Any]:
    path = route_to_path(route)
    text = path.read_text(encoding="utf-8")
    links = sorted(set(LINK_RE.findall(text)))
    return {
        "route": route,
        "path": path.relative_to(ROOT).as_posix(),
        "body_characters": len(text),
        "internal_link_count": len(links),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def aggregate_candidate_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cohort, module_name in BUILDERS:
        module = importlib.import_module(module_name)
        result = module.build()
        for row in result["records"]:
            item = dict(row)
            item["candidate_cohort"] = cohort
            rows.append(item)
    if len(rows) != 795:
        raise ValueError(f"expected aggregate 795 candidate rows, found {len(rows)}")
    ids = [row["inventory_id"] for row in rows]
    if len(set(ids)) != 795:
        raise ValueError("aggregate candidate map contains duplicate inventory IDs")
    return rows


def text_has_any(text: str, terms: list[str]) -> bool:
    low = text.casefold()
    return any(term.casefold() in low for term in terms)


def choose_anchor(row: dict[str, Any], policy: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    anchors = set(policy["canonical_anchor_routes"])
    quality: list[dict[str, Any]] = []
    for route in row.get("target_routes", []):
        if route not in anchors:
            continue
        try:
            q = route_quality(route)
        except FileNotFoundError:
            continue
        quality.append(q)
        if (
            q["body_characters"] >= int(policy["minimum_anchor_body_characters"])
            and q["internal_link_count"] >= int(policy["minimum_anchor_internal_links"])
        ):
            return route, quality
    return None, quality


def classify(row: dict[str, Any], policy: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    reasons: list[str] = []
    if row.get("priority") != policy["required_priority"]:
        reasons.append("not_p0")
    if row.get("disposition_candidate") != policy["required_candidate_disposition"]:
        reasons.append("candidate_disposition_not_merged_successor")
    if row.get("missing_target_routes"):
        reasons.append("missing_target_route")

    title = str(row.get("legacy_title", ""))
    state = str(row.get("current_state_candidate", ""))
    flags = " ".join(str(x) for x in row.get("flags", []))
    if text_has_any(title, policy["blocked_title_terms"]):
        reasons.append("d3_or_high_risk_title_term")
    if text_has_any(state, policy["blocked_state_terms"]):
        reasons.append("d3_or_high_risk_state")
    if text_has_any(flags, [
        "no_investment", "no_financial", "no_token", "no_current_exchange",
        "private_or_restricted", "legal_review", "financial_web3_or_token",
        "no_financial_or_settlement", "security_or_access_review_required"
    ]):
        reasons.append("explicit_high_risk_flag")

    anchor, quality = choose_anchor(row, policy)
    if not anchor:
        reasons.append("no_qualified_substantive_anchor")

    if reasons:
        return "held", {
            "inventory_id": row["inventory_id"],
            "article_id": row["article_id"],
            "legacy_section": row["legacy_section"],
            "legacy_subcategory": row["legacy_subcategory"],
            "legacy_title": title,
            "priority": row.get("priority"),
            "candidate_disposition": row.get("disposition_candidate"),
            "current_state_candidate": state,
            "target_routes": row.get("target_routes", []),
            "hold_reasons": sorted(set(reasons)),
            "anchor_quality_checked": quality,
        }

    anchor_quality = next(q for q in quality if q["route"] == anchor)
    return "selected", {
        "inventory_id": row["inventory_id"],
        "article_id": row["article_id"],
        "legacy_section": row["legacy_section"],
        "legacy_subcategory": row["legacy_subcategory"],
        "legacy_title": title,
        "priority": row["priority"],
        "candidate_cohort": row["candidate_cohort"],
        "candidate_disposition": row["disposition_candidate"],
        "current_state_candidate": state,
        "canonical_anchor_route": anchor,
        "canonical_anchor_quality": anchor_quality,
        "continuity_routes": row.get("target_routes", []),
        "historical_body_status": row.get("body_status", "reconstruction_required"),
        "substantive_current_successor_body": "present_and_machine_qualified",
        "machine_acceptance_state": policy["machine_acceptance_state"],
        "terminal_disposition_accepted": False,
        "parent_certification_required": True,
        "authority_ceiling": policy["authority_ceiling"],
    }


def build() -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    rows = aggregate_candidate_rows()
    selected: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for row in rows:
        state, record = classify(row, policy)
        (selected if state == "selected" else held).append(record)

    p0_total = sum(1 for row in rows if row.get("priority") == "P0")
    selected_sections = Counter(row["legacy_section"] for row in selected)
    selected_anchors = Counter(row["canonical_anchor_route"] for row in selected)
    hold_reasons = Counter(reason for row in held for reason in row["hold_reasons"])

    payload = {
        "schema_version": "1.0.0",
        "wave_id": "ct.docs.substantive-rebuild.wave-1.v1",
        "sprint": 7,
        "pass": "A_stale_state_and_substantive_successor_qualification",
        "source_universe_count": 795,
        "p0_candidate_count": p0_total,
        "selected_count": len(selected),
        "held_count": len(held),
        "selected_section_counts": dict(sorted(selected_sections.items())),
        "selected_anchor_counts": dict(sorted(selected_anchors.items())),
        "hold_reason_counts": dict(sorted(hold_reasons.items())),
        "policy": policy,
        "selected_records": selected,
        "held_records": held,
        "guardrails": {
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "parent_certification_required": True,
            "d3_human_reserved": True,
            "legal_policy_activation_created": False,
            "investment_or_securities_authority_created": False,
            "patent_status_authority_created": False,
            "franchise_or_license_activation_created": False,
            "token_exchange_or_settlement_authority_created": False,
            "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
            "phase_11_20_state": "reserved_definition_required",
            "canonical_brand": "CrownThrive",
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["wave_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    result = build()
    print("PASS_SUBSTANTIVE_REBUILD_WAVE1_BUILD")
    print(f"source_universe_count={result['source_universe_count']}")
    print(f"p0_candidate_count={result['p0_candidate_count']}")
    print(f"selected_count={result['selected_count']}")
    print(f"held_count={result['held_count']}")
    print("selected_section_counts=" + json.dumps(result["selected_section_counts"], sort_keys=True))
    print("selected_anchor_counts=" + json.dumps(result["selected_anchor_counts"], sort_keys=True))
    print("wave_sha256=" + result["wave_sha256"])
    print("terminal_disposition_self_authorized=false")
    print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output={args.output}")
    elif not args.summary_only:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
