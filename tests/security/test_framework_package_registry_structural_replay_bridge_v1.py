from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = (ROOT / "supabase/migrations/20260823235409_framework_package_registry_structural_replay_bridge_v1.sql").read_text()


def test_bridge_precedes_exact_provider_failure_and_is_production_noop():
    assert "20260823235410_framework_production_promotion_and_cie_activation_v1" in BRIDGE
    assert "to_regclass('institutional_federation.framework_package_registry') is not null" in BRIDGE
    assert "return;" in BRIDGE


def test_bridge_creates_empty_nonsovereign_shape_only():
    assert "create table institutional_federation.framework_package_registry" in BRIDGE.lower()
    assert "authority_ceiling in ('D0','D1','D2')" in BRIDGE
    assert "can_vote=false" in BRIDGE
    assert "d3_human_reserved=true" in BRIDGE
    assert "operationally_enabled boolean not null default false" in BRIDGE.lower()
    assert "public_activation_allowed boolean not null default false" in BRIDGE.lower()
    assert "checkout_enabled boolean not null default false" in BRIDGE.lower()
    assert "customer_entitlement_active boolean not null default false" in BRIDGE.lower()
    assert "force row level security" in BRIDGE.lower()
    assert "from public, anon, authenticated, service_role" in BRIDGE.lower()
    assert "HOLD_FRAMEWORK_PACKAGE_REPLAY_BRIDGE_MUST_BE_EMPTY" in BRIDGE


def test_bridge_does_not_seed_or_activate_frameworks():
    assert "insert into institutional_federation.framework_package_registry" not in BRIDGE.lower()
    assert "grant " not in BRIDGE.lower()
    assert "vault.create_secret" not in BRIDGE
    assert "append_dail_event" not in BRIDGE
    assert "authority_created',true" not in BRIDGE.lower()
