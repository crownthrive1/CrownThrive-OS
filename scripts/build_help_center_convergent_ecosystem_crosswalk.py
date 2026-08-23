#!/usr/bin/env python3
"""Build the Sprint 5 Convergent Ecosystem 206-title candidate crosswalk.

This decodes the protected 795-title Help Center bundle, isolates exactly the
Convergent Ecosystem section, classifies stale/current/historical state, and
assigns current continuity routes without claiming recovery of missing bodies
or self-authorizing terminal dispositions.
"""
from __future__ import annotations
import argparse, base64, gzip, hashlib, json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/help_center_article_manifest.v1.bundle.json"
TARGET = "Convergent Ecosystem"

CORE = ["/ecosystem/platform-registry", "/portfolio/platform-state-register", "/ecosystem/flows-and-handoffs"]
LONG_TAIL = ["/ecosystem/platform-registry", "/portfolio/platform-state-register", "/support/legal-status-and-historical-claim-supersession"]
COMMERCE = ["/commerce/thriveevergreen", "/commerce/payment-and-fulfillment", "/ecosystem/platform-registry"]
API = ["/developers/platform-api-adapter-matrix", "/technology/phase-3-readiness-gate", "/ecosystem/platform-registry"]
MEDIA = ["/ecosystem/platform-registry", "/portfolio/platform-state-register", "/doctrine/cultural-imprint-engine"]
STATUS = ["/technology/ecosystem-status-resilience", "/technology/security-privacy-continuity", "/ecosystem/platform-registry"]
CHLOM_LEX = ["/chlom/dla-dail-lex", "/commerce/thriveevergreen", "/chlom/lifecycle-and-remedies"]
DOCS = ["/knowledge/documentation-rebuild-coverage-census", "/ecosystem/platform-registry", "/standards/documentation-reconciliation-continuity-framework"]
LEGAL = ["/support/legal-depot-policy-matrix", "/support/legal-status-and-historical-claim-supersession", "/standards/evidence-claims-and-proof-standard"]

SPECIFIC = {
    "AdLuxe Network": "/platforms/adluxe-network-institutional-registry",
    "BrandCards": "/platforms/brandcards-institutional-registry",
    "Crown Affiliates": "/platforms/crown-affiliates-ambassadors-institutional-registry",
    "Crown Ambassadors": "/platforms/crown-affiliates-ambassadors-institutional-registry",
    "CrownFluence": "/platforms/crownfluence-institutional-registry",
    # CrownLytics has a canonical operating-role record in the shared platform registry.
    # Do not invent a dedicated deployment/provider registry until current evidence supports one.
    "CrownLytics": "/ecosystem/platform-registry",
    "CrownPulse": "/platforms/crownpulse-institutional-registry",
    "CrownRewards (My CrownRewards)": "/platforms/crownrewards-institutional-registry",
    "CrownThrive IO": "/technology/crownthrive-io-domain-deployment-certification",
    "CrownThrive Studios": "/platforms/crownthrive-studios-institutional-registry",
    "CrownThriveU": "/platforms/crownthriveu-institutional-registry",
    "Locticians Community & Directory": "/platforms/locticians-institutional-registry",
    # Melanated TV is currently represented inside the governed media-federation record;
    # a standalone deployment registry would overstate provider/runtime evidence.
    "Melanated TV": "/platforms/media-federation-institutional-registry",
    "Melanin Magic": "/platforms/melanin-magic-institutional-registry",
    "Melanin Magic Wholesale": "/platforms/melanin-magic-institutional-registry",
    "Network Status": "/technology/ecosystem-status-resilience",
    "Sermon Toolkit": "/platforms/kjv-visualized-sermon-toolkit-institutional-registry",
    "ThriveGather": "/platforms/thrivegather-institutional-registry",
    "ThrivePeer": "/platforms/thrivepeer-institutional-registry",
    "ThrivePush": "/platforms/thrivepush-institutional-registry",
    "ThriveSeat": "/platforms/thriveseat-institutional-registry",
    "ThriveTickets": "/platforms/thrivetickets-institutional-registry",
    "ThriveTools": "/platforms/thrivetools-institutional-registry",
    "ThriveTools Opt": "/platforms/thrivetools-institutional-registry",
    "ThriveTools SEO": "/platforms/thrivetools-institutional-registry",
    "Virality Music": "/platforms/virality-music-institutional-registry",
}

