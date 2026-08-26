#!/usr/bin/env python3
"""PentaMarketer: governed campaign manifest compiler for CrownThrive."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, sys
from datetime import datetime, timezone

def read_json(path): return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

def vocabulary(registry):
    out = {}
    for term in registry.get("terms", []):
        if term.get("status") not in {"canonical", "draft"}: continue
        for name in [term["canonical"], *(term.get("aliases") or [])]: out[name.casefold().replace("™", "").replace("®", "").strip()] = term
    return out

def resolve_terms(names, registry):
    vocab, resolved, unknown = vocabulary(registry), [], []
    for name in names:
        term = vocab.get(name.casefold().replace("™", "").replace("®", "").strip())
        if not term: unknown.append(name)
        else: resolved.append({"input": name, "id": term["id"], "canonical": term["canonical"]})
    return resolved, unknown

def validate_campaign(campaign, registry, policy):
    errors = []
    for key in ("campaign_id","objective","audience","message","cta","channels","terms","cie_imprint","chlom_authority_ref"):
        if not campaign.get(key): errors.append(f"missing {key}")
    bad_channels = sorted(set(campaign.get("channels", [])) - set(policy.get("channels", [])))
    if bad_channels: errors.append(f"unsupported channels: {', '.join(bad_channels)}")
    resolved, unknown = resolve_terms(campaign.get("terms", []), registry)
    if unknown: errors.append("unknown/unapproved PentaScribe terms: " + ", ".join(unknown))
    message = " ".join([campaign.get("message", ""), campaign.get("cta", "")])
    for pattern in policy.get("claim_policy", {}).get("blocked_patterns", []):
        if re.search(pattern, message, re.I): errors.append(f"blocked claim pattern: {pattern}")
    if "®" in message:
        registered = any((t.get("trademark") or {}).get("status") == "registered" and (t.get("trademark") or {}).get("registration") for t in registry.get("terms", []))
        if not registered: errors.append("® used but registry contains no evidence-backed registered mark")
    return errors, resolved

def compile_manifest(campaign, registry, policy):
    errors, resolved = validate_campaign(campaign, registry, policy)
    if errors: raise ValueError("\n".join(errors))
    payload = {"schema_version": "1.0.0", "campaign_id": campaign["campaign_id"], "objective": campaign["objective"], "audience": campaign["audience"], "message": campaign["message"], "cta": campaign["cta"], "channels": campaign["channels"], "terminology": resolved, "cie_imprint": campaign["cie_imprint"], "chlom_authority_ref": campaign["chlom_authority_ref"], "publication_state": "PLAN_ONLY", "required_handoffs": {"distribution": policy["distribution_handoff"], "measurement": policy["measurement_handoff"], "commerce": policy["commerce_handoff"], "documentation": policy["documentation_handoff"]}, "generated_at": datetime.now(timezone.utc).isoformat(), "governance_note": "This manifest is not publication authority. Provider writes require certified routes/adapters and applicable CHLOM/CIE gates."}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(); payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest(); return payload

def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument("command", choices=["validate", "compile"]); p.add_argument("--campaign", required=True); p.add_argument("--registry", default="penta/scribe/registry.json"); p.add_argument("--policy", default="penta/marketer/policy.json"); p.add_argument("--out", default="-"); args = p.parse_args(argv)
    campaign, registry, policy = read_json(args.campaign), read_json(args.registry), read_json(args.policy)
    errors, _ = validate_campaign(campaign, registry, policy)
    if args.command == "validate":
        if errors: print("\n".join(errors), file=sys.stderr); return 1
        print("PASS"); return 0
    try: manifest = compile_manifest(campaign, registry, policy)
    except ValueError as exc: print(str(exc), file=sys.stderr); return 1
    text = json.dumps(manifest, indent=2) + "\n"
    if args.out == "-": print(text, end="")
    else:
        out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text, encoding="utf-8"); print(out)
    return 0

if __name__ == "__main__": raise SystemExit(main())
