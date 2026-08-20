#!/usr/bin/env python3
"""Deterministic, read-only router for CrownThrive authoritative expert sources.

This module performs no network calls and accepts no credentials. It maps a task
or explicit domain to the approved source catalog and emits a public-safe routing
plan. Provider adapters remain separately gated.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "developers" / "manifests" / "authoritative-expert-source-router.v1.json"

KEYWORD_DOMAINS = {
    "economics_demographics": {
        "economy", "economic", "gdp", "inflation", "labor", "employment",
        "population", "demographic", "census", "income", "industry"
    },
    "securities": {
        "sec", "securities", "filing", "edgar", "issuer", "public company",
        "10-k", "10-q", "8-k", "xbrl"
    },
    "cybersecurity": {
        "cve", "vulnerability", "vulnerabilities", "cybersecurity", "security",
        "exploit", "kev", "cvss", "patch"
    },
    "legal_regulatory": {
        "law", "legal", "regulation", "regulatory", "rule", "rules",
        "federal register", "congress", "statute", "docket", "compliance"
    },
    "health_biomedical": {
        "health", "medical", "drug", "device", "clinical", "trial",
        "biomedical", "fda", "pubmed"
    },
    "energy_environment": {
        "energy", "electricity", "oil", "gas", "generation", "nasa", "earth",
        "environment"
    },
    "procurement_grants": {
        "procurement", "contract", "contracts", "sam.gov", "solicitation",
        "federal opportunity", "government opportunity"
    },
    "research_scholarship": {
        "paper", "papers", "study", "studies", "research", "doi", "journal",
        "citation", "scholarship", "literature"
    },
    "ip_rights_licensing": {
        "copyright", "license", "licensing", "rights", "ip", "intellectual property",
        "royalty", "ownership", "permission"
    },
    "accessibility_consumer_protection": {
        "accessibility", "ada", "consumer protection", "advertising claim",
        "deceptive", "disclosure", "wcag"
    },
    "standards_protocols": {
        "standard", "standards", "nist", "w3c", "protocol", "specification",
        "framework"
    },
}


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def infer_domain(task: str, manifest: dict[str, Any]) -> str:
    normalized = re.sub(r"\s+", " ", task.lower()).strip()
    scores: dict[str, int] = {}
    for domain, keywords in KEYWORD_DOMAINS.items():
        score = sum(2 if " " in kw and kw in normalized else 1 for kw in keywords if kw in normalized)
        if score:
            scores[domain] = score

    if scores:
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]

    if "open_entity_research" in manifest["domain_profiles"]:
        return "open_entity_research"
    raise ValueError("No routable domain found and no discovery fallback is configured.")


def route(task: str | None = None, domain: str | None = None, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    selected_domain = domain or infer_domain(task or "", manifest)

    if selected_domain not in manifest["domain_profiles"]:
        raise ValueError(f"Unknown domain: {selected_domain}")

    profile = manifest["domain_profiles"][selected_domain]
    by_id = {source["source_id"]: source for source in manifest["sources"]}
    selected_sources = [by_id[source_id] for source_id in profile["sources"]]

    return {
        "router_id": manifest["stable_id"],
        "router_status": manifest["status"],
        "program_phase": manifest["program_phase"],
        "phase_3_entry": manifest["phase_3_entry"],
        "domain": selected_domain,
        "review_policy": profile["review_policy"],
        "high_consequence": selected_domain in manifest["safety"]["high_consequence_domains"],
        "provider_mutation_allowed": manifest["safety"]["provider_mutation"],
        "sources": [
            {
                "source_id": source["source_id"],
                "name": source["name"],
                "authority_class": source["authority_class"],
                "documentation_url": source["documentation_url"],
                "api_base": source["api_base"],
                "auth_mode": source["auth_mode"],
                "runtime_state": source["runtime_state"],
                "claim_scope": source["claim_scope"],
            }
            for source in selected_sources
        ],
        "evidence_requirement": manifest["evidence_envelope"]["required_fields"],
        "runtime_note": (
            "This is a routing plan, not proof that a CrownThrive provider adapter, "
            "credential, entitlement, or deployed integration is active."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Route a task to CrownThrive authoritative expert sources.")
    parser.add_argument("--task", help="Natural-language task description.")
    parser.add_argument("--domain", help="Explicit domain profile.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    if not args.task and not args.domain:
        parser.error("Provide --task or --domain.")

    print(json.dumps(route(task=args.task, domain=args.domain, manifest_path=args.manifest), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
