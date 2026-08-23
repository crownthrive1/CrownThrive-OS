#!/usr/bin/env python3
"""Build Sprint 4 candidate crosswalk for all 297 recovered CHLOM Help Center titles.

The source bundle is the existing 795-title forensic manifest. This script does not
claim recovery of missing article bodies and does not self-authorize terminal
rights/legal/economic/production state.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/help_center_article_manifest.v1.bundle.json"
TARGET_SECTION = "CHLOM"
EXPECTED = 297


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
            lists = [v for v in decoded.values() if isinstance(v, list) and len(v) == 795]
            if len(lists) != 1:
                raise ValueError("unable to locate unique 795-record list")
            candidates = lists[0]
    if not isinstance(candidates, list) or len(candidates) != 795:
        raise ValueError("forensic manifest must contain exactly 795 records")

    records: list[dict[str, Any]] = []
    for index, row in enumerate(candidates, 1):
        if isinstance(row, dict):
            record = dict(row)
        elif isinstance(row, list) and fields and len(row) == len(fields):
            record = dict(zip(fields, row))
        else:
            raise ValueError(f"unsupported compact row at {index}")
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


def any_term(text: str, terms: tuple[str, ...]) -> bool:
    low = text.casefold()
    return any(term.casefold() in low for term in terms)


def classify(record: dict[str, Any]) -> dict[str, Any]:
    title = str(record.get("recovered_title") or "").strip()
    sub = str(record.get("recovered_subcategory") or "").strip()
    text = f"{title} {sub}"
    low = text.casefold()

    priority = "P1"
    state = "needs_current_reconciliation"
    disposition = "merged_successor"
    routes = ["/chlom/overview", "/chlom/source-reconciliation", "/chlom/module-catalog"]
    flags: list[str] = []

    # Historical/research lineage is preserved without promoting it to current authority.
    if any_term(text, ("whitepaper", "white paper", "research", "genesis", "blueprint", "historical", "concept", "theory", "future state", "future-state")):
        priority = "P2"
        state = "historical_research_reconciliation"
        disposition = "superseded_history"
        routes = ["/chlom/historical-papers-and-research", "/chlom/paper-suite-and-ip-library", "/chlom/source-reconciliation"]
        flags.append("no_historical_research_promotion_to_current_authority")

    # Authority, approvals, governance and correction are Phase-3-sensitive.
    if any_term(text, ("authority", "approval", "governance", "founder", "adjudication", "override", "correction", "consent", "permission")):
        priority = "P0"
        state = "authority_governance_reconciliation"
        disposition = "merged_successor"
        routes = ["/chlom/founder-adjudication-and-after-the-fact-correction", "/chlom/lifecycle-and-remedies", "/chlom/source-reconciliation"]
        flags.append("no_authority_expansion_from_article_rebuild")

    # Rights, licenses and entitlements are independently consequential.
    if any_term(text, ("dla", "license", "licensing", "rights", "royalty", "entitlement", "ownership", "chain of title", "attribution")):
        priority = "P0"
        state = "rights_license_reconciliation"
        disposition = "merged_successor"
        routes = ["/chlom/dla-dail-lex", "/chlom/rights-ledger-and-evidence", "/chlom/lifecycle-and-remedies"]
        flags.append("rights_and_license_state_requires_current_evidence")

    # Evidence, DAIL, provenance and proofs map to the current evidence spine.
    if any_term(text, ("dail", "evidence", "audit", "proof", "provenance", "receipt", "ledger", "record integrity", "attestation")):
        priority = "P0"
        state = "evidence_audit_reconciliation"
        disposition = "merged_successor"
        routes = ["/chlom/rights-ledger-and-evidence", "/chlom/source-reconciliation", "/chlom/registry-model"]

    # LEX/economic/settlement concepts are preserved but cannot create economic authority.
    if any_term(text, ("lex", "treasury", "economic", "settlement", "payout", "payment", "marketplace", "exchange", "revenue", "value routing", "value-routing")):
        priority = "P0"
        state = "economic_lex_reconciliation"
        disposition = "merged_successor"
        routes = ["/chlom/dla-dail-lex", "/chlom/lifecycle-and-remedies", "/commerce/thriveevergreen"]
        flags.append("no_economic_authority_from_recovered_title")

    # Identity and trust signals map to CrownThrive ID but do not create identity proof.
    if any_term(text, ("identity", "did", "decentralized identifier", "passport", "reputation", "trust score", "trust-score", "credential")):
        priority = "P0"
        state = "identity_trust_reconciliation"
        disposition = "merged_successor"
        routes = ["/technology/crownthrive-id", "/chlom/registry-model", "/chlom/source-reconciliation"]
        flags.append("identity_claim_requires_current_binding_evidence")

    # Machine contracts are seed-critical for Phase 3.
    if any_term(text, ("api", "mcp", "webhook", "sdk", "schema", "registry", "event", "data model", "data-model", "endpoint", "integration")):
        priority = "P0"
        state = "machine_contract_reconciliation"
        disposition = "merged_successor"
        routes = ["/chlom/registry-model", "/chlom/phase-3-service-contract", "/chlom/ecosystem-integrations"]

    # Framework/pallet/module/engine concepts map to the current compositional model.
    if any_term(text, ("pallet", "component", "module", "framework", "engine", "protocol", "metaprotocol", "service map", "service-map")):
        if priority != "P0":
            priority = "P1"
        state = "component_framework_reconciliation"
        if disposition != "superseded_history":
            disposition = "merged_successor"
        routes = ["/chlom/module-catalog", "/chlom/full-component-pallet-atlas", "/chlom/component-pallet-service-implementation-map"]

    # AI/agent/algorithm concepts map into current protected capability/factory surfaces.
    if any_term(text, ("ai", "agent", "algorithm", "oracle", "automation", "model", "machine learning", "machine-learning")):
        if priority != "P0":
            priority = "P1"
        state = "ai_agent_algorithm_reconciliation"
        if disposition != "superseded_history":
            disposition = "merged_successor"
        routes = ["/chlom/module-catalog", "/chlom/proprietary-asset-factory", "/chlom/paper-to-engineering-decomposition-pipeline"]
        flags.append("no_model_or_agent_authority_from_title_only")

    # User/operator surfaces.
    if any_term(text, ("portal", "dashboard", "widget", "console", "interface", "workspace")):
        if priority != "P0":
            priority = "P1"
        state = "interface_surface_reconciliation"
        disposition = "merged_successor"
        routes = ["/chlom/portal-dashboard-widget-catalog", "/chlom/ecosystem-integrations", "/chlom/module-catalog"]

    # Recovery and continuity are P0 because they affect institutional survivability.
    if any_term(text, ("recovery", "migration", "continuity", "backup", "rollback", "restore", "disaster", "vendor exit", "vendor-exit")):
        priority = "P0"
        state = "recovery_continuity_reconciliation"
        disposition = "merged_successor"
        routes = ["/chlom/recovery-modernization-and-build-plan", "/chlom/lifecycle-and-remedies", "/chlom/source-reconciliation"]

    # Exact overview-like source identities may map directly to the canonical overview.
    normalized_title = " ".join(title.casefold().replace("™", "").split())
    if normalized_title in {"chlom overview", "what is chlom", "what is chlom?", "chlom metaprotocol overview"}:
        priority = "P0"
        state = "current_canonical_overview_candidate"
        disposition = "canonical_article"
        routes = ["/chlom/overview", "/chlom/six-functions", "/chlom/current-vs-target-architecture"]

    missing = [route for route in routes if not route_exists(route)]
    if missing:
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
        "missing_target_routes": missing,
        "flags": sorted(set(flags)),
        "review_state": "candidate_requires_evidence_review",
        "terminal_disposition_authorized": False,
    }


def build() -> dict[str, Any]:
    records = decode_bundle()
    scoped = [r for r in records if r.get("recovered_section") == TARGET_SECTION]
    if len(scoped) != EXPECTED:
        raise ValueError(f"expected {EXPECTED} CHLOM titles, found {len(scoped)}")
    crosswalk = [classify(r) for r in scoped]
    if len({r["inventory_id"] for r in crosswalk}) != EXPECTED:
        raise ValueError("duplicate inventory IDs in CHLOM crosswalk")
    if any(r["legacy_section"] != TARGET_SECTION for r in crosswalk):
        raise ValueError("non-CHLOM record leaked into scope")
    if any(r["body_status"] != "reconstruction_required" for r in crosswalk):
        raise ValueError("missing source bodies may not be promoted to recovered")
    if any(r["terminal_disposition_authorized"] for r in crosswalk):
        raise ValueError("candidate build may not self-authorize terminal disposition")

    priorities = Counter(r["priority"] for r in crosswalk)
    dispositions = Counter(r["disposition_candidate"] for r in crosswalk)
    states = Counter(r["current_state_candidate"] for r in crosswalk)
    missing_rows = [r for r in crosswalk if r["missing_target_routes"]]

    return {
        "schema_version": "1.0.0",
        "crosswalk_id": "ct.docs.help-center.chlom-crosswalk.candidate.v1",
        "sprint": 4,
        "pass": "A_stale_state_reconciliation_candidate",
        "section": TARGET_SECTION,
        "record_count": EXPECTED,
        "source_forensic_universe": 795,
        "summary": {
            "priority_counts": dict(sorted(priorities.items())),
            "disposition_candidate_counts": dict(sorted(dispositions.items())),
            "current_state_candidate_counts": dict(sorted(states.items())),
            "missing_target_route_rows": len(missing_rows),
        },
        "guardrails": {
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "legal_rights_economic_authority_expansion": False,
            "production_activation_created": False,
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
    print("PASS_HELP_CENTER_CHLOM_CROSSWALK")
    print(f"records={result['record_count']}")
    print("priority_counts=" + json.dumps(result["summary"]["priority_counts"], sort_keys=True))
    print("disposition_candidate_counts=" + json.dumps(result["summary"]["disposition_candidate_counts"], sort_keys=True))
    print("current_state_candidate_counts=" + json.dumps(result["summary"]["current_state_candidate_counts"], sort_keys=True))
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
