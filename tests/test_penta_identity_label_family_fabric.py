import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_identity_family_fabric_contract():
    contract = json.loads((ROOT / "data/penta/penta-identity-label-family-fabric.v1.json").read_text())
    assert contract["schema"] == "crownthrive.penta.identity-label-family-fabric/v1"
    assert contract["history"]["append_only"] is True
    assert contract["history"]["delete_policy"] == "forbidden; retire or supersede"
    assert contract["history"]["hash"] == "sha256"
    assert contract["population"]["active_citizens"] == 437
    assert contract["population"]["families"] == 15
    assert contract["family_runtime"]["dispatch_authority"] == "NONE_FROM_ROUTER"
    assert contract["family_runtime"]["inherit_member_authority"] is False
    assert contract["refresh_rpc"] == "integration_control.penta_identity_refresh_v1(text)"
    assert len(contract["source_snapshot"]["source_sha256"]) == 64
    assert len(contract["source_snapshot"]["registry_sha256"]) == 64
    assert "D3" in contract["authority_invariant"]


def test_provider_migration_custody_files_present():
    required = [
        "20260830025630_penta_identity_label_family_fabric_v1.sql",
        "20260830025906_penta_identity_reconcile_runtime_projection_v1.sql",
        "20260830030246_penta_identity_source_custody_invoker_v1.sql",
    ]
    for name in required:
        path = ROOT / "supabase/migrations" / name
        assert path.is_file(), name
        assert path.read_text().strip(), name


def test_projector_is_source_custodied():
    projector = ROOT / "supabase/functions/penta-identity-source-custody-v1/index.ts"
    text = projector.read_text()
    assert projector.is_file()
    assert '20260830025630' in text
    assert '20260830025906' in text
    assert '20260830030246' in text
    assert 'raw_secret_exposed:false' in text
    assert 'production_history_rewritten:false' in text