KNOWN_HISTORICAL = {"Kamora360", "ThriveCafé"}
LONG_TAIL_SUBS = {
    "ChainCliques", "FindCliques", "NFTCliques", "SocialAIly", "XENthrive",
    "Luxperiences", "The Artful Gallery (Wearable Art (Le Galeriste))",
    "The Artful Mane Gallery", "The Mane Experience", "The TAME Gallery",
    "Thrive AI Studio", "ThriveAlumni", "Ecodrive", "Go-Flipbooks",
    "Melanated Stock", "Melanated Vault", "Melanated Voices",
    "Melanated Voices Platform(s) (MVP)", "Melanated Voices TV", "Lyfted Society",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def decode_bundle() -> list[dict[str, Any]]:
    bundle = load_json(BUNDLE)
    encoded = "".join((ROOT / part).read_text(encoding="utf-8").strip() for part in bundle["parts"])
    decoded = json.loads(gzip.decompress(base64.b64decode(encoded)).decode("utf-8"))
    fields = bundle.get("record_encoding", {}).get("fields", [])
    candidates: Any = decoded
    if isinstance(decoded, dict):
        candidates = decoded.get("records", decoded.get("rows", decoded))
        if isinstance(candidates, dict):
            lists = [v for v in decoded.values() if isinstance(v, list) and len(v) == 795]
            if len(lists) != 1:
                raise ValueError("unable to locate unique 795-record list")
            candidates = lists[0]
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
    normalized = route.split("#", 1)[0].strip("/")
    return (ROOT / f"{normalized}.mdx").is_file() or (ROOT / normalized).is_file()


def add_specific(sub: str, routes: list[str], flags: list[str]) -> list[str]:
    specific = SPECIFIC.get(sub)
    if specific:
        if route_exists(specific):
            return [specific] + [r for r in routes if r != specific]
        flags.append("specific_registry_route_missing_using_canonical_fallback")
    return routes


def classify(record: dict[str, Any]) -> dict[str, Any]:
    sub = str(record["recovered_subcategory"])
    title = str(record["recovered_title"])
    low = title.casefold()
    flags: list[str] = []
    priority = "P1"
    disposition = "merged_successor"
    state = "platform_current_state_reconciliation"
    routes = list(CORE)

    if sub in {"60-sec Blurbs", "Glossary"}:
        state = "ecosystem_navigation_and_glossary_reconciliation"
        routes = list(DOCS)

    elif sub == "CHLOM LEX":
        state = "chlom_lex_economic_reconciliation"
        priority = "P0"
        routes = list(CHLOM_LEX)
        flags.append("no_current_exchange_or_economic_authority_from_legacy_title")

    elif sub == "AdLuxe Network":
        state = "advertising_provider_and_commerce_reconciliation"
        priority = "P0"
        routes = list(COMMERCE) + ["/developers/platform-api-adapter-matrix"]
        if any(k in low for k in ["security", "2fa", "permission", "approval", "verification"]):
            flags.append("security_or_access_review_required")
        if any(k in low for k in ["budget", "billing", "payout", "finance", "campaign", "publisher", "advertiser"]):
            flags.append("economic_or_delivery_truth_must_remain_reconciled")

    elif sub == "CrownRewards (My CrownRewards)":
        state = "loyalty_economic_and_member_reconciliation"
        priority = "P0" if any(k in low for k in ["points", "rewards", "errors", "analytics", "qr", "partner"]) else "P1"
        routes = list(COMMERCE)

    elif sub == "CrownThrive IO":
        state = "io_surface_and_machine_contract_reconciliation"
        priority = "P0" if any(k in low for k in ["master standard", "executive", "director", "committee"]) else "P1"
        routes = list(API)

    elif sub == "CrownLytics":
        if any(k in low for k in ["privacy", "terms", "refund", "data processing", "cookie", "disclaimer"]):
            state = "legal_policy_reconciliation"
            priority = "P0"
            routes = list(LEGAL)
        else:
            state = "analytics_platform_reconciliation"
            routes = list(CORE)

    elif sub == "Locticians Community & Directory":
        state = "directory_community_support_reconciliation"
        priority = "P1"
        routes = list(CORE) + ["/developers/platform-api-adapter-matrix"]

    elif sub in {"Melanin Magic", "Melanin Magic Wholesale"}:
        state = "commerce_product_professional_reconciliation"
        priority = "P0" if any(k in low for k in ["confidential", "compliance", "risk", "wholesale", "inventory", "ordering", "certification"]) else "P1"
        routes = list(COMMERCE)
        if "confidential" in low:
            disposition = "restricted_record"
            flags.append("private_or_restricted_projection_required")

    elif sub == "Network Status":
        state = "status_resilience_reconciliation"
        priority = "P0"
        routes = list(STATUS)

    elif sub == "Virality Music":
        if any(k in low for k in ["treasury", "oracle", "valuation", "royalty", "capital"]):
            state = "media_economic_research_reconciliation"
            priority = "P0"
            routes = ["/platforms/virality-music-institutional-registry", "/chlom/dla-dail-lex", "/commerce/thriveevergreen"]
            flags.append("no_financial_or_settlement_authority_from_whitepaper_title")
        else:
            state = "media_platform_reconciliation"
            routes = list(MEDIA)

    elif sub == "ThriveStudio":
        state = "superseded_alias_reconciliation"
        priority = "P2"
        disposition = "superseded_history"
        routes = ["/ecosystem/platform-registry", "/portfolio/platform-state-register", "/support/legal-status-and-historical-claim-supersession"]
        flags.append("current_successor_name_crownthrive_studios")

    elif sub in KNOWN_HISTORICAL:
        state = "historical_or_retired_platform_reconciliation"
        priority = "P2"
        disposition = "superseded_history"
        routes = list(LONG_TAIL)

    elif sub == "Lyfted Society":
        state = "historical_research_or_investment_review_required"
        priority = "P0" if "investor" in low else "P2"
        disposition = "superseded_history"
        routes = list(LONG_TAIL)
        if "investor" in low:
            flags.append("no_investment_or_securities_claim_without_current_authority")

    elif sub in LONG_TAIL_SUBS:
        state = "long_tail_current_state_reconciliation"
        priority = "P1"
        routes = list(LONG_TAIL)
        if any(k in low for k in ["nft", "token", "blockchain", "investor"]):
            priority = "P0"
            flags.append("financial_web3_or_token_review_required")

    elif sub in {"Melanated TV", "Melanated Voices", "Melanated Voices Platform(s) (MVP)", "Melanated Voices TV", "Melanated Stock", "Melanated Vault"}:
        state = "media_brand_lineage_reconciliation"
        routes = list(MEDIA)

    elif sub in {"Crown Affiliates", "Crown Ambassadors"}:
        state = "affiliate_ambassador_economic_reconciliation"
        priority = "P0"
        routes = list(COMMERCE)

    elif sub == "BrandCards":
        state = "brandcards_component_and_identity_reconciliation"
        routes = ["/ecosystem/platform-registry", "/doctrine/cultural-imprint-engine", "/technology/crownthrive-id"]

    elif sub in {"ThriveTools", "ThriveTools Opt", "ThriveTools SEO", "CrownPulse", "ThrivePush", "ThriveSeat", "ThriveGather", "ThrivePeer", "ThriveTickets", "CrownFluence", "CrownThriveU", "Sermon Toolkit", "CrownThrive Studios"}:
        state = "active_platform_capability_reconciliation"
        routes = list(API if sub in {"ThriveTools", "ThriveTools Opt", "ThriveTools SEO", "CrownPulse", "ThrivePush"} else CORE)

    routes = add_specific(sub, routes, flags)
    routes = list(dict.fromkeys(routes))
    missing = [r for r in routes if not route_exists(r)]
    if missing:
        flags.append("candidate_route_missing")

    if "crown thrive" in low:
        flags.append("source_title_spaced_brand_typo_preserved_current_brand_normalized")

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
        "flags": flags,
        "review_state": "candidate_requires_evidence_review",
        "terminal_disposition_authorized": False,
    }


