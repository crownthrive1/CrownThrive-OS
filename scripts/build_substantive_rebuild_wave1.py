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
import pentadocs_quality as pentadocs_quality

BUILDERS = [
    ("legal_depot", "build_help_center_legal_depot_crosswalk"),
    ("chlom", "build_help_center_chlom_crosswalk"),
    ("convergent_ecosystem", "build_help_center_convergent_ecosystem_crosswalk"),
    ("final_94", "build_help_center_final_94_crosswalk"),
]
LINK_RE = re.compile(r"\]\((/[^) #]+)(?:#[^)]+)?\)")

# Versioned compatibility layer for current PentaDocs pages.  The audience
# envelope is navigation scaffolding, not evidence that a historical article
# acquired a substantive current successor.  Keep this signature frozen: a
# future generated envelope must use a new algorithm version rather than
# silently changing legacy qualification semantics.
ROUTE_QUALITY_ALGORITHM = "pentadocs_envelope_neutral_v2"
CURRENT_SELECTION_VIEW_SCHEMA = "ct.docs.substantive-current-selection/v2"

# State-family ownership is evaluated before Wave 1's generic canonical-anchor
# scan.  Broad continuity pages (notably /chlom/registry-model) may remain in a
# row's target_routes, but they cannot preempt the state-specific wave that owns
# the row's substantive qualification decision.
WAVE2_RESERVED_STATE_FAMILIES = frozenset({
    "machine_contract_reconciliation",
})
WAVE3_RESERVED_STATE_FAMILIES = frozenset({
    "identity_trust_reconciliation",
    "evidence_audit_reconciliation",
})
WAVE1_STATE_FAMILY_DEFERRAL_REASONS = {
    **{
        state: "deferred_to_wave_2_machine_contract_state_lane"
        for state in WAVE2_RESERVED_STATE_FAMILIES
    },
    **{
        state: "deferred_to_wave_3_identity_evidence_state_lane"
        for state in WAVE3_RESERVED_STATE_FAMILIES
    },
}
PENTADOCS_ORIENTATION_MARKER = "{/* pentadocs:audience-orientation:v1 */}"
PENTADOCS_PROFILE_FIELDS = {
    "standard_version",
    "primary_audience",
    "page_type",
    "content_state",
}

_GENERATED_PAGE_LABELS = {
    "orientation",
    "doctrine page",
    "registry",
    "reference",
    "status record",
    "workflow",
    "runbook",
    "standard",
    "support page",
    "how-to guide",
    "policy page",
    "legal and rights reference",
    "developer reference",
    "dated change record",
    "historical record",
    "page",
}

_GENERATED_AUDIENCE_SIGNATURES = {
    "Info": {
        (
            "executive and governance readers",
            "its documented scope, decisions, and institutional relationships",
            "[Current operational state](/start-here/current-operational-state)",
            "[Governance stack](/governance/governance-stack)",
        ),
        (
            "public and community readers",
            "the documented topic and its CrownThrive relationships",
            "[Start here](/start-here/orientation)",
            "[Ecosystem map](/ecosystem/map)",
        ),
        (
            "support, rights, and licensing readers",
            "the documented support, rights, licensing, or policy context",
            "[Support operating model](/support/support-operating-model)",
            "[Rights and AI provenance](/governance/rights-and-ai-provenance)",
        ),
    },
    "Note": {
        (
            "operators and administrators",
            "the documented controls, responsibilities, and handoffs",
            "[Operating principles](/start-here/operating-principles)",
            "[Permissions and approvals](/automation/permissions-and-approval-gates)",
        ),
        (
            "builders and integrators",
            "the documented interfaces, constraints, and integration context",
            "[Developer platform](/developers/overview)",
            "[API integration standards](/technology/api-integration-standards)",
        ),
    },
}

_GENERATED_ORIENTATION_MESSAGES: dict[str, set[str]] = {
    component: {
        (
            f"**Audience:** {audience}. Use this {page_label} to understand {focus}. "
            f"Continue with {first} or {second}."
        )
        for audience, focus, first, second in signatures
        for page_label in _GENERATED_PAGE_LABELS
    }
    for component, signatures in _GENERATED_AUDIENCE_SIGNATURES.items()
}
_GENERATED_ORIENTATION_MESSAGES["Warning"] = {
    (
        "**Audience:** governance reviewers and researchers. This page is dated context, "
        "not current operating authority. Confirm present guidance in "
        "[Current operational state](/start-here/current-operational-state) and use "
        "[Source authority hierarchy](/knowledge/source-authority-hierarchy) to evaluate "
        "source precedence."
    )
}

_FRONTMATTER_RE = re.compile(
    r"\A---\n(?P<frontmatter>.*?)\n---(?P<body>.*)\Z",
    flags=re.DOTALL,
)
_GENERATED_ORIENTATION_RE = re.compile(
    rf"\A(?P<leading>\s*){re.escape(PENTADOCS_ORIENTATION_MARKER)}\n"
    r"<(?P<component>Info|Note|Warning)>\n"
    r"  (?P<message>[^\n]+)\n"
    r"</(?P=component)>\n\n",
)


