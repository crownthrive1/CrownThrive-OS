#!/usr/bin/env python3
"""Build the Sprint 6 candidate crosswalk for the final 94 recovered Help Center titles."""
from __future__ import annotations
import argparse, base64, gzip, hashlib, json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/help_center_article_manifest.v1.bundle.json"
ALREADY_MAPPED = {"CrownThrive Legal Depot", "CHLOM", "Convergent Ecosystem"}
EXPECTED_SECTIONS = {
    "CrownThrive HQ": 46,
    "Cultural Imprint Engine (CIE)": 11,
    "Hybrid Incubator": 5,
    "Investor Relations": 5,
    "MM Suites": 13,
    "Thrive Flywheel": 14,
}

LEGAL = ["/support/legal-depot-policy-matrix", "/support/legal-status-and-historical-claim-supersession", "/standards/evidence-claims-and-proof-standard"]
IP = ["/knowledge/patent-defensibility-register", "/standards/ip-protection-chain-of-title-and-trade-secret", "/governance/ip-ownership-and-control"]
RESTRICTED = ["/knowledge/restricted-source-register", "/standards/ip-protection-chain-of-title-and-trade-secret", "/chlom/proprietary-asset-factory"]
NARRATIVE = ["/doctrine/convergent-ecosystem", "/doctrine/master-narrative-ledger", "/ecosystem/holdings-and-asset-spine"]
INFRA = ["/technology/cloud-sovereign-deployment-blueprint", "/technology/dependency-backup-and-recovery", "/portfolio/engine-domain-vendor-registry"]
INVEST = ["/support/legal-status-and-historical-claim-supersession", "/standards/evidence-claims-and-proof-standard", "/ecosystem/holdings-and-asset-spine"]
COLLAB = ["/platforms/collab-portal-institutional-registry", "/governance/model", "/support/legal-status-and-historical-claim-supersession"]
CIE_CORE = ["/doctrine/cultural-imprint-engine", "/doctrine/cie-public-internal-usage", "/doctrine/cie-integration-handoffs"]
KULTURE = ["/portfolio/kulture-house-kulture-radio-institutional-record", "/doctrine/cultural-imprint-engine", "/standards/evidence-claims-and-proof-standard"]
BONGED = ["/portfolio/bonged-out-institutional-record", "/commerce/thriveevergreen", "/support/legal-status-and-historical-claim-supersession"]
LUX = ["/platforms/hospitality-travel-experiences-institutional-registry", "/corridors/hospitality-travel-experiences", "/doctrine/cultural-imprint-engine"]
STUDIO = ["/platforms/crownthrive-studios-institutional-registry", "/support/legal-status-and-historical-claim-supersession", "/doctrine/cultural-imprint-engine"]
HYBRID = ["/doctrine/hybrid-incubator", "/doctrine/convergent-ecosystem", "/governance/model"]
HYBRID_RIGHTS = ["/doctrine/hybrid-incubator", "/chlom/dla-dail-lex", "/commerce/thriveevergreen", "/technology/phase-3-readiness-gate"]
MM = ["/corridors/mm-suites-lineage-and-current-state", "/corridors/mm-suites-phygital-operating-spine", "/portfolio/platform-state-register"]
MM_COMM = ["/corridors/mm-suites-phygital-operating-spine", "/commerce/thriveevergreen", "/support/legal-status-and-historical-claim-supersession"]
MM_REWARDS = ["/platforms/crownrewards-institutional-registry", "/corridors/mm-suites-phygital-operating-spine", "/commerce/thriveevergreen"]
MM_DOCS = ["/standards/documentation-source-of-truth-and-autonomous-governance", "/corridors/mm-suites-lineage-and-current-state", "/knowledge/restricted-source-register"]
FW = ["/doctrine/thrive-flywheel", "/doctrine/convergent-ecosystem", "/revenue/revenue-architecture"]
FW_GOV = ["/doctrine/thrive-flywheel", "/governance/model", "/chlom/overview"]
FW_INC = ["/doctrine/thrive-flywheel", "/doctrine/hybrid-incubator", "/ecosystem/flows-and-handoffs"]
FW_TOOLS = ["/doctrine/thrive-flywheel", "/doctrine/framework-engine-registry", "/ecosystem/platform-registry"]
FW_PAPERS = ["/doctrine/thrive-flywheel", "/knowledge/research-study-ip-register", "/knowledge/source-authority-hierarchy"]


