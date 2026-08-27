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
    "PentaScripts", "PentaFactory", "PentaDocs", "PentaScribe", "PentaMarketer",
    "PentaRoute", "PentaFederation", "PentaGeneration", "PentaStudios", "PentaBooks"
}
AXES = {"truth", "authority", "execution", "interoperation", "continuity"}
PENTAROUTE_PRIMITIVES = {
    "PentaTun", "PentaBeata", "PentaFetch", "PentaGet", "PentaHead", "PentaOptions",
    "PentaPost", "PentaPut", "PentaPatch", "PentaDelete", "PentaQuery", "PentaSearch",
    "PentaRead", "PentaList", "PentaParse", "PentaTransform", "PentaValidate", "PentaResolve",
    "PentaObserve", "PentaCache", "PentaSync", "PentaIngest", "PentaImport", "PentaExport",
    "PentaSnapshot", "PentaCreate", "PentaUpdate", "PentaUpsert", "PentaQueue", "PentaRetry",
    "PentaDispatch", "PentaSchedule", "PentaLock", "PentaReconcile", "PentaRollback", "PentaBind",
    "PentaHook", "PentaEvent", "PentaStream", "PentaVault", "PentaAuth", "PentaSign",
    "PentaCertify", "PentaAudit", "PentaTest", "PentaCompile", "PentaGenerate", "PentaDeploy",
    "PentaRelease", "PentaDiscover"
}


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

    by_name = {c["name"]: c for c in components}
    assert by_name["PentaScribe"]["axis"] == "truth"
    assert by_name["PentaScribe"]["contract"] == "ct.penta.scribe.v1"
    assert by_name["PentaMarketer"]["axis"] == "execution"
    assert by_name["PentaMarketer"]["contract"] == "ct.penta.marketer.v1"

    route = by_name["PentaRoute"]
    assert route["contract"] == "ct.penta.route.v3"
    assert not (PENTAROUTE_PRIMITIVES & set(route.get("aliases", []))), "PentaRoute primitives are distinct route-member identities, not umbrella aliases"
    assert set(route.get("primitives", [])) == PENTAROUTE_PRIMITIVES, "PentaRoute primitive membership drift"

    required_files = [
        ROOT / "penta" / "README.md",
        ROOT / "penta" / "runtime" / "penta_vergence.ts",
        ROOT / "penta" / "runtime" / "evidence.py",
        ROOT / "penta" / "scribe" / "pentascribe.py",
        ROOT / "penta" / "scribe" / "federation_governance.py",
        ROOT / "penta" / "scribe" / "runtime.py",
        ROOT / "penta" / "marketer" / "pentamarketer.py",
        ROOT / "penta" / "marketer" / "runtime.py",
        ROOT / "penta" / "marketer" / "adapters.registry.json",
        ROOT / "penta" / "maps" / "PENTAMAP-001.md",
        ROOT / "supabase" / "functions" / "penta-flex" / "index.ts",
        ROOT / "supabase" / "functions" / "penta-vergence-bridge" / "index.ts",
        ROOT / "scripts" / "penta_vergence_reconciler.py",
    ]
    absent = [str(p.relative_to(ROOT)) for p in required_files if not p.exists()]
    assert not absent, f"missing implementation files: {absent}"

    bridge = (ROOT / "supabase" / "functions" / "penta-vergence-bridge" / "index.ts").read_text(encoding="utf-8").lower()
    for invariant in [
        "penta-vergence",
        "penta_vergence_claim_v1",
        "penta_vergence_complete_v1",
        "crownthrive1/crownthrive-os",
        "repository_id",
        "oidc",
    ]:
        assert invariant.lower() in bridge, f"PentaVergence bridge invariant missing: {invariant}"
    retired_slug = "crownthrive-" + "support"
    assert retired_slug not in bridge, "active PentaVergence bridge must not target retired repository identity"

    reconciler = (ROOT / "scripts" / "penta_vergence_reconciler.py").read_text(encoding="utf-8").lower()
    assert "git push --force" not in reconciler
    assert "delete_ref" not in reconciler
    assert "merge_candidate" in reconciler
    assert "close_represented" in reconciler
    assert "preserve_hold" in reconciler

    print(f"PASS PentaOS registry={len(components)} components axes=5 required={len(REQUIRED)} route_primitives={len(PENTAROUTE_PRIMITIVES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
