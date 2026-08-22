#!/usr/bin/env python3
"""Cross-validate machine-trigger fabric bindings into factory, plugins and Vault."""

from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8"))

FABRIC="developers/manifests/machine-trigger-asset-fabric.v1.json"
PLUGINS="developers/manifests/machine-trigger-plugin-suite.v1.json"
VAULT="developers/manifests/machine-trigger-vault-binding-contract.v1.json"
INTAKE="developers/manifests/machine-trigger-factory-intake.v1.json"

def main()->int:
    f,p,v,i=map(load,(FABRIC,PLUGINS,VAULT,INTAKE))
    assert f["fabric"]==p["fabric_id"]==v["fabric_id"]==i["fabric_id"]=="ct.fabric.machine-trigger-assets.v1"
    assert p["source_manifest"]==v["source_manifest"]==i["source_manifest"]==FABRIC
    assert p["factory_intake_manifest"]==INTAKE
    assert p["vault_binding_contract"]==VAULT
    assert v["plugin_manifest"]==PLUGINS and v["factory_intake_manifest"]==INTAKE
    assert i["plugin_manifest"]==PLUGINS and i["vault_binding_contract"]==VAULT
    assert f["bind"]["plugin_suite"]==p["manifest_id"]
    assert f["bind"]["vault_binding_contract"]==v["binding_id"]
    assert f["bind"]["factory_intake"]==i["manifest_id"]

    triggers=f["triggers"]
    assert len(triggers)==32 and len({r[0] for r in triggers})==32
    assert f["estate"]["trigger_bundles"]==i["trigger_bundle_count"]==v["expected_binding_count"]==32
    assert f["estate"]["derivative_candidates"]==i["derivative_candidate_count"]==128
    assert f["estate"]["authoritative_delta"]==i["authoritative_generation_asset_count_delta"]==0
    assert i["state"]=="CANDIDATE_HOLD_PENDING_GOVERNED_FACTORY_INTAKE"
    assert i["generation_assignment"]=="UNASSIGNED_PENDING_GOVERNED_FACTORY_INTAKE"
    assert i["factory_id"]==f["bind"]["factory"]=="ct.fleet.chlom-proprietary-asset-factory.100k-plus"
    assert i["commercial_derivatives_require_thriveevergreen_ecac"] is True
    assert i["factory_continuation_may_expand_authority"] is False
    assert i["candidate_count_may_be_represented_as_authoritative_before_admission"] is False
    assert "plugin-suite exact binding" in i["admission_requires"]

    expected_plugins={x[0] for x in f["plugins"]}
    actual_plugins={x["plugin_id"] for x in p["plugins"]}
    assert p["plugin_count"]==len(actual_plugins)==5 and actual_plugins==expected_plugins
    assert p["defaults"]=={
      "authority_ceiling":"D2","vote_eligible":False,"quorum_eligible":False,"no_self_approval":True,
      "provider_write_default":False,"production_activation_default":False,"economic_activation_default":False}
    assert p["phase3_scheduled_activation"] is False and p["commerce_scheduled_activation"] is False
    assert p["ecac_non_bypass"] is True
    assert "factory_intake_acceptance" in p["runtime_promotion_requires"]
    assert "vault_binding_readback" in p["runtime_promotion_requires"]

    assert v["binding_id"]==f["vault"]["id"]=="ct.binding.machine-trigger-vault.v1"
    assert v["state"]==f["vault"]["state"]=="PENDING_RUNTIME_BINDING"
    assert v["broker"]==f["vault"]["broker"] and v["gateway"]==f["vault"]["gateway"]
    assert v["profiles"]==f["vault"]["profiles"]
    assert v["opaque_references_only"] is True and v["raw_secret_return"] is False and v["public_vault_locator"] is False
    assert v["authoritative_database_binding"] is False
    assert v["exact_asset_and_sha_binding_required"] is True and v["readback_required"] is True and v["restore_test_required"] is True
    assert "plugin-suite exact binding" in v["promotion_requires"]
    assert "factory-intake acceptance" in v["promotion_requires"]
    assert v["runtime_boundary"]=={
      "binding_candidate_generation":True,"database_write_performed_by_candidate_contract":False,
      "vault_mutation_performed_by_scheduled_validation":False,"production_invocation_enabled":False}

    for row in triggers:
        tid,group,event,target,plugin,profile,independent,preconditions=row
        assert plugin in actual_plugins
        assert profile in v["profiles"]
        assert group in {"phase_gate","phase3_bootstrap","commerce","continuity"}
        if group=="commerce" and tid in {"commerce.publish.bounded","commerce.entitlement.fulfillment"}:
            assert "valid_non_superseded_ECAC" in preconditions
    print(json.dumps({
      "result":"PASS_MACHINE_TRIGGER_BINDINGS",
      "fabric":f["fabric"],"trigger_bundles":32,"derivative_candidates":128,"plugins":5,
      "vault_binding_candidates":32,"authoritative_delta":0,"factory_intake":i["state"],"vault_runtime":v["state"],
      "mutual_binding":"PASS"
    },sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