def load_records() -> list[dict[str, Any]]:
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    encoded = "".join((ROOT / p).read_text(encoding="utf-8").strip() for p in bundle["parts"])
    decoded = json.loads(gzip.decompress(base64.b64decode(encoded)).decode("utf-8"))
    fields = bundle.get("record_encoding", {}).get("fields", [])
    candidates: Any = decoded.get("records", decoded.get("rows", decoded)) if isinstance(decoded, dict) else decoded
    if not isinstance(candidates, list) or len(candidates) != 795:
        raise ValueError("compact Help Center bundle must contain exactly 795 records")
    records = []
    for i, row in enumerate(candidates, 1):
        r = dict(zip(fields, row)) if isinstance(row, list) else dict(row)
        order = int(r.get("recovered_order", r.get("order", i)))
        r.setdefault("recovered_order", order)
        r.setdefault("inventory_id", f"HC-{order:04d}")
        r.setdefault("article_id", f"ct.article.recovered.{order:04d}")
        r.setdefault("recovered_section", r.get("section"))
        r.setdefault("recovered_subcategory", r.get("subcategory"))
        r.setdefault("recovered_title", r.get("title"))
        records.append(r)
    return records


def route_exists(route: str) -> bool:
    p = route.split("#", 1)[0].strip("/")
    return (ROOT / f"{p}.mdx").is_file() or (ROOT / p).is_file()


def phase_vector() -> dict[str, str]:
    return {str(i): ("reserved_definition_required" if i >= 11 else "continuity_impact_only") for i in range(1, 21)}


