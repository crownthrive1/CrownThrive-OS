#!/usr/bin/env python3
"""Verify the public Generation 6 projection without opening the private archive."""
from pathlib import Path
import hashlib
import json
import sys

root = Path(__file__).resolve().parent.parent / "developers" / "manifests"
manifest_path = root / "chlom-proprietary-asset-factory-v6.public.json"
receipt_path = root / "chlom-proprietary-factory-v6-verification.json"
errors = []

for path in (manifest_path, receipt_path):
    if not path.exists():
        errors.append(f"missing: {path}")
        continue
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid JSON {path}: {exc}")

if not errors:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    counts = manifest.get("counts", {})
    expected = {
        "algorithms_and_capabilities": 1000,
        "skills": 300,
        "prompts": 500,
        "scripts": 300,
        "new_assets": 2100,
        "new_independent_agents": 60,
        "commercialization_candidates": 40,
    }
    for key, value in expected.items():
        if counts.get(key) != value:
            errors.append(f"{key}: expected {value}, observed {counts.get(key)}")
    gates = manifest.get("release_gates", {})
    for key in ("production_activation", "checkout_activation", "money_movement"):
        if gates.get(key) != "HOLD":
            errors.append(f"{key} must remain HOLD")
    if manifest.get("custody", {}).get("secret_values_exposed") is not False:
        errors.append("secret_values_exposed must be false")

if errors:
    print(json.dumps({"state": "FAIL", "errors": errors}, indent=2))
    sys.exit(1)

print(json.dumps({
    "state": "PASS",
    "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    "verification_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest()
}, indent=2))
