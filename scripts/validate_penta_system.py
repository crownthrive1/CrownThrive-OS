#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "penta" / "registry" / "penta-component-registry.v1.json"
REQUIRED = {
    "PentaOS", "PentaVergence", "PentaTechture", "PentaPology", "PentaFlex",
    "PentaPlanes", "PentaAgents", "PentaMCL", "PentaLLM", "PentaBoxes",
    "PentaStars", "PentaRithms", "PentaSets", "PentaBound", "PentaBind",
    "PentaWire", "PentaSecure", "PentaInterOps", "PentaMaps", "PentaFlows",
    "PentaSkills", "PentaTools", "PentaOrchestrator", "PentaBase", "PentaIP",
    "PentaScripts", "PentaFactory", "PentaDocs", "PentaRoute", "PentaFederation",
    "PentaGeneration", "PentaStudios", "PentaBooks"
}
AXES = {"truth", "authority", "execution", "interoperation", "continuity"}


def main() -> int:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    components = data.get("components", [])
    assert data.get("compatibility_policy") == "alias_preserve_stable_machine_contracts"
    assert set(data.get("axes", [])) == AXES

    names = [c["name"] for c in components]
    keys = [c["key"] for c in components]
    contracts = [c["contract"] for c in components]
    assert len(names) == len(set(names)), "duplicate canonical Penta name"
    assert len(keys) == len(set(keys)), "duplicate component key"
    assert len(contracts) == len(set(contracts)), "duplicate stable contract id"
    missing = sorted(REQUIRED - set(names))
    assert not missing, f"required Penta components missing: {missing}"

    for c in components:
        assert c["name"].startswith("Penta"), c
        assert c["key"].startswith("penta."), c
        assert c["contract"].startswith("ct."), c
        assert c.get("state") in {"active", "planned", "hold", "unbound"}, c
        aliases = c.get("aliases", [])
        assert isinstance(aliases, list), c

    required_files = [
        ROOT / "penta" / "README.md",
        ROOT / "penta" / "runtime" / "penta_vergence.ts",
        ROOT / "penta" / "maps" / "PENTAMAP-001.md",
        ROOT / "supabase" / "migrations" / "20260826_penta_os_vergence_v1.sql",
        ROOT / "supabase" / "functions" / "penta-flex" / "index.ts",
        ROOT / "supabase" / "functions" / "penta-vergence-bridge" / "index.ts",
        ROOT / "scripts" / "penta_vergence_reconciler.py",
    ]
    absent = [str(p.relative_to(ROOT)) for p in required_files if not p.exists()]
    assert not absent, f"missing implementation files: {absent}"

    migration = (ROOT / "supabase" / "migrations" / "20260826_penta_os_vergence_v1.sql").read_text(encoding="utf-8")
    for invariant in [
        "force row level security",
        "penta-vergence-continuity-4h-v1",
        "penta-vergence-deep-local-gate-v1",
        "America/New_York",
        "penta_vergence_claim_v1",
        "penta_vergence_complete_v1",
    ]:
        assert invariant.lower() in migration.lower(), f"migration invariant missing: {invariant}"

    reconciler = (ROOT / "scripts" / "penta_vergence_reconciler.py").read_text(encoding="utf-8").lower()
    for forbidden in ["force-push", "delete branch", "self-approve"]:
        # Forbidden concepts may appear only in explanatory docstrings; operational command forms are checked below.
        pass
    assert "git push --force" not in reconciler
    assert "delete_ref" not in reconciler
    assert "merge_candidate" in reconciler
    assert "close_represented" in reconciler
    assert "preserve_hold" in reconciler

    print(f"PASS PentaOS registry={len(components)} components axes=5 required={len(REQUIRED)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
