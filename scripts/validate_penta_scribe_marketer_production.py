#!/usr/bin/env python3
"""Validate the promoted PentaScribe/PentaMarketer production control plane."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "penta/registry/penta-component-registry.v1.json"
EXTENSION = ROOT / "data/penta/systems.extensions.pentascribe-marketer.json"
INTEGRATION = ROOT / "data/penta/pentascribe-marketer.integration.json"
ADAPTERS = ROOT / "penta/marketer/adapters.registry.json"
WORKFLOW = ROOT / ".github/workflows/penta-scribe-marketer-production.yml"
DOC = ROOT / "docs/phase3/PENTASCRIBE_PENTAMARKETER_PRODUCTION.md"


def load(path: Path) -> dict:
    assert path.is_file(), f"missing {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    components = load(COMPONENTS)
    by_key = {c["key"]: c for c in components.get("components", [])}
    assert by_key["penta.scribe"]["state"] == "active"
    assert by_key["penta.scribe"]["contract"] == "ct.penta.scribe.v1"
    assert by_key["penta.marketer"]["state"] == "active"
    assert by_key["penta.marketer"]["contract"] == "ct.penta.marketer.v1"

    extension = load(EXTENSION)
    systems = {s["machine_key"]: s for s in extension.get("systems", [])}
    for key in ("penta.scribe", "penta.marketer"):
        assert systems[key]["maturity"] == "production"
        assert systems[key]["production_scope"]
        assert systems[key]["runtime_ref"]
    production_evidence = extension.get("production_evidence", {})
    assert production_evidence.get("first_verified_run_id") == 32944441770
    assert production_evidence.get("first_verified_head_sha") == "760d940fa4032d3bcd81928b63debd8150b4e46c"
    assert len(production_evidence.get("artifact_sha256", "")) == 64

    integration = load(INTEGRATION)
    assert integration.get("status") == "production_control_plane"
    runtime = integration.get("runtime", {})
    assert runtime.get("production_workflow") == ".github/workflows/penta-scribe-marketer-production.yml"
    assert runtime.get("schedule") == "23 * * * *"
    assert runtime.get("first_verified_artifact_id") == 9597699054
    assert len(runtime.get("first_verified_artifact_sha256", "")) == 64
    assert integration["governance"]["publication_authority"] == "certified downstream provider route only"

    adapters = load(ADAPTERS)
    amap = {a["channel"]: a for a in adapters.get("adapters", [])}
    assert set(amap) == {"owned_web", "email", "social", "media", "community", "partner", "paid"}
    for channel in ("email", "social", "paid"):
        assert amap[channel]["state"] == "hold_unbound"
        assert amap[channel]["mutation_authority"] is False
        assert amap[channel]["readback_required"] is True
    for channel in ("owned_web", "media", "community", "partner"):
        assert amap[channel]["execution_mode"] == "artifact_only"
        assert amap[channel]["mutation_authority"] is False

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for fragment in (
        "cron: '23 * * * *'",
        "python penta/scribe/runtime.py cycle",
        "python penta/marketer/runtime.py cycle",
        "retention-days: 30",
    ):
        assert fragment in workflow, f"production workflow missing {fragment}"
    assert DOC.is_file()

    print(json.dumps({
        "status": "PASS",
        "systems": ["PentaScribe", "PentaMarketer"],
        "production_scope": "internal_control_plane",
        "first_verified_run_id": 32944441770,
        "external_provider_mutation": "capability_bound_per_adapter",
        "held_channels": ["email", "social", "paid"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
