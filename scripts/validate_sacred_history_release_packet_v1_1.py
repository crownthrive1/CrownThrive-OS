#!/usr/bin/env python3
"""Validate the Phase 3 Sacred History source packet without treating projection lag as authority."""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/sacred-history-release-packet.v1.1.json"
SOURCES = ROOT / "knowledge/sacred-history-source-register.mdx"
ASSETS = ROOT / "knowledge/curriculum-study-asset-register.mdx"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    manifest = json.loads(read(MANIFEST))
    sources = read(SOURCES)
    assets = read(ASSETS)

    if manifest.get("manifest_version") != "1.1.0" or manifest.get("institutional_phase") != "3":
        fail("manifest version/phase drift")
    if manifest.get("canonical_content_id") != "ct.content.sacred-history":
        fail("content identity drift")

    authority = manifest["authority"]
    if authority.get("autonomy_ceiling") != "A2" or authority.get("delegation_ceiling") != "D2":
        fail("authority ceiling drift")
    if not authority.get("d3_human_reserved"):
        fail("D3 must remain human-reserved")
    for key in ("self_approval_allowed", "authority_manufacture_allowed", "economic_authority_manufacture_allowed"):
        if authority.get(key) is not False:
            fail(f"authority prohibition drift: {key}")

    expected_sources = {f"S{i}" for i in range(124, 132)}
    present = set(re.findall(r"^\| `(S\d+)` \|", sources, flags=re.MULTILINE))
    if not expected_sources.issubset(present):
        fail("source register must include S124-S131")
    if set(manifest["source_lineage"]["public_source_refs"]) != expected_sources:
        fail("manifest/source register mismatch")

    snapshot = manifest["historical_wave1_snapshot"]
    if snapshot.get("blueprint_count") != 1000 or snapshot.get("strict_finished_product_count") != 0:
        fail("Wave-1 blueprint/completion accounting drift")
    if snapshot.get("source_checkout_is_current_status_claim") is not False:
        fail("historical HTTP-500 observation may not be promoted to current truth")

    gates = manifest["current_gates"]
    if gates.get("chlom_rights") != "HOLD" or gates.get("new_checkout") is not False:
        fail("rights/checkout fail-closed boundary drift")
    for key in ("new_provider_writes", "wallet_or_credit_movements", "new_entitlements", "new_production_route_count_claimed"):
        if gates.get(key) != 0:
            fail(f"unsupported effect introduced: {key}")

    penta = manifest["penta_binding"]
    if penta.get("commerce_economic_activation") != "PentaGreen" or penta.get("authority_inheritance") is not False:
        fail("PentaGreen/authority binding drift")

    if "ct.content.sacred-history" not in assets or "PentaGreen" not in assets:
        fail("asset register missing current Sacred History/PentaGreen binding")

    public_text = "\n".join([read(MANIFEST), sources, assets])
    for pattern in (r"SUPABASE_SERVICE_ROLE_KEY", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"(?i)access[_ -]?token\s*[:=]"):
        if re.search(pattern, public_text):
            fail(f"restricted secret pattern detected: {pattern}")

    print(json.dumps({
        "status": "PASS",
        "manifest": manifest["manifest_id"],
        "sources": len(expected_sources),
        "historical_blueprints": snapshot["blueprint_count"],
        "historical_finished_products": snapshot["strict_finished_product_count"],
        "current_chlom": gates["chlom_rights"],
        "penta_green": gates["penta_green_activation"],
        "global_storefront_hold": manifest["core_property"]["global_storefront_hold"]
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
