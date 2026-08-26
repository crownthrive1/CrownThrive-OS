"""Regression tests for the Penta Family production control plane."""
from __future__ import annotations
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.penta_family import PentaFamilyError, compose_family, load_family, member_dispatch_gate, member_portal, validate_family_registry  # noqa: E402


def expect_error(fn, contains: str) -> None:
    try: fn()
    except PentaFamilyError as exc: assert contains in str(exc), (contains, str(exc))
    else: raise AssertionError(f"expected PentaFamilyError containing {contains!r}")


def base_registry(catalogs: list[dict], refs: list[str] | None = None) -> dict:
    return {
        "registry_id": "crownthrive.penta.family", "canonical_name": "Penta Family", "status": "production", "production_scope": "institutional_control_plane",
        "production_contract": {"fail_closed": True, "member_status_is_independent": True, "production_family_does_not_promote_members": True, "unknown_members_block_dispatch": True, "duplicate_machine_keys_block_dispatch": True, "missing_required_catalogs_block_dispatch": True, "execution_requires_member_eligibility": True, "execution_eligible_maturity": ["certified", "production"]},
        "catalogs": catalogs,
        "control_plane_validation": {"registered_penta_refs_required": True, "normalize_display_names": True, "external_refs_allowed": ["CHLOM", "DAIL"], "unresolved_reference_disposition": "hold_fail_closed"},
        "control_planes": {"test": refs or ["PentaTest", "CHLOM"]},
        "portal_contract": {"every_registered_member_has_portal": True, "base_route": "/penta", "route_pattern": "/penta/{machine_key_suffix}", "portal_state_is_independent_from_maturity": True, "portal_does_not_create_execution_authority": True, "required_sections": ["overview", "status", "responsibilities", "inputs_outputs", "authority_boundary", "dependencies", "sops_slas", "runbooks", "guides", "evidence", "api_mcp", "changelog", "support"]},
        "self_build_contract": {"contract_path": "data/penta/self-build.contract.json", "candidate_schema_path": "schemas/penta/self-build-candidate.schema.json", "runtime_path": "runtime/penta_self_build.py", "applies_to_all_registered_members": True, "typed_gap_required": True, "penta_factory_builder_required": True, "independent_certification_required": True, "negative_and_stress_tests_required": True, "rollback_required": True, "authority_never_manufactured": True, "d3_human_reserved": True},
    }


def test_live_repository_contract() -> None:
    registry, snapshot = load_family(ROOT)
    assert registry["status"] == "production" and snapshot["family_status"] == "production" and snapshot["fail_closed"] is True
    assert snapshot["member_count"] >= 50
    assert snapshot["promotion_count"] == 5
    assert set(snapshot["promoted_members"]) == {"penta.mail", "penta.status", "penta.credentials", "penta.build", "penta.certify"}

    for key in ("penta.scribe", "penta.mail", "penta.status", "penta.credentials", "penta.build", "penta.certify"):
        gate = member_dispatch_gate(snapshot, key)
        assert gate["eligible"] is True, (key, gate)
        assert snapshot["members"][key]["maturity"] == "production"

    control = member_dispatch_gate(snapshot, "penta.control")
    assert control["eligible"] is False and control["disposition"] == "hold_fail_closed"
    capital = member_dispatch_gate(snapshot, "penta.capital")
    assert capital["eligible"] is False and "implemented" in capital["reason"]

    for key in ("penta.concierge", "penta.nurture", "penta.green", "penta.managers", "penta.directors", "penta.hr", "penta.pay", "penta.cost", "penta.board", "penta.ofac", "penta.suite", "penta.rfa", "penta.pr"):
        assert key in snapshot["members"]
        gate = member_dispatch_gate(snapshot, key)
        assert gate["eligible"] is False and "specified" in gate["reason"], (key, gate)

    unknown = member_dispatch_gate(snapshot, "penta.unknown")
    assert unknown["eligible"] is False and unknown["disposition"] == "hold_fail_closed"


def test_promotions_retain_source_lineage_and_evidence() -> None:
    _, snapshot = load_family(ROOT)
    for key in snapshot["promoted_members"]:
        member = snapshot["members"][key]
        promotion = member["maturity_promotion"]
        assert promotion["from_maturity"] == "specified"
        assert promotion["to_maturity"] == "production"
        assert promotion["authority_ref"]
        assert promotion["evidence_refs"] and promotion["runtime_refs"]
        for ref in [*promotion["evidence_refs"], *promotion["runtime_refs"]]: assert (ROOT / ref).exists(), (key, ref)
        assert member["source"].startswith("data/penta/")


def test_all_control_plane_penta_refs_resolve() -> None:
    _, snapshot = load_family(ROOT)
    for entries in snapshot["control_plane_resolution"].values():
        for entry in entries:
            if entry["kind"] == "penta_member": assert entry["resolved_to"] in snapshot["members"]
            else: assert entry["resolved_to"] in {"CHLOM", "DAIL"}


