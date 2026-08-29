from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data/penta/stripe-webhook-ingress.v2.json"
INGRESS = ROOT / "supabase/functions/stripe-webhook-ingress-v2/index.ts"
BOOTSTRAP = ROOT / "supabase/functions/stripe-webhook-bootstrap-v2/index.ts"
SCHEMA = ROOT / "supabase/migrations/20260829023000_stripe_webhook_ingress_fabric_v2.sql"
RETIREMENT = ROOT / "supabase/migrations/20260829023100_stripe_webhook_bootstrap_retirement_history_v2.sql"


def test_contract_is_production_but_has_no_money_authority() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert data["contract"] == "ct.stripe.webhook-ingress.v2"
    assert data["status"] == "production"
    assert data["security"]["stripe_signature_required"] is True
    assert data["event_semantics"]["canary_is_not_real_provider_event"] is True
    assert data["event_semantics"]["live_event_receipt_requires_real_stripe_signature_delivery"] is True
    assert "no_money_movement" in data["non_authorities"]
    assert "no_signature_bypass" in data["non_authorities"]


def test_ingress_requires_raw_body_signature_verification() -> None:
    source = INGRESS.read_text(encoding="utf-8")
    assert 'request.headers.get("stripe-signature")' in source
    assert "TOLERANCE_SECONDS = 300" in source
    assert "constantTimeEqual" in source
    assert "t=${parsed.timestamp}.${rawBody}" not in source  # guards accidental literal interpolation typo
    assert "`${parsed.timestamp}.${rawBody}`" in source
    assert "stripe_signature_verification_failed" in source
    assert "request_too_large" in source
    assert "stripe_webhook_record_event_v2" in source


def test_bootstrap_never_returns_secrets_and_only_retires_after_canary() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")
    canary_at = source.index("const canary = await signedCanary")
    retire_at = source.index("const retired: string[]")
    assert canary_at < retire_at
    assert "if (!canary.ok)" in source
    assert "ct_provider_secret_upsert_v2" in source
    assert "secret_exposed: false" in source
    assert "signingSecret," not in source[source.index("return respond(200"):]
    assert '"DELETE", `/webhook_endpoints/' in source


def test_schema_is_private_append_only_and_idempotent() -> None:
    sql = SCHEMA.read_text(encoding="utf-8").lower()
    assert "stripe_event_id text primary key" in sql
    assert "unique(stripe_event_id,handler_ref)" in sql
    assert "stripe webhook event/receipt evidence is append-only" in sql
    assert "enable row level security" in sql
    assert "from public,anon,authenticated" in sql
    assert "grant execute on function public.stripe_webhook_record_event_v2" in sql
    assert "no money" not in sql or "money_movement_authority" in sql


def test_canary_and_real_provider_events_are_not_conflated() -> None:
    ingress = INGRESS.read_text(encoding="utf-8")
    schema = SCHEMA.read_text(encoding="utf-8")
    assert '"bootstrap_canary"' in ingress
    assert '"stripe_provider"' in ingress
    assert "p_source_kind='stripe_provider'" in schema
    assert "source_kind='bootstrap_canary'" in schema
    assert "real_provider_events_received" in schema


def test_retirement_history_is_monotonic() -> None:
    sql = RETIREMENT.read_text(encoding="utf-8").lower()
    assert "array_agg(distinct x order by x)" in sql
    assert "retired_ids_this_run" in sql
    assert "retired_ids_total" in sql
    assert "broken_predecessors_retired_total" in sql
