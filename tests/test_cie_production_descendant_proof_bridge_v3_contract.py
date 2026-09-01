from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "supabase/migrations/20260901235049_cie_production_descendant_proof_bridge_v3.sql"
REFRESH = ROOT / "supabase/migrations/20260901235440_cie_current_head_technical_assurance_v2.sql"
GATE_ROLLBACK = ROOT / "supabase/rollback/20260901235049_cie_production_descendant_proof_bridge_v3_rollback.sql"
REFRESH_ROLLBACK = ROOT / "supabase/rollback/20260901235440_cie_current_head_technical_assurance_v2_rollback.sql"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gate_requires_parent_and_child_descendant_proof():
    sql = _text(GATE)
    assert "v_child_descendant_ok" in sql
    assert "{parent_compare,status}" in sql
    assert "{child_compare,status}" in sql
    assert "behind_by" in sql
    assert "technical_assurance_only" in sql


def test_gate_preserves_founder_receipt_and_no_authority_rewrite():
    sql = _text(GATE)
    assert "v_prod.authority_mode=''founder_direct''" in sql
    assert "v_prod.rollback_state=''ready''" in sql
    assert "production_authority_rewritten" in sql
    assert "package_production_authority_rewritten" in sql
    assert "authority_effect" in sql
    assert "operational_activation" in sql


def test_refresh_accepts_descendants_without_reauthorizing_source():
    sql = _text(REFRESH)
    assert "github_parent_child_descendant_evidence_required" in sql
    assert "{parent_compare,base_sha}" in sql
    assert "{child_compare,base_sha}" in sql
    assert "technical_assurance_only" in sql
    assert "package_production_authority_rewritten" in sql
    assert "production_authority_rewritten'',false" in sql
    assert "operational_activation'',false" in sql
    assert "authority_effect'',false" in sql


def test_rollbacks_are_exact_poststate_guarded_and_history_preserving():
    gate = _text(GATE_ROLLBACK)
    refresh = _text(REFRESH_ROLLBACK)
    assert "2e62eed35a1a5aafa1dcd55eb446cc32833da7ccd37d6ae7d7cfd6338708a22e" in gate
    assert "555dd34cbd5cce94cfbc5bad15c79e57a50530e6915afffde8932e68e476e049" in gate
    assert "264c9cb333ebcc387e04231e32a9950e0c263cacf576641381b7136cab6caac1" in refresh
    assert "0f11c868f06e32afa2ccc83c8dbb905d0b130bdeae16f2c73aabbb693c779da7" in refresh
    for sql in (gate, refresh):
        lowered = sql.lower()
        assert "delete from chlom_runtime.dail" not in lowered
        assert "truncate" not in lowered
