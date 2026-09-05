from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "supabase/migrations/20260904134400_penta_pr_restack_execution_adapter_v2.sql").read_text()
EDGE = (ROOT / "supabase/functions/penta-pr-restack-provider/index.ts").read_text()
BRIDGE = (ROOT / "supabase/migrations/20260823202949_chlom_vault_capability_structural_replay_bridge_v1.sql").read_text()
TOMBSTONE = (ROOT / "supabase/migrations/20260823203545_chlom_vault_capability_structural_replay_bridge_v1.sql").read_text()
EXEC_BRIDGE = (ROOT / "supabase/migrations/20260823203648_execution_builder_structural_replay_bridge_v1.sql").read_text()


def test_assignment_gate_is_exact_and_d2_bounded():
    assert "PR_RESTACK_CURRENT_MAIN" in SQL
    assert "provider_write_allowed" in SQL
    assert "D0','D1','D2" in SQL
    assert "HOLD_CURRENT_MAIN_ASSIGNMENT_DRIFT" in SQL
    assert "source_repo is distinct from 'crownthrive1/CrownThrive-OS'" in SQL


def test_provider_requires_service_role_and_exact_provider_readback():
    assert 'jwtRole(req) !== "service_role"' in EDGE
    assert 'mainSha !== req.expected_main_sha' in EDGE
    assert 'predecessorHead !== req.predecessor_head_sha' in EDGE
    assert 'readback.body?.draft === true' in EDGE
    assert 'String(readback.body?.head?.sha ?? "") === successorHead' in EDGE
    assert 'String(readback.body?.base?.ref ?? "") === "main"' in EDGE


def test_provider_is_draft_restack_only():
    assert 'method: "POST"' in EDGE
    assert 'draft: true' in EDGE
    assert 'merge_performed: false' in EDGE
    assert 'predecessor_close_performed: false' in EDGE
    assert 'certification_claimed: false' in EDGE
    assert 'authority_created: false' in EDGE
    assert '/merges' not in EDGE
    assert '/merge' not in EDGE
    assert 'method: "DELETE"' not in EDGE


def test_predecessor_history_and_zero_delta_are_fail_closed():
    assert 'predecessor.body?.state !== "open"' in EDGE
    assert 'HOLD_PREDECESSOR_ZERO_DELTA_RECLASSIFY' in EDGE
    assert 'HOLD_RESTACK_DIFF_PAGINATION_REQUIRED' in EDGE
    assert 'Predecessor branch/head/diff/history are preserved' in EDGE


def test_no_secret_material_is_serialized_to_evidence():
    assert "penta_pm_github_token" in EDGE
    assert "ghToken" in EDGE
    assert "penta_pm_github_token" not in SQL
    assert "raw_secret" not in SQL.lower()


def test_structural_replay_bridge_precedes_provider_proven_preflight_without_credentials():
    assert "20260823202950_execution_builder_capability_contract_identity_v1.sql" in BRIDGE
    assert "create schema if not exists chlom_runtime" in BRIDGE.lower()
    assert "create schema if not exists chlom_secrets" in BRIDGE.lower()
    assert "revoke all on schema chlom_runtime from public, anon, authenticated" in BRIDGE.lower()
    assert "grant usage on schema chlom_runtime to service_role" in BRIDGE.lower()
    assert "chlom_secrets.trade_secret_assets" in BRIDGE
    assert "chlom_runtime.vaulted_capability_registry" in BRIDGE
    assert "create or replace view chlom_runtime.capability_contracts" in BRIDGE
    assert "HOLD_CAPABILITY_STRUCTURAL_REPLAY_BRIDGE_INCOMPLETE" in BRIDGE
    assert "HOLD_CAPABILITY_BASE_PRIMARY_KEY_MISSING" in BRIDGE
    assert "vault.create_secret" not in BRIDGE
    assert "decrypted_secret" not in BRIDGE
    assert "insert into chlom_secrets.trade_secret_assets" not in BRIDGE.lower()
    assert "insert into chlom_runtime.vaulted_capability_registry" not in BRIDGE.lower()


def test_structural_replay_bridge_preserves_client_deny_and_service_role_boundary():
    assert "force row level security" in BRIDGE.lower()
    assert "to anon, authenticated using (false) with check (false)" in BRIDGE.lower()
    assert "grant select, insert, update on chlom_secrets.trade_secret_assets to service_role" in BRIDGE.lower()
    assert "grant select, insert, update on chlom_runtime.vaulted_capability_registry to service_role" in BRIDGE.lower()
    assert "body_exposure_allowed boolean not null default false" in BRIDGE.lower()
    assert "to_regnamespace('chlom_runtime')" in BRIDGE
    assert "to_regnamespace('chlom_secrets')" in BRIDGE


def test_late_bridge_is_provenance_only_tombstone():
    assert "PROVENANCE-ONLY TOMBSTONE" in TOMBSTONE
    assert "20260823202949_chlom_vault_capability_structural_replay_bridge_v1.sql" in TOMBSTONE
    assert "create table" not in TOMBSTONE.lower()
    assert "create or replace view" not in TOMBSTONE.lower()
    assert "vault.create_secret" not in TOMBSTONE


def test_execution_builder_replay_bridge_is_blank_replay_only_and_production_noop():
    assert "20260823203649_execution_builder_agent_v1_0_1" in EXEC_BRIDGE
    assert "to_regclass('chlom_runtime.agent_templates') is null" in EXEC_BRIDGE
    assert "if not v_replay_bootstrap then" in EXEC_BRIDGE
    assert "return;" in EXEC_BRIDGE
    assert "replay_only_structural_bridge" in EXEC_BRIDGE
    assert "execution_authority',false" in EXEC_BRIDGE
    assert "certification_effect',false" in EXEC_BRIDGE
    assert "authority_created',false" in EXEC_BRIDGE


def test_execution_builder_replay_bridge_recreates_only_bounded_historical_shape():
    assert "create table chlom_runtime.agent_templates" in EXEC_BRIDGE.lower()
    assert "create table chlom_runtime.agent_suite_registry" in EXEC_BRIDGE.lower()
    assert "create table chlom_runtime.agent_skill_packages" in EXEC_BRIDGE.lower()
    assert "create table chlom_runtime.agent_health" in EXEC_BRIDGE.lower()
    assert "create table chlom_runtime.construction_work_queue" in EXEC_BRIDGE.lower()
    assert "create table institutional_federation.capability_execution_queue" in EXEC_BRIDGE.lower()
    assert "authority_ceiling in ('D0','D1','D2')" in EXEC_BRIDGE
    assert "check (not vote_eligible)" in EXEC_BRIDGE
    assert "check (no_self_approval)" in EXEC_BRIDGE
    assert "force row level security" in EXEC_BRIDGE.lower()
    assert "from public, anon, authenticated, service_role" in EXEC_BRIDGE.lower()


def test_execution_builder_replay_bridge_has_no_real_dail_or_provider_authority():
    assert "REPLAY_ONLY_NOOP" in EXEC_BRIDGE
    assert "'durable_write',false" in EXEC_BRIDGE
    assert "insert into chlom_runtime.dail" not in EXEC_BRIDGE.lower()
    assert "insert into public.dail" not in EXEC_BRIDGE.lower()
    assert "provider_activation',false" in EXEC_BRIDGE
    assert "grant execute on function chlom_runtime.append_dail_event" not in EXEC_BRIDGE.lower()
    assert "vault.create_secret" not in EXEC_BRIDGE
    assert "decrypted_secret" not in EXEC_BRIDGE
