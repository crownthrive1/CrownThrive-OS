from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "supabase/migrations/20260905111500_chlom_control_plane_release_status_provider_projection_v2.sql").read_text()
LOW = SQL.lower()


def test_release_status_reads_latest_governed_gateway_deployment():
    assert "chlom_protocol.gateway_deployment_versions_v1" in SQL
    assert "ct.gateway.chlom-authenticated-gateway-v1" in SQL
    assert "chlom-control-plane-v1" in SQL
    assert "order by g.version desc, g.recorded_at desc" in LOW
    assert "CURRENT_RECORDED_PROVIDER_RELEASE" in SQL


def test_gateway_identity_is_projected_from_receipt_not_fixed_release_claim():
    assert "v_gateway.evidence->>'gateway_version'" in SQL
    assert "v_gateway.evidence->>'dispatcher_contract'" in SQL
    assert "v_gateway.provider_state" in SQL
    assert "v_gateway.provider_readback" in SQL
    assert "v_gateway.verify_jwt" in SQL
    assert "v_gateway.source_sha256" in SQL
    assert "v_gateway.deployment_manifest_sha256" in SQL
    assert "'version', '1.2.0'" not in SQL


def test_dispatcher_contract_maps_to_exact_database_function_identity():
    assert "ct.chlom.authenticated-control-plane-dispatch.v3" in SQL
    assert "public.chlom_api_dispatch_v3(text,jsonb,text)" in SQL
    assert "ct.chlom.authenticated-control-plane-dispatch.v2" in SQL
    assert "public.chlom_api_dispatch_v2(text,jsonb,text)" in SQL
    assert "HOLD_DISPATCHER_IDENTITY_UNRESOLVED" in SQL


def test_projection_fails_closed_on_missing_or_incomplete_provider_evidence():
    assert "HOLD_NO_GATEWAY_DEPLOYMENT_RECORD" in SQL
    assert "HOLD_PROVIDER_NOT_ACTIVE" in SQL
    assert "HOLD_PROVIDER_READBACK_REQUIRED" in SQL
    assert "HOLD_PROVIDER_JWT_REQUIRED" in SQL
    assert "HOLD_PROVIDER_SOURCE_DIGEST_REQUIRED" in SQL
    assert "HOLD_DEPLOYMENT_MANIFEST_REQUIRED" in SQL
    assert "'ok', v_projection_state = 'CURRENT_RECORDED_PROVIDER_RELEASE'" in SQL


def test_existing_security_and_external_authority_boundaries_are_preserved():
    assert "security definer" in LOW
    assert "set search_path = pg_catalog, chlom_protocol, public" in LOW
    assert "idempotency_enforced_for_mutations" in SQL
    assert "conflicting_key_reuse_fails_closed" in SQL
    assert "external_execution_enabled', false" in SQL
    assert "external_money_movement" in SQL
    assert "production_token_mint_confirmation" in SQL
    assert "legal_title_adjudication" in SQL
    assert "insert into chlom_protocol.gateway_deployment_versions_v1" not in LOW
    assert "update chlom_protocol.gateway_deployment_versions_v1" not in LOW
    assert "delete from chlom_protocol.gateway_deployment_versions_v1" not in LOW
