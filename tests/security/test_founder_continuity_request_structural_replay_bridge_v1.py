from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = (ROOT / "supabase/migrations/20260823235408_founder_continuity_request_structural_replay_bridge_v1.sql").read_text()


def test_bridge_is_exact_dependency_and_production_noop():
    assert "20260823235410" in BRIDGE
    assert "to_regclass('chlom_runtime.founder_continuity_requests') is not null" in BRIDGE
    assert "return;" in BRIDGE


def test_bridge_is_empty_fail_closed_request_shape_only():
    assert "create table chlom_runtime.founder_continuity_requests" in BRIDGE.lower()
    assert "request_id uuid primary key" in BRIDGE.lower()
    assert "human_signal_state" in BRIDGE
    assert "force row level security" in BRIDGE.lower()
    assert "from public, anon, authenticated, service_role" in BRIDGE.lower()
    assert "HOLD_FOUNDER_CONTINUITY_REQUEST_REPLAY_BRIDGE_MUST_BE_EMPTY" in BRIDGE


def test_bridge_does_not_recreate_delegated_authority_layer():
    low = BRIDGE.lower()
    assert "founder_continuity_policies" not in low
    assert "founder_continuity_votes" not in low
    assert "founder_continuity_attestations" not in low
    assert "surrogate_authorized" not in low
    assert "quorum_met" not in low
    assert "cron.schedule" not in low
    assert "grant " not in low
    assert "append_dail_event" not in low
    assert "vote_effect',false" in BRIDGE
    assert "surrogate_authority',false" in BRIDGE
    assert "execution_authority',false" in BRIDGE
    assert "authority_created',false" in BRIDGE