def test_every_member_has_portal_and_required_sections() -> None:
    registry, snapshot = load_family(ROOT)
    assert len(snapshot["portal_index"]) == snapshot["member_count"]
    for key, member in snapshot["members"].items():
        assert member["portal_route"] == f"/penta/{key.split('.', 1)[1]}" and member["portal_state"] == "contracted"
    mail = member_portal(snapshot, registry, "penta.mail")
    assert mail["portal_route"] == "/penta/mail"
    assert mail["sections"]["status"]["member_maturity"] == "production"
    assert mail["sections"]["status"]["execution_eligible"] is True
    assert mail["sections"]["status"]["maturity_promotion"]["authority_ref"]
    assert set(registry["portal_contract"]["required_sections"]) <= set(mail["sections"])


def test_contract_cannot_disable_fail_closed() -> None:
    registry = json.loads((ROOT / "data/penta/family.registry.json").read_text(encoding="utf-8")); broken = copy.deepcopy(registry); broken["production_contract"]["fail_closed"] = False
    expect_error(lambda: validate_family_registry(broken), "fail_closed")


def test_portal_contract_cannot_drop_required_section() -> None:
    registry = json.loads((ROOT / "data/penta/family.registry.json").read_text(encoding="utf-8")); broken = copy.deepcopy(registry); broken["portal_contract"]["required_sections"].remove("authority_boundary")
    expect_error(lambda: validate_family_registry(broken), "portal contract missing required sections")


def test_self_build_contract_cannot_manufacture_authority() -> None:
    registry = json.loads((ROOT / "data/penta/family.registry.json").read_text(encoding="utf-8")); broken = copy.deepcopy(registry); broken["self_build_contract"]["authority_never_manufactured"] = False
    expect_error(lambda: validate_family_registry(broken), "authority_never_manufactured")


def test_missing_required_catalog_blocks_family_snapshot() -> None:
    registry = base_registry([{"catalog_id": "missing", "path": "data/penta/missing.registry.json", "required": True, "role": "test"}])
    with tempfile.TemporaryDirectory() as temp: expect_error(lambda: compose_family(Path(temp), registry), "missing required family catalogs")


def test_duplicate_machine_keys_block_composition() -> None:
    registry = base_registry([{"catalog_id": "a", "path": "data/penta/a.json", "required": True, "role": "test"}, {"catalog_id": "b", "path": "data/penta/b.json", "required": True, "role": "test"}])
    catalog = {"systems": [{"machine_key": "penta.test", "canonical_name": "PentaTest", "maturity": "production"}]}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); (root / "data/penta").mkdir(parents=True)
        for name in ("a.json", "b.json"): (root / "data/penta" / name).write_text(json.dumps(catalog), encoding="utf-8")
        expect_error(lambda: compose_family(root, registry), "duplicate machine_key")


def test_unresolved_control_plane_reference_blocks_composition() -> None:
    registry = base_registry([{"catalog_id": "a", "path": "data/penta/a.json", "required": True, "role": "test"}], refs=["PentaMissing"])
    catalog = {"systems": [{"machine_key": "penta.test", "canonical_name": "Penta Test", "maturity": "specified"}]}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); (root / "data/penta").mkdir(parents=True); (root / "data/penta/a.json").write_text(json.dumps(catalog), encoding="utf-8")
        expect_error(lambda: compose_family(root, registry), "unresolved control-plane reference")


def test_display_name_normalization_resolves_member() -> None:
    registry = base_registry([{"catalog_id": "a", "path": "data/penta/a.json", "required": True, "role": "test"}], refs=["PentaTest"])
    catalog = {"systems": [{"machine_key": "penta.test", "canonical_name": "Penta Test", "maturity": "specified"}]}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); (root / "data/penta").mkdir(parents=True); (root / "data/penta/a.json").write_text(json.dumps(catalog), encoding="utf-8")
        snapshot = compose_family(root, registry); assert snapshot["control_plane_resolution"]["test"][0]["resolved_to"] == "penta.test"


def test_promotion_fails_closed_if_evidence_missing() -> None:
    registry = base_registry([{"catalog_id": "a", "path": "data/penta/a.json", "required": True, "role": "test"}])
    catalog = {"systems": [{"machine_key": "penta.test", "canonical_name": "PentaTest", "maturity": "specified"}]}
    promotion = {"schema": "ct.penta.production-promotions.v1", "version": "1.0.0", "fail_closed": True, "promotions": [{"machine_key": "penta.test", "from_maturity": "specified", "to_maturity": "production", "effective_at": "2026-08-26T00:00:00Z", "authority_ref": "test", "evidence_status": "PASS", "evidence_refs": ["missing-proof.json"], "runtime_refs": ["missing-runtime.py"], "scope": "test"}]}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); (root / "data/penta").mkdir(parents=True); (root / "data/penta/a.json").write_text(json.dumps(catalog), encoding="utf-8"); (root / "data/penta/production-promotions.v1.json").write_text(json.dumps(promotion), encoding="utf-8")
        expect_error(lambda: compose_family(root, registry), "promotion evidence/runtime missing")


def run() -> None:
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests: test(); print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} Penta Family tests")


if __name__ == "__main__": run()
