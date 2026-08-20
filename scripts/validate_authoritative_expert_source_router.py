#!/usr/bin/env python3
"""Fail-closed validator for the CrownThrive authoritative expert-source fabric."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers" / "manifests" / "authoritative-expert-source-router.v1.json"
SCHEMA_PATH = ROOT / "developers" / "schemas" / "authoritative-expert-source-router.v1.schema.json"
ROUTER_PATH = ROOT / "scripts" / "expert_source_router.py"

REQUIRED_DOMAINS = {
    "economics_demographics",
    "securities",
    "cybersecurity",
    "legal_regulatory",
    "health_biomedical",
    "energy_environment",
    "procurement_grants",
    "research_scholarship",
    "ip_rights_licensing",
    "accessibility_consumer_protection",
    "standards_protocols",
}

OFFICIAL_HOST_SUFFIXES = {
    "gov", "census.gov", "bls.gov", "bea.gov", "sec.gov", "nist.gov", "cisa.gov",
    "federalregister.gov", "gsa.gov", "regulations.gov", "congress.gov", "nasa.gov",
    "fda.gov", "clinicaltrials.gov", "ncbi.nlm.nih.gov", "eia.gov", "sam.gov",
    "worldbank.org", "w3.org", "copyright.gov", "ftc.gov", "ada.gov",
    "crossref.org", "openalex.org",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)\b(sk-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9]{20,}|api[_-]?key\s*[:=]\s*['\"][^'\"]+)", re.I),
    re.compile(r"(?i)\b(bearer\s+[a-z0-9._-]{20,}|client_secret\s*[:=]\s*['\"][^'\"]+)", re.I),
]


def fail(message: str) -> None:
    raise AssertionError(message)


def host_is_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_HOST_SUFFIXES)


def main() -> int:
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    router_text = ROUTER_PATH.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    json.loads(schema_text)

    if manifest.get("schema_version") != "1.0.0":
        fail("Unexpected schema version.")
    if manifest.get("stable_id") != "ct.capability.authoritative-expert-source-router.v1":
        fail("Stable router ID drift.")
    if manifest.get("program_phase") != "2.99":
        fail("Source fabric may not advance the institutional program phase.")
    if manifest.get("phase_3_entry") != "blocked_pending_phase_2_99_hard_exit":
        fail("Phase 3 must remain blocked.")
    if manifest.get("status") not in {"prepared_not_activated", "controlled_test"}:
        fail("Source fabric cannot be production-active in this Phase 2.99 packet.")

    safety = manifest["safety"]
    if safety.get("provider_mutation") is not False:
        fail("Provider mutation must remain disabled.")
    if safety.get("credential_storage_in_git") is not False:
        fail("Credentials must not be stored in public Git.")
    if set(safety.get("phase_2_99_methods", [])) - {"GET", "HEAD"}:
        fail("Only GET/HEAD are allowed in Phase 2.99.")

    override = [x for x in safety.get("founder_overrides", []) if x.get("provider") == "SoundCloud API"]
    if not override or override[0].get("status") != "removed_by_founder_override":
        fail("The SoundCloud API founder override is missing.")
    lowered = manifest_text.lower()
    if '"source_id": "soundcloud' in lowered or '"api_base": "https://api.soundcloud' in lowered:
        fail("SoundCloud API routing is forbidden by founder override.")

    inheritance = manifest["inheritance"]
    if inheritance.get("scope") != "institution_wide":
        fail("Source fabric must be institution-wide.")
    if inheritance.get("agents") != "all_registered_agents":
        fail("All registered agents must inherit source routing.")
    if inheritance.get("projects") != "all_current_and_future_crownthrive_projects":
        fail("All current and future CrownThrive projects must inherit source routing.")

    tools = {tool["tool"]: tool for tool in manifest["mcp_contracts"]}
    required_tools = {
        "expert_sources.route",
        "expert_sources.search",
        "expert_sources.fetch",
        "expert_sources.health",
    }
    if set(tools) != required_tools:
        fail(f"MCP contract set drift: {set(tools)}")
    for tool in tools.values():
        if tool["mode"] not in {"read_only", "local_read_only"}:
            fail(f"Non-read-only MCP contract: {tool['tool']}")
        if tool["state"] == "active":
            fail(f"MCP contract cannot be active in this packet: {tool['tool']}")

    profiles = manifest["domain_profiles"]
    missing_domains = REQUIRED_DOMAINS - set(profiles)
    if missing_domains:
        fail(f"Required domain profiles missing: {sorted(missing_domains)}")

    sources = manifest["sources"]
    if len(sources) < 15:
        fail("Insufficient source diversity.")
    ids = [source["source_id"] for source in sources]
    if len(ids) != len(set(ids)):
        fail("Duplicate source IDs.")
    by_id = {source["source_id"]: source for source in sources}

    for source in sources:
        if not source["documentation_url"].startswith("https://"):
            fail(f"Non-HTTPS documentation URL: {source['source_id']}")
        if source["authority_class"] != "open_secondary" and not host_is_allowed(source["documentation_url"]):
            fail(f"Unrecognized authoritative host: {source['source_id']} -> {source['documentation_url']}")
        api_base = source.get("api_base")
        if api_base is not None and not api_base.startswith("https://"):
            fail(f"Non-HTTPS API base: {source['source_id']}")
        if set(source["allowed_methods"]) - {"GET", "HEAD"}:
            fail(f"Write-capable source record: {source['source_id']}")
        if not source.get("claim_scope"):
            fail(f"Missing claim scope: {source['source_id']}")

    for domain, profile in profiles.items():
        if not profile["sources"]:
            fail(f"Empty source profile: {domain}")
        unknown = set(profile["sources"]) - set(by_id)
        if unknown:
            fail(f"Profile {domain} references unknown sources: {sorted(unknown)}")

    high = set(safety["high_consequence_domains"])
    for required in {"legal_regulatory", "securities", "health_biomedical", "ip_rights_licensing", "cybersecurity"}:
        if required not in high:
            fail(f"High-consequence classification missing: {required}")
        if "review" not in profiles[required]["review_policy"]:
            fail(f"High-consequence profile lacks explicit review: {required}")

    for pattern in SECRET_PATTERNS:
        if pattern.search(manifest_text + schema_text + router_text):
            fail("Credential-shaped value detected.")

    sys.path.insert(0, str(ROOT / "scripts"))
    import expert_source_router  # type: ignore

    security_route = expert_source_router.route(task="Check a CVE against known exploited vulnerabilities")
    if security_route["domain"] != "cybersecurity":
        fail("Cybersecurity routing failed.")
    if security_route["provider_mutation_allowed"] is not False:
        fail("Routing unexpectedly allows provider mutation.")
    if not security_route["high_consequence"]:
        fail("Cybersecurity route must be high-consequence.")

    legal_route = expert_source_router.route(task="Review a new federal regulation and compliance implications")
    if legal_route["domain"] != "legal_regulatory":
        fail("Legal/regulatory routing failed.")
    if "federal_register" not in {s["source_id"] for s in legal_route["sources"]}:
        fail("Federal Register missing from legal/regulatory route.")

    research_route = expert_source_router.route(task="Find peer-reviewed papers and DOI metadata")
    if research_route["domain"] != "research_scholarship":
        fail("Research routing failed.")

    print(
        "PASS authoritative expert-source fabric: "
        f"{len(sources)} sources, {len(profiles)} domain profiles, "
        f"{len(tools)} MCP contracts, Phase 3 remains blocked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
