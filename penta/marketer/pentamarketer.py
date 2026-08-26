#!/usr/bin/env python3
"""PentaMarketer: governed campaign manifest compiler for CrownThrive."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
SCRIBE_PATH = SCRIPT_DIR.parent / "scribe" / "pentascribe.py"
FEDERATION_GOVERNANCE_PATH = SCRIPT_DIR.parent / "scribe" / "federation_governance.py"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


scribe = load_module("pentascribe_for_marketer", SCRIBE_PATH)
federation_governance = load_module("pentascribe_federation_governance_for_marketer", FEDERATION_GOVERNANCE_PATH)


def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def vocabulary(registry: dict, sources: dict | None = None) -> dict:
    return scribe.build_federated_vocabulary(registry, sources)


def resolve_terms(names, registry: dict, sources: dict | None = None):
    vocab = vocabulary(registry, sources)
    resolved, unknown = [], []
    for name in names:
        term = vocab.get(scribe.semantic_key(name))
        if not term:
            unknown.append(name)
        else:
            resolved.append({
                "input": name,
                "id": term["id"],
                "canonical": term["canonical"],
                "authority": term["authority"],
                "authority_source": term["source_path"],
            })
    return resolved, unknown


def registered_mark_forms(registry):
    forms = set()
    for term in registry.get("terms", []):
        tm = term.get("trademark") or {}
        if tm.get("status") != "registered" or not tm.get("registration"):
            continue
        for name in [term.get("canonical", ""), *(term.get("aliases") or [])]:
            bare = name.replace("™", "").replace("®", "").strip()
            if bare:
                forms.add(bare + "®")
    return sorted(forms, key=len, reverse=True)


def unverified_registered_symbol_use(message, registry):
    remainder = message
    for form in registered_mark_forms(registry):
        remainder = re.sub(re.escape(form), "", remainder, flags=re.I)
    return "®" in remainder


def validate_campaign(campaign, registry, policy, sources: dict | None = None):
    errors = []
    for key in ("campaign_id", "objective", "audience", "message", "cta", "channels", "terms", "cie_imprint", "chlom_authority_ref"):
        if not campaign.get(key):
            errors.append(f"missing {key}")
    if sources:
        try:
            audit = federation_governance.audit_federation(registry, sources)
        except (ValueError, FileNotFoundError) as exc:
            errors.append(f"PentaScribe federation audit unavailable: {exc}")
            audit = None
        if audit and audit["result"] != "PASS":
            errors.append(f"PentaScribe federation authority conflict: {audit['conflict_count']} unresolved semantic collision(s)")
    bad_channels = sorted(set(campaign.get("channels", [])) - set(policy.get("channels", [])))
    if bad_channels:
        errors.append(f"unsupported channels: {', '.join(bad_channels)}")
    resolved, unknown = resolve_terms(campaign.get("terms", []), registry, sources)
    if unknown:
        errors.append("unknown/unapproved PentaScribe terms: " + ", ".join(unknown))
    message = " ".join([campaign.get("message", ""), campaign.get("cta", "")])
    for pattern in policy.get("claim_policy", {}).get("blocked_patterns", []):
        if re.search(pattern, message, re.I):
            errors.append(f"blocked claim pattern: {pattern}")
    if "®" in message and unverified_registered_symbol_use(message, registry):
        errors.append("® used for a mark without evidence-backed registered status")
    return errors, resolved


def compile_manifest(campaign, registry, policy, sources: dict | None = None):
    errors, resolved = validate_campaign(campaign, registry, policy, sources)
    if errors:
        raise ValueError("\n".join(errors))
    payload = {
        "schema_version": "1.2.0",
        "campaign_id": campaign["campaign_id"],
        "objective": campaign["objective"],
        "audience": campaign["audience"],
        "message": campaign["message"],
        "cta": campaign["cta"],
        "channels": campaign["channels"],
        "terminology": resolved,
        "semantic_resolution": "pentascribe_federated_governed_v1" if sources else "pentascribe_seed_v1",
        "semantic_authority_gate": "PASS" if sources else "SEED_ONLY",
        "cie_imprint": campaign["cie_imprint"],
        "chlom_authority_ref": campaign["chlom_authority_ref"],
        "publication_state": "PLAN_ONLY",
        "required_handoffs": {
            "distribution": policy["distribution_handoff"],
            "measurement": policy["measurement_handoff"],
            "commerce": policy["commerce_handoff"],
            "documentation": policy["documentation_handoff"],
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "governance_note": "This manifest is not publication authority. Provider writes require certified routes/adapters and applicable CHLOM/CIE gates.",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "compile"])
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--registry", default="penta/scribe/registry.json")
    parser.add_argument("--sources", default="penta/scribe/sources.registry.json")
    parser.add_argument("--policy", default="penta/marketer/policy.json")
    parser.add_argument("--out", default="-")
    args = parser.parse_args(argv)
    campaign = read_json(args.campaign)
    registry = read_json(args.registry)
    policy = read_json(args.policy)
    sources_path = pathlib.Path(args.sources) if args.sources else None
    sources = read_json(sources_path) if sources_path and sources_path.is_file() else None
    errors, _ = validate_campaign(campaign, registry, policy, sources)
    if args.command == "validate":
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print("PASS")
        return 0
    try:
        manifest = compile_manifest(campaign, registry, policy, sources)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    text = json.dumps(manifest, indent=2) + "\n"
    if args.out == "-":
        print(text, end="")
    else:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