def build() -> dict[str, Any]:
    all_records = decode_bundle()
    scope = [r for r in all_records if r.get("recovered_section") == TARGET]
    if len(scope) != 206:
        raise ValueError(f"expected 206 Convergent Ecosystem records, found {len(scope)}")
    rows = [classify(r) for r in scope]
    if len({r["inventory_id"] for r in rows}) != 206:
        raise ValueError("duplicate inventory IDs")
    if any(r["terminal_disposition_authorized"] for r in rows):
        raise ValueError("terminal dispositions may not self-authorize")
    if any(r["body_status"] != "reconstruction_required" for r in rows):
        raise ValueError("missing historical bodies may not be promoted as recovered")

    priority = Counter(r["priority"] for r in rows)
    disposition = Counter(r["disposition_candidate"] for r in rows)
    states = Counter(r["current_state_candidate"] for r in rows)
    missing_rows = [r for r in rows if r["missing_target_routes"]]
    specific_missing = [r for r in rows if "specific_registry_route_missing_using_canonical_fallback" in r["flags"]]

    result = {
        "schema_version": "1.0.0",
        "crosswalk_id": "ct.docs.help-center.convergent-ecosystem-crosswalk.candidate.v1",
        "sprint": 5,
        "pass": "A_stale_state_reconciliation_candidate",
        "section": TARGET,
        "record_count": 206,
        "source_forensic_universe": 795,
        "summary": {
            "priority_counts": dict(sorted(priority.items())),
            "disposition_candidate_counts": dict(sorted(disposition.items())),
            "current_state_candidate_counts": dict(sorted(states.items())),
            "missing_target_route_rows": len(missing_rows),
            "specific_registry_fallback_rows": len(specific_missing),
        },
        "guardrails": {
            "canonical_brand": "CrownThrive",
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "provider_write_expansion": False,
            "production_activation_created": False,
            "rights_or_economic_authority_created": False,
            "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
            "phase_11_20_state": "reserved_definition_required",
        },
        "records": rows,
    }
    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    result["candidate_crosswalk_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    result = build()
    print("PASS_HELP_CENTER_CONVERGENT_ECOSYSTEM_CROSSWALK")
    print(f"records={result['record_count']}")
    print("priority_counts=" + json.dumps(result["summary"]["priority_counts"], sort_keys=True))
    print("disposition_candidate_counts=" + json.dumps(result["summary"]["disposition_candidate_counts"], sort_keys=True))
    print("current_state_candidate_counts=" + json.dumps(result["summary"]["current_state_candidate_counts"], sort_keys=True))
    print("missing_target_route_rows=" + str(result["summary"]["missing_target_route_rows"]))
    print("specific_registry_fallback_rows=" + str(result["summary"]["specific_registry_fallback_rows"]))
    print("candidate_crosswalk_sha256=" + result["candidate_crosswalk_sha256"])
    print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output={args.output}")
    elif not args.summary_only:
        print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
