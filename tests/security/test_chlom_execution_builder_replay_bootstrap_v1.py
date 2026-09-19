from pathlib import Path


MIGRATION = Path("supabase/migrations/20260823203000_chlom_execution_builder_replay_bootstrap_v1.sql")
DEPENDENT_VERSION = "20260823203546"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_bootstrap_precedes_execution_builder_identity_migration() -> None:
    assert MIGRATION.name[:14] < DEPENDENT_VERSION


def test_bootstrap_is_idempotent_and_creates_only_contract_dependencies() -> None:
    sql = _sql()
    assert "create schema if not exists chlom_secrets" in sql
    assert "create schema if not exists chlom_runtime" in sql
    assert "create table if not exists chlom_secrets.trade_secret_assets" in sql
    assert "create table if not exists chlom_runtime.vaulted_capability_registry" in sql
    assert "create or replace view chlom_runtime.capability_contracts" in sql
    assert "create table chlom_runtime.execution_capability_registry" not in sql


def test_bootstrap_keeps_client_access_fail_closed() -> None:
    sql = _sql()
    assert sql.count("enable row level security") == 2
    assert sql.count("force row level security") == 2
    assert sql.count("to anon, authenticated") == 2
    assert sql.count("using (false)") == 2
    assert sql.count("with check (false)") == 2
    assert sql.count("revoke all") >= 3
    assert "grant select on chlom_runtime.capability_contracts to service_role" in sql


def test_bootstrap_does_not_create_authority_or_secret_bodies() -> None:
    sql = _sql()
    forbidden = (
        "create role",
        "alter role",
        "security definer",
        "vault.decrypted_secrets",
        "decrypted_secret",
        "secret_value",
        "force merge",
        "github_token",
    )
    for token in forbidden:
        assert token not in sql


def test_bootstrap_preserves_explicit_authority_ceiling_domain() -> None:
    sql = _sql()
    for ceiling in ("'d0'::text", "'d1'::text", "'d2'::text", "'d3'::text"):
        assert ceiling in sql
    assert "requires_independent_verifier boolean not null default false" in sql
    assert "body_exposure_allowed boolean not null default false" in sql