def classify(r: dict[str, Any]) -> dict[str, Any]:
    section = str(r["recovered_section"])
    sub = str(r["recovered_subcategory"])
    title = str(r["recovered_title"])
    low = title.casefold()
    priority = "P1"
    disposition = "merged_successor"
    state = "needs_current_reconciliation"
    routes = list(NARRATIVE)
    flags: list[str] = []

    if section == "CrownThrive HQ":
        if sub == "Collab Portal":
            state, priority, routes = "governance_sovereignty_claim_reconciliation", "P0", list(COLLAB)
            flags += ["no_nation_state_or_sovereign_legal_status_from_legacy_title"]
        elif sub == "Business & Legal Templates":
            state, priority, routes = "legal_template_reconciliation", "P0", list(LEGAL)
            flags += ["current_legal_review_required_before_use"]
        elif sub == "Provisional Patents Hub":
            state, priority, routes = "patent_ip_claim_reconciliation", "P0", list(IP)
            flags += ["no_filing_pending_grant_or_scope_claim_from_legacy_title"]
        elif sub == "Business Plans/Prospectuses":
            if any(k in low for k in ["investor", "prospectus", "valuation", "economic architecture"]):
                state, priority, routes = "investment_financial_claim_reconciliation", "P0", list(INVEST)
                flags += ["investment_securities_and_valuation_review_required"]
                if "investor prospectus" in low:
                    disposition = "restricted_record"
            elif "chlom" in low or "lex" in low:
                state, priority = "chlom_economic_governance_reconciliation", "P0"
                routes = ["/chlom/overview", "/chlom/dla-dail-lex", "/commerce/thriveevergreen"]
                flags += ["no_exchange_license_or_economic_authority_from_legacy_title"]
            elif any(k in low for k in ["infrastructure", "sovereign web", "sovereign compute"]):
                state, routes = "infrastructure_architecture_reconciliation", list(INFRA)
                flags += ["target_architecture_not_deployment_proof"]
            elif "hybrid incubator" in low or "thrivealumni" in low:
                state = "program_lineage_reconciliation"
                routes = ["/doctrine/hybrid-incubator", "/governance/thrivealumni-governance-lineage", "/doctrine/convergent-ecosystem"]
            else:
                state, routes = "institutional_narrative_reconciliation", list(NARRATIVE)
        elif sub == "Corporate Playbooks":
            if "confidential algorithm" in low:
                state, priority, disposition, routes = "restricted_algorithm_ops_reconciliation", "P0", "restricted_record", list(RESTRICTED)
            elif "sovereign web" in low:
                state, routes = "infrastructure_architecture_reconciliation", list(INFRA)
            elif "moat" in low or "defensibility" in low:
                state, priority, routes = "ip_defensibility_reconciliation", "P0", list(IP)
            elif "founder" in low:
                state, routes = "founder_doctrine_reconciliation", ["/doctrine/founder-doctrine-and-code", "/knowledge/source-authority-hierarchy", "/knowledge/restricted-source-register"]
            else:
                state, routes = "operating_playbook_reconciliation", ["/doctrine/core-operating-spine", "/standards/run-packet-project-management", "/knowledge/source-authority-hierarchy"]
        elif sub == "Developer Notes":
            state = "historical_release_and_ops_reconciliation"
            if "internal only" in low:
                priority, disposition, routes = "P0", "restricted_record", ["/knowledge/restricted-source-register", "/platforms/locticians-institutional-registry", "/knowledge/source-authority-hierarchy"]
            elif "locticians" in low and "flipbooks" in low:
                routes = ["/platforms/go-flipbooks-institutional-registry", "/platforms/locticians-institutional-registry", "/knowledge/source-authority-hierarchy"]
            elif "locticians" in low:
                routes = ["/platforms/locticians-institutional-registry", "/support/legal-status-and-historical-claim-supersession", "/knowledge/source-authority-hierarchy"]
                if "release notes" in low:
                    priority, disposition = "P2", "superseded_history"
            elif "mvp" in low or "melanated voices" in low:
                routes = ["/platforms/media-federation-institutional-registry", "/doctrine/cultural-imprint-engine", "/knowledge/source-authority-hierarchy"]
                if "release notes" in low:
                    priority, disposition = "P2", "superseded_history"

    elif section == "Cultural Imprint Engine (CIE)":
        if sub == "Kulture House":
            state, routes = "kulture_house_imprint_reconciliation", list(KULTURE)
            if "valuation" in low:
                priority, disposition = "P0", "restricted_record"
                flags += ["valuation_claim_requires_current_evidence_and_authority"]
        elif sub == "BongedOut!":
            state, priority, routes = "lease_operator_economic_reconciliation", "P0", list(BONGED)
            flags += ["no_lease_franchise_or_operator_authority_from_legacy_title"]
        elif sub == "Luxperiences Network":
            state, routes = "hospitality_imprint_reconciliation", list(LUX)
        elif sub == "ThriveStudio Productions":
            state, priority, disposition, routes = "superseded_studio_alias_reconciliation", "P2", "superseded_history", list(STUDIO)
            flags += ["current_successor_is_crownthrive_studios"]
        else:
            state, priority, routes = "cie_framework_reconciliation", "P0" if sub == "Imprint Framework" else "P1", list(CIE_CORE)
            flags += ["implementation_state_independent_from_framework_definition"]

    elif section == "Hybrid Incubator":
        if sub == "Incubator Membership Tiers":
            state, priority, routes = "membership_license_economic_reconciliation", "P0", list(HYBRID_RIGHTS)
            flags += ["no_phase3_license_membership_or_commerce_activation_from_legacy_title"]
        elif sub == "Partner, Business & Brand Activation":
            state, priority, routes = "cultural_ip_operator_rights_reconciliation", "P0", list(HYBRID_RIGHTS)
            flags += ["no_ip_lease_or_operator_sovereignty_without_current_authority"]
        else:
            state, routes = "incubator_program_playbook_reconciliation", list(HYBRID)
            if "v1.0" in low:
                priority, disposition = "P2", "superseded_history"

    elif section == "Investor Relations":
        if "non‑disclosure" in low or "non-disclosure" in low:
            state, priority, routes = "investor_legal_confidentiality_reconciliation", "P0", list(LEGAL)
            flags += ["current_legal_review_required_before_use"]
        elif "azure" in low:
            state, priority, routes = "investor_comparative_claim_reconciliation", "P0", ["/standards/evidence-claims-and-proof-standard", "/chlom/overview", "/support/legal-status-and-historical-claim-supersession"]
            flags += ["comparative_claim_requires_current_evidence"]
        else:
            state, priority, disposition, routes = "restricted_investor_valuation_scorecard_reconciliation", "P0", "restricted_record", list(INVEST)
            flags += ["no_investment_securities_valuation_or_offer_authority"]

    elif section == "MM Suites":
        if sub == "Suite Pros":
            if "agreement" in low:
                state, priority, routes = "suite_pro_legal_participation_reconciliation", "P0", list(MM_COMM)
                flags += ["agreement_requires_current_legal_version_and_assent_controls"]
            elif "crownrewards" in low or "pilot" in low:
                state, routes = "mm_suites_rewards_pilot_reconciliation", list(MM_REWARDS)
                flags += ["pilot_state_not_production_or_economic_truth"]
            else:
                state, routes = "suite_pro_onboarding_reconciliation", list(MM)
        elif sub in {"Franchisees", "Regional Licensees"}:
            state, priority, routes = "franchise_regional_license_reconciliation", "P0", list(MM_COMM)
            flags += ["no_franchise_offer_license_or_income_claim_without_current_legal_authority"]
        elif sub == "Corporate Ops Manual":
            if "master docs ledger" in low:
                state, priority, disposition, routes = "restricted_internal_docs_ledger_reconciliation", "P0", "restricted_record", list(MM_DOCS)
            elif "prospectus" in low or "investor" in low:
                state, priority, disposition, routes = "restricted_mm_suites_investor_reconciliation", "P0", "restricted_record", list(MM_COMM)
                flags += ["no_investment_or_franchise_offer_from_legacy_title"]
            else:
                state, routes = "mm_suites_flywheel_reconciliation", ["/doctrine/thrive-flywheel", "/corridors/mm-suites-lineage-and-current-state", "/corridors/mm-suites-phygital-operating-spine"]
        elif sub == "Corporate":
            if any(k in low for k in ["prospectus", "income protection"]):
                state, priority, routes = "mm_suites_financial_franchise_claim_reconciliation", "P0", list(MM_COMM)
                flags += ["financial_franchise_and_income_claim_review_required"]
                if "prospectus" in low:
                    disposition = "restricted_record"
            else:
                state, routes = "mm_suites_corporate_identity_reconciliation", list(MM)

    elif section == "Thrive Flywheel":
        if sub == "Governance and Compliance Loop":
            state, priority, routes = "flywheel_governance_compliance_reconciliation", "P0", list(FW_GOV)
        elif sub == "Incubator and Partner Pathways":
            state, routes = "flywheel_incubator_pathways_reconciliation", list(FW_INC)
        elif sub == "Tools, Frameworks and Engines":
            state, routes = "flywheel_tools_frameworks_reconciliation", list(FW_TOOLS)
        elif sub.startswith("TF "):
            state, routes = "flywheel_research_paper_family_reconciliation", list(FW_PAPERS)
        else:
            state, routes = "flywheel_operating_model_reconciliation", list(FW)

    routes = list(dict.fromkeys(routes))
    missing = [x for x in routes if not route_exists(x)]
    if missing:
        flags.append("candidate_route_missing")
    return {
        "article_id": r["article_id"],
        "inventory_id": r["inventory_id"],
        "legacy_order": int(r["recovered_order"]),
        "legacy_section": section,
        "legacy_subcategory": sub,
        "legacy_title": title,
        "body_status": "reconstruction_required",
        "priority": priority,
        "current_state_candidate": state,
        "disposition_candidate": disposition,
        "target_routes": routes,
        "missing_target_routes": missing,
        "flags": flags,
        "review_state": "candidate_requires_evidence_review",
        "terminal_disposition_authorized": False,
        "phase_3_seed_impact": "knowledge_dependency_only_no_entry_authority",
        "phase_impact_1_20": phase_vector(),
    }


