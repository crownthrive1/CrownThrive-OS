#!/usr/bin/env python3
"""Dedicated current-successor substantive gate for Wave 7 Batch 004 Lane A.

This gate is intentionally conservative. It may qualify only the exact zero-flag
Lane A identities emitted by Batch 004, and only when a current mapped successor
route is substantive and carries strong lexical evidence for the recovered legacy
intent. A held record remains pending; the gate never fabricates historical bodies,
accepts terminal disposition, or expands legal/economic/provider authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave1 as wave1
import execute_docs_rebuild_quad_lane_batch as q1

RECEIPT_PATH = ROOT / "developers/manifests/docs-rebuild-quad-lane-batch-004.v1.json"
GATE1 = ROOT / "developers/manifests/docs-wave7-adluxe-substantive-gate-001.v1.json"
GATE2 = ROOT / "developers/manifests/docs-wave7-adluxe-substantive-gate-002.v1.json"
GATE3 = ROOT / "developers/manifests/docs-wave7-melanin-magic-substantive-gate-003.v1.json"
EXPECTED_IDS = ["HC-0114", "HC-0115", "HC-0117", "HC-0256"]

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "into", "is", "it", "of", "on", "or", "our", "the", "to", "using",
    "with", "your", "you", "guide", "overview", "help", "center", "crownthrive",
}


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate_by_id() -> dict[str, dict[str, Any]]:
    return {str(r["inventory_id"]): r for r in wave1.aggregate_candidate_rows()}


def prior_qualified_ids() -> set[str]:
    ids = set(q1.prior_ids())
    for path in (GATE1, GATE2, GATE3):
        ids.update(str(x) for x in load_json(path)["qualified_inventory_ids"])
    if len(ids) != 73:
        raise ValueError(f"expected 73 prior machine-qualified records, found {len(ids)}")
    return ids


def tokens(value: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(value.casefold()) if t not in STOPWORDS and len(t) >= 3]


def lexical_evidence(title: str, state: str, text: str) -> dict[str, Any]:
    low = text.casefold()
    title_exact = title.casefold() in low if title.strip() else False
    state_exact = state.casefold() in low if len(state.strip()) >= 12 else False
    title_tokens = sorted(set(tokens(title)))
    state_tokens = sorted(set(tokens(state)))
    evidence_tokens = title_tokens or state_tokens
    matched = [t for t in evidence_tokens if t in low]
    coverage = (len(matched) / len(evidence_tokens)) if evidence_tokens else 0.0
    long_anchor = any(len(t) >= 6 for t in matched)
    if len(evidence_tokens) <= 2:
        lexical_pass = bool(title_exact or state_exact)
    else:
        lexical_pass = bool(title_exact or state_exact or (coverage >= 0.75 and len(matched) >= 3 and long_anchor))
    return {
        "title_exact": title_exact,
        "state_exact": state_exact,
        "evidence_tokens": evidence_tokens,
        "matched_tokens": matched,
        "token_coverage": round(coverage, 4),
        "long_anchor_present": long_anchor,
        "lexical_pass": lexical_pass,
    }


def best_successor(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    observed: list[dict[str, Any]] = []
    title = str(row.get("legacy_title", ""))
    state = str(row.get("current_state_candidate", ""))
    for route in row.get("target_routes", []):
        try:
            q = wave1.route_quality(route)
            text = wave1.route_to_path(route).read_text(encoding="utf-8")
        except FileNotFoundError:
            observed.append({"route": route, "route_present": False, "accepted": False})
            continue
        lex = lexical_evidence(title, state, text)
        accepted = bool(q["body_characters"] >= 12000 and q["internal_link_count"] >= 4 and lex["lexical_pass"])
        item = {**q, **lex, "route_present": True, "accepted": accepted}
        observed.append(item)
    accepted_routes = [x for x in observed if x.get("accepted")]
    accepted_routes.sort(key=lambda x: (x.get("token_coverage", 0), x.get("body_characters", 0)), reverse=True)
    return (accepted_routes[0] if accepted_routes else None), observed


def build() -> dict[str, Any]:
    receipt = load_json(RECEIPT_PATH)
    admitted = list(receipt["lane_inventory_ids"]["A"])
    if admitted != EXPECTED_IDS:
        raise ValueError(f"Batch 004 Lane A identity drift: {admitted}")
    if receipt["official_counts_after_batch"] != {"machine_qualified_p0": 73, "pending_p0": 376}:
        raise ValueError("unexpected Batch 004 baseline")
    if not receipt["guardrails"]["lane_a_requires_zero_flags"]:
        raise ValueError("Batch 004 did not enforce zero-flag Lane A admission")

    rows = aggregate_by_id()
    prior = prior_qualified_ids()
    if prior & set(EXPECTED_IDS):
        raise ValueError("Gate 004 cohort overlaps prior qualified identities")

    results: list[dict[str, Any]] = []
    selected: list[str] = []
    for inventory_id in EXPECTED_IDS:
        row = rows[inventory_id]
        reasons: list[str] = []
        flags = list(row.get("flags", []))
        if row.get("priority") != "P0":
            reasons.append("not_p0")
        if row.get("disposition_candidate") != "merged_successor":
            reasons.append("not_merged_successor_candidate")
        if flags:
            reasons.append("candidate_flags_not_empty")
        if row.get("missing_target_routes"):
            reasons.append("missing_target_routes")
        if q1.is_high_risk(row):
            reasons.append("high_risk_semantics")

        successor, observations = best_successor(row)
        if successor is None:
            reasons.append("no_substantive_intent_matched_current_successor")

        accepted = not reasons
        if accepted:
            selected.append(inventory_id)
        results.append({
            "inventory_id": inventory_id,
            "article_id": row.get("article_id"),
            "legacy_section": row.get("legacy_section"),
            "legacy_subcategory": row.get("legacy_subcategory"),
            "legacy_title": row.get("legacy_title"),
            "current_state_candidate": row.get("current_state_candidate"),
            "target_routes": row.get("target_routes", []),
            "candidate_flags": flags,
            "accepted_successor": successor,
            "route_observations": observations,
            "machine_substantive_qualified": accepted,
            "qualification_state": "QUALIFIED_CURRENT_SUCCESSOR" if accepted else "HELD",
            "hold_reasons": sorted(set(reasons)),
            "historical_body_recovered": False,
            "terminal_disposition_accepted": False,
            "parent_review_required_for_terminal_disposition": True,
        })

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "gate_id": "ct.docs.rebuild.wave7.substantive-gate-004.v1",
        "source_execution_receipt": RECEIPT_PATH.relative_to(ROOT).as_posix(),
        "records_evaluated": len(EXPECTED_IDS),
        "records_machine_qualified": len(selected),
        "qualified_inventory_ids": selected,
        "held_inventory_ids": [x for x in EXPECTED_IDS if x not in set(selected)],
        "results": results,
        "counting": {
            "machine_qualified_before": 73,
            "pending_p0_before": 376,
            "machine_qualified_delta": len(selected),
            "pending_p0_delta": -len(selected),
            "machine_qualified_after": 73 + len(selected),
            "pending_p0_after": 376 - len(selected),
        },
        "guardrails": {
            "exact_lane_a_identity_required": True,
            "zero_candidate_flags_required": True,
            "high_risk_semantics_prohibited": True,
            "substantive_route_minimum_body_characters": 12000,
            "substantive_route_minimum_internal_links": 4,
            "strong_intent_evidence_required": True,
            "held_records_count_as_qualified": False,
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "authority_activation_created": False,
            "provider_write_expansion_created": False,
            "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
        },
    }
    payload["gate_sha256"] = canonical_hash(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build()
    print("PASS_WAVE7_SUBSTANTIVE_GATE_004")
    print("qualified_inventory_ids=" + ",".join(result["qualified_inventory_ids"]))
    print("held_inventory_ids=" + ",".join(result["held_inventory_ids"]))
    print(f"records_machine_qualified={result['records_machine_qualified']}")
    print(f"machine_qualified_after={result['counting']['machine_qualified_after']}")
    print(f"pending_p0_after={result['counting']['pending_p0_after']}")
    print("historical_body_recovery_claimed=false")
    print("terminal_disposition_self_authorized=false")
    print("gate_sha256=" + result["gate_sha256"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output={args.output}")


if __name__ == "__main__":
    main()
