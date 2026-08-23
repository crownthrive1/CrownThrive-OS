#!/usr/bin/env python3
"""Build the Sprint 3 CrownThrive Legal Depot reconstruction crosswalk.

This script decodes the existing 795-title compact Help Center bundle, isolates the
198 Legal Depot recovery records, and produces candidate successor/disposition
records without claiming recovery of missing historical article bodies.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/help_center_article_manifest.v1.bundle.json"
RULES = ROOT / "data/documentation/help-center-legal-depot-reconstruction-rules.v1.json"
TARGET_SECTION = "CrownThrive Legal Depot"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def decode_bundle() -> list[dict[str, Any]]:
    bundle = load_json(BUNDLE)
    encoded = "".join((ROOT / part).read_text(encoding="utf-8").strip() for part in bundle["parts"])
    decoded = json.loads(gzip.decompress(base64.b64decode(encoded)).decode("utf-8"))
    fields = bundle.get("record_encoding", {}).get("fields", [])

    candidates: Any = decoded
    if isinstance(decoded, dict):
        if isinstance(decoded.get("records"), list):
            candidates = decoded["records"]
        elif isinstance(decoded.get("rows"), list):
            candidates = decoded["rows"]
        else:
            list_values = [value for value in decoded.values() if isinstance(value, list) and len(value) == 795]
            if len(list_values) != 1:
                raise ValueError("unable to locate unique 795-record list in compact manifest")
            candidates = list_values[0]

    if not isinstance(candidates, list) or len(candidates) != 795:
        raise ValueError(f"expected 795 compact records, found {len(candidates) if isinstance(candidates, list) else 'non-list'}")

    records: list[dict[str, Any]] = []
    for index, row in enumerate(candidates, 1):
        if isinstance(row, dict):
            record = dict(row)
        elif isinstance(row, list):
            if not fields or len(row) != len(fields):
                raise ValueError(f"compact row {index} cannot be decoded with declared fields")
            record = dict(zip(fields, row))
        else:
            raise ValueError(f"unsupported compact row type at {index}: {type(row).__name__}")

        order = int(record.get("recovered_order", record.get("order", index)))
        record.setdefault("inventory_id", f"HC-{order:04d}")
        record.setdefault("article_id", f"ct.article.recovered.{order:04d}")
        record.setdefault("recovered_order", order)
        record.setdefault("recovered_section", record.get("section"))
        record.setdefault("recovered_subcategory", record.get("subcategory"))
        record.setdefault("recovered_title", record.get("title"))
        records.append(record)
    return records


def route_exists(route: str) -> bool:
    normalized = route.split("#", 1)[0].strip("/")
    return (ROOT / f"{normalized}.mdx").is_file() or (ROOT / normalized).is_file()


def contains_any(text: str, terms: list[str]) -> bool:
    low = text.casefold()
    return any(term.casefold() in low for term in terms)


def classify(record: dict[str, Any], ruleset: dict[str, Any]) -> dict[str, Any]:
    title = str(record["recovered_title"])
    sub = str(record["recovered_subcategory"])
    low = title.casefold()
    rule = ruleset["subcategory_rules"].get(sub)
    if not rule:
        raise ValueError(f"missing Legal Depot subcategory rule: {sub}")

    priority = rule.get("default_priority", "P1")
    disposition = rule.get("default_disposition_candidate", "merged_successor")
    routes = list(rule.get("target_routes", []))
    state = "needs_current_reconciliation"
    flags: list[str] = []

    if sub == "Governance & Leadership Policies":
        if contains_any(title, rule.get("historical_patterns", [])):
            state = "historical_or_program_specific"
            routes = [
                "/governance/thrivealumni-governance-lineage",
                "/governance/governance-stack",
                "/support/legal-status-and-historical-claim-supersession",
            ]
        if contains_any(title, rule.get("research_or_legal_review_patterns", [])):
            state = "historical_research_or_legal_review_required"
            disposition = "superseded_history"
            priority = "P2"
            flags.append("no_current_legal_or_token_claim")
        if "founder" in low:
            state = "current_governance_reconciliation"
            disposition = "merged_successor"
            priority = "P0"
            routes = list(rule.get("founder_authority_routes", routes))

    elif sub == "Master Terms & Universal Policies":
        if contains_any(title, ["Privacy", "Data Rights", "Content Ownership"]):
            routes = list(rule.get("privacy_routes", routes))
        elif contains_any(title, ["Payment", "Refund", "Failed Transaction"]):
            routes = list(rule.get("payment_routes", routes))
        elif contains_any(title, ["Affiliate", "Ambassador", "Referral"]):
            routes = list(rule.get("affiliate_routes", routes))
        elif contains_any(title, ["Intellectual Property", "Brand, Logo", "Licensing", "Commercial Rights", "White-Label", "IP Protection"]):
            routes = list(rule.get("ip_licensing_routes", routes))
        elif contains_any(title, ["AI &", "Automation Ethics", "AI Moderation"]):
            routes = list(rule.get("ai_routes", routes))
        if contains_any(title, rule.get("research_or_legal_review_patterns", [])):
            state = "historical_research_or_legal_review_required"
            disposition = "superseded_history"
            priority = "P2"
            flags.append("no_current_token_equity_authority")

    elif sub == "Platform-Specific Addenda":
        if contains_any(title, rule.get("sunset_or_historical_patterns", [])):
            state = "historical_or_sunset_addendum"
            disposition = "superseded_history"
            priority = "P2"
            routes.append(rule["sunset_route"])
        elif "addenda" in low or "addendum" in low:
            state = "platform_addendum_current_state_required"

    elif sub == "Programs, Incubators & Partner Tiers":
        if contains_any(title, ["Investment", "Equity"]):
            priority = "P0"
            state = "legal_review_required"
            flags.append("no_investment_or_equity_claim_without_current_authority")
        elif "refund" in low:
            priority = "P0"
            routes = ["/commerce/payment-and-fulfillment", "/support/legal-depot-policy-matrix"]

    elif sub == "Disclaimers & Legal Notices":
        if contains_any(title, rule.get("high_risk_patterns", [])):
            state = "high_risk_disclaimer_reconciliation"
            flags.append("no_financial_or_web3_promotion")
        elif "entity disclosure" in low:
            routes = ["/portfolio/entity-architecture", "/support/legal-status-and-historical-claim-supersession"]
        elif "support center" in low or "thrivebot" in low:
            routes = ["/support/support-operating-model", "/platforms/thrivesupport-institutional-registry", "/support/cross-platform-disclaimer-and-disclosure-matrix"]

    elif sub == "Privacy, Data & Cookies":
        state = "privacy_current_state_reconciliation"

    elif sub == "Support Policies & User Expectations":
        if contains_any(title, ["Refund", "Dispute"]):
            priority = "P0"
            routes = list(rule.get("payment_routes", routes))
        elif contains_any(title, ["Maintenance", "Uptime"]):
            routes = list(rule.get("status_routes", routes))
        elif "version control" in low:
            priority = "P0"
            routes = list(rule.get("versioning_routes", routes))

    elif sub == "Affiliate, Referral & Earnings Policies":
        if contains_any(title, ["Agreement", "Earnings Disclaimer"]):
            priority = "P0"

    elif sub == "Standard Operating Procedures (SOPs)":
        if contains_any(title, rule.get("p0_patterns", [])):
            priority = "P0"
        if "platform retirement" in low:
            routes = list(rule.get("sunset_routes", routes))
        elif "public help center" in low:
            routes = list(rule.get("docs_routes", routes))

    elif sub == "Platform Lifecycle & Sunset Notices":
        state = "current_successor_exists"

    elif sub == "CHLOM™ Legal & IP Notices":
        state = "chlom_rights_legal_reconciliation"
        if "crownththrive" in low:
            flags.append("source_title_typo_preserved_current_brand_normalized")

    missing_routes = [route for route in routes if not route_exists(route)]
    if missing_routes:
        flags.append("candidate_route_missing")

    return {
        "article_id": record["article_id"],
        "inventory_id": record["inventory_id"],
        "legacy_order": int(record["recovered_order"]),
        "legacy_section": record["recovered_section"],
        "legacy_subcategory": sub,
        "legacy_title": title,
        "body_status": "reconstruction_required",
        "priority": priority,
        "current_state_candidate": state,
        "disposition_candidate": disposition,
        "target_routes": routes,
        "missing_target_routes": missing_routes,
        "flags": flags,
        "review_state": "candidate_requires_evidence_review",
        "terminal_disposition_authorized": False,
    }


def build() -> dict[str, Any]:
    records = decode_bundle()
    ruleset = load_json(RULES)
    legal = [record for record in records if record.get("recovered_section") == TARGET_SECTION]
    if len(legal) != ruleset["expected_title_count"]:
        raise ValueError(f"expected {ruleset['expected_title_count']} Legal Depot titles, found {len(legal)}")

    crosswalk = [classify(record, ruleset) for record in legal]
    if len({row["inventory_id"] for row in crosswalk}) != len(crosswalk):
        raise ValueError("duplicate inventory IDs in Legal Depot crosswalk")
    if any(row["legacy_section"] != TARGET_SECTION for row in crosswalk):
        raise ValueError("non-Legal-Depot record leaked into Sprint 3 scope")
    if any(row["body_status"] != "reconstruction_required" for row in crosswalk):
        raise ValueError("missing historical bodies may not be promoted as recovered")
    if any(row["terminal_disposition_authorized"] for row in crosswalk):
        raise ValueError("candidate build may not self-authorize terminal disposition")

    priority_counts = Counter(row["priority"] for row in crosswalk)
    disposition_counts = Counter(row["disposition_candidate"] for row in crosswalk)
    state_counts = Counter(row["current_state_candidate"] for row in crosswalk)
    missing_route_rows = [row for row in crosswalk if row["missing_target_routes"]]

    return {
        "schema_version": "1.0.0",
        "crosswalk_id": "ct.docs.help-center.legal-depot-crosswalk.candidate.v1",
        "sprint": 3,
        "pass": "A_stale_state_reconciliation_candidate",
        "section": TARGET_SECTION,
        "record_count": len(crosswalk),
        "source_forensic_universe": 795,
        "summary": {
            "priority_counts": dict(sorted(priority_counts.items())),
            "disposition_candidate_counts": dict(sorted(disposition_counts.items())),
            "current_state_candidate_counts": dict(sorted(state_counts.items())),
            "missing_target_route_rows": len(missing_route_rows),
        },
        "guardrails": {
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
            "phase_11_20_state": "reserved_definition_required",
            "canonical_brand": "CrownThrive",
        },
        "records": crosswalk,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    result = build()
    print("PASS_HELP_CENTER_LEGAL_DEPOT_CROSSWALK")
    print(f"records={result['record_count']}")
    print("priority_counts=" + json.dumps(result["summary"]["priority_counts"], sort_keys=True))
    print("disposition_candidate_counts=" + json.dumps(result["summary"]["disposition_candidate_counts"], sort_keys=True))
    print("missing_target_route_rows=" + str(result["summary"]["missing_target_route_rows"]))
    print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output={args.output}")
    elif not args.summary_only:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