def build() -> dict[str, Any]:
    all_records = load_records()
    scope = [r for r in all_records if r.get("recovered_section") not in ALREADY_MAPPED]
    if len(scope) != 94:
        raise ValueError(f"expected 94 final records, found {len(scope)}")
    section_counts = Counter(str(r["recovered_section"]) for r in scope)
    if dict(section_counts) != EXPECTED_SECTIONS:
        raise ValueError(f"unexpected final section counts: {dict(section_counts)}")
    rows = [classify(r) for r in scope]
    if len({r["inventory_id"] for r in rows}) != 94:
        raise ValueError("duplicate inventory IDs")
    if any(r["terminal_disposition_authorized"] for r in rows):
        raise ValueError("terminal dispositions may not self-authorize")
    if any(r["body_status"] != "reconstruction_required" for r in rows):
        raise ValueError("missing historical bodies may not be promoted as recovered")
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "record_id": "ct.docs.sprint6.final94.crosswalk.2026-08-23.v1",
        "sprint_id": "ct.docs.freshness.2026-08-23.s6",
        "framework_id": "ct.framework.documentation-reconciliation-continuity",
        "source_universe_count": 795,
        "records": rows,
        "summary": {
            "records": 94,
            "section_counts": dict(sorted(section_counts.items())),
            "priority_counts": dict(sorted(Counter(r["priority"] for r in rows).items())),
            "disposition_candidate_counts": dict(sorted(Counter(r["disposition_candidate"] for r in rows).items())),
            "current_state_candidate_counts": dict(sorted(Counter(r["current_state_candidate"] for r in rows).items())),
            "missing_target_route_rows": sum(bool(r["missing_target_routes"]) for r in rows),
            "restricted_candidate_rows": sum(r["disposition_candidate"] == "restricted_record" for r in rows),
            "candidate_crosswalk_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "mapped_candidate_titles_after_sprint_6": 795,
            "remaining_titles_after_sprint_6": 0,
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
            "phase_11_20_state": "reserved_definition_required",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    s = result["summary"]
    print("PASS_HELP_CENTER_FINAL_94_CROSSWALK")
    print("records=94")
    print("section_counts=" + json.dumps(s["section_counts"], ensure_ascii=False, sort_keys=True))
    print("priority_counts=" + json.dumps(s["priority_counts"], sort_keys=True))
    print("disposition_candidate_counts=" + json.dumps(s["disposition_candidate_counts"], sort_keys=True))
    print("current_state_candidate_counts=" + json.dumps(s["current_state_candidate_counts"], sort_keys=True))
    print(f"missing_target_route_rows={s['missing_target_route_rows']}")
    print(f"restricted_candidate_rows={s['restricted_candidate_rows']}")
    print(f"candidate_crosswalk_sha256={s['candidate_crosswalk_sha256']}")
    print("mapped_candidate_titles=795")
    print("remaining_titles=0")
    print(f"phase_3_entry={s['phase_3_entry']}")
    if args.write:
        out = ROOT / "data/documentation/sprint-6-final-94-crosswalk.v1.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote={out.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