def normalize_pentadocs_envelope(text: str) -> str:
    """Remove only exact generated-v1 or managed-v2 audience/profile envelopes.

    Custom audience callouts remain current source content.  Heading demotion,
    Columns migration, and every other body edit also remain visible to the
    legacy quality calculation.
    """

    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return text

    values = pentadocs_quality.parse_frontmatter(match.group("frontmatter")).values
    frontmatter_lines = [
        line
        for line in match.group("frontmatter").splitlines()
        if not (
            (key_match := re.match(r"^([A-Za-z0-9_.:-]+)\s*:", line))
            and key_match.group(1) in PENTADOCS_PROFILE_FIELDS
        )
    ]
    body = match.group("body")
    orientation = _GENERATED_ORIENTATION_RE.match(body)
    if orientation is not None:
        component = orientation.group("component")
        message = orientation.group("message")
        if message in _GENERATED_ORIENTATION_MESSAGES.get(component, set()):
            body = orientation.group("leading") + body[orientation.end() :]
    else:
        v2 = pentadocs_quality.extract_top_orientation(body)
        if (
            v2 is not None
            and v2.marker == pentadocs_quality.ORIENTATION_MARKER
            and pentadocs_quality.is_exact_managed_orientation(v2.rendered, values)
        ):
            tail = body[v2.end :]
            if tail.startswith("\r\n\r\n"):
                tail = tail[4:]
            elif tail.startswith("\n\n"):
                tail = tail[2:]
            elif tail.startswith("\r\n"):
                tail = tail[2:]
            elif tail.startswith("\n"):
                tail = tail[1:]
            body = body[: v2.start] + tail
        elif v2 is not None and v2.marker == pentadocs_quality.ORIENTATION_MARKER:
            body = pentadocs_quality.strip_generated_custom_orientation_supplement(
                body,
                values,
            )

    return f"---\n{'\n'.join(frontmatter_lines)}\n---{body}"


def pentadocs_editorial_eligibility(text: str) -> dict[str, Any]:
    """Return the editorial ceiling for current-successor qualification."""

    match = _FRONTMATTER_RE.match(text)
    values: dict[str, str] = {}
    if match is not None:
        for line in match.group("frontmatter").splitlines():
            field = re.match(
                r"^(primary_audience|content_state)\s*:\s*(.*?)\s*$",
                line,
            )
            if field is None:
                continue
            value = field.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
                value = value[1:-1]
            values[field.group(1)] = value

    reasons: list[str] = []
    if values.get("primary_audience") == "historical":
        reasons.append("primary_audience_historical")
    if values.get("content_state") in {"historical", "superseded"}:
        reasons.append(f"content_state_{values['content_state']}")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "primary_audience": values.get("primary_audience"),
        "content_state": values.get("content_state"),
    }


def current_selection_view(wave: int) -> dict[str, Any]:
    return {
        "schema": CURRENT_SELECTION_VIEW_SCHEMA,
        "wave": wave,
        "quality_algorithm": ROUTE_QUALITY_ALGORITHM,
        "basis": "current_semantic_recomputation",
        "historical_receipts": "immutable_independent_evidence",
        "historical_or_superseded_current_successor_eligible": False,
    }


def editorial_exclusion_report(held_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose candidate IDs held specifically by current editorial state."""

    report: list[dict[str, Any]] = []
    for record in held_records:
        checked = record.get("anchor_quality_checked")
        qualities = checked if isinstance(checked, list) else [checked]
        ineligible = [
            quality
            for quality in qualities
            if isinstance(quality, dict)
            and quality.get("editorial_current_successor_eligible") is False
        ]
        if not ineligible:
            continue
        report.append(
            {
                "inventory_id": record.get("inventory_id"),
                "article_id": record.get("article_id"),
                "anchor_routes": sorted(
                    {str(quality.get("route")) for quality in ineligible if quality.get("route")}
                ),
                "editorial_reasons": sorted(
                    {
                        str(reason)
                        for quality in ineligible
                        for reason in quality.get("editorial_eligibility_reasons", [])
                    }
                ),
                "hold_reasons": sorted(str(reason) for reason in record.get("hold_reasons", [])),
            }
        )
    return sorted(report, key=lambda item: str(item["inventory_id"]))


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
    source_text = path.read_text(encoding="utf-8")
    eligibility = pentadocs_editorial_eligibility(source_text)
    text = normalize_pentadocs_envelope(source_text)
    links = sorted(set(LINK_RE.findall(text)))
    return {
        "quality_algorithm": ROUTE_QUALITY_ALGORITHM,
        "editorial_current_successor_eligible": eligibility["eligible"],
        "editorial_eligibility_reasons": eligibility["reasons"],
        "primary_audience": eligibility["primary_audience"],
        "content_state": eligibility["content_state"],
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


def source_specialist_review_flags(row: dict[str, Any]) -> list[str]:
    """Surface existing review flags without inferring a new specialist route."""

    return sorted(
        {
            str(flag)
            for flag in row.get("flags", [])
            if "review" in str(flag).casefold() or "specialist" in str(flag).casefold()
        }
    )


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
            q["editorial_current_successor_eligible"]
            and q["body_characters"] >= int(policy["minimum_anchor_body_characters"])
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
    deferred_state_reason = WAVE1_STATE_FAMILY_DEFERRAL_REASONS.get(state)
    if deferred_state_reason:
        reasons.append(deferred_state_reason)
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

    # A reserved semantic lane is a policy decision, not a failed generic
    # anchor scan.  Do not let a broad registry route absorb the row first.
    if deferred_state_reason:
        anchor, quality = None, []
    else:
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
            "source_specialist_review_flags": source_specialist_review_flags(row),
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
        "source_specialist_review_flags": source_specialist_review_flags(row),
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
        "selection_view": current_selection_view(1),
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
        "editorial_current_successor_exclusions": editorial_exclusion_report(held),
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
