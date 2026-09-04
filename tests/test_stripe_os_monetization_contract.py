import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
MCP_PATH = ROOT / ".mcp.json"
PROVIDERS_PATH = ROOT / "runtime" / "penta-provider-control-plane" / "providers.json"
CONTRACT_PATH = ROOT / "contracts" / "providers" / "stripe-os-monetization-mesh.v1.json"
HARDENING_PATH = ROOT / "supabase" / "migrations" / "20260901024551_stripe_runtime_typed_adapter_hardening_v2.sql"
REPAIR_PATH = ROOT / "supabase" / "migrations" / "20260901025133_stripe_pentagreen_runtime_contract_repair_v1.sql"
READINESS_PATH = ROOT / "supabase" / "migrations" / "20260901025747_stripe_capability_adoption_and_truthful_readiness_v2.sql"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def compact_sql(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").lower()).strip()


class StripeOSMonetizationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mcp = load_json(MCP_PATH)
        cls.providers = load_json(PROVIDERS_PATH)
        cls.contract = load_json(CONTRACT_PATH)
        cls.hardening = compact_sql(HARDENING_PATH)
        cls.repair = compact_sql(REPAIR_PATH)
        cls.readiness = compact_sql(READINESS_PATH)
        cls.stripe_provider = next(
            provider for provider in cls.providers["providers"]
            if provider["provider_id"] == "stripe"
        )

    def test_official_mcp_has_no_source_credential_projection(self):
        stripe_mcp = self.mcp["mcpServers"]["stripe"]
        self.assertEqual(stripe_mcp, {"url": "https://mcp.stripe.com"})
        serialized = json.dumps(stripe_mcp).lower()
        for forbidden in ("authorization", "header", "secret", "token", "${"):
            self.assertNotIn(forbidden, serialized)

        operator_mcp = self.contract["adapter"]["operator_mcp"]
        self.assertEqual(operator_mcp["url"], "https://mcp.stripe.com")
        self.assertFalse(operator_mcp["credential_projection"])

    def test_one_canonical_adapter_owns_all_transport_variants(self):
        adapter = self.stripe_provider["adapter"]
        contract_adapter = self.contract["adapter"]
        self.assertEqual(adapter["adapter_id"], "ct.adapter.stripe.v1")
        self.assertEqual(adapter["version"], "2.0.0")
        self.assertEqual(contract_adapter["canonical_adapter_id"], "ct.adapter.stripe.v1")
        self.assertEqual(contract_adapter["version"], "2.0.0")

        registry_variants = adapter["transport_variants"]
        contract_variants = contract_adapter["transport_variants"]
        expected_ids = {
            "ct.adapter.stripe.mcp.v1",
            "ct.adapter.stripe.runtime.v1",
            "ct.adapter.stripe.webhook.v3",
            "ct.adapter.stripe.catalog-mirror.v2",
        }
        self.assertEqual({row["adapter_id"] for row in registry_variants}, expected_ids)
        self.assertEqual({row["adapter_id"] for row in contract_variants}, expected_ids)
        for row in registry_variants:
            self.assertEqual(row["authority"], "inherits_ct.adapter.stripe.v1")
        for row in contract_variants:
            self.assertEqual(row["authority"], "inherits_ct.adapter.stripe.v1")
            self.assertFalse(row["independent_authority"])

    def test_provider_registry_exposes_only_certified_runtime_operations(self):
        operations = {
            row["operation"]: row
            for row in self.stripe_provider["adapter"]["operations"]
        }
        self.assertEqual(
            set(operations),
            {
                "balance_read",
                "product_write",
                "price_write",
                "payment_link_write",
                "webhook_reconcile",
            },
        )
        self.assertFalse(operations["balance_read"]["side_effect"])
        self.assertEqual(operations["balance_read"]["authority_class"], "D0")
        for operation in (
            "product_write",
            "price_write",
            "payment_link_write",
            "webhook_reconcile",
        ):
            self.assertTrue(operations[operation]["side_effect"])
            self.assertEqual(operations[operation]["authority_class"], "D2")
            self.assertTrue(operations[operation]["requires_readback"])
        for unsupported in (
            "checkout_write",
            "subscription_write",
            "invoice_write",
            "connect_write",
            "transfer_write",
            "payout_write",
        ):
            self.assertNotIn(unsupported, operations)

    def test_factory_truth_is_paused_with_zero_ready_candidates(self):
        state = self.contract["runtime_state"]
        self.assertEqual(
            self.contract["maturity"],
            "production_runtime_repaired_factory_paused",
        )
        self.assertFalse(state["factory_clock_active"])
        self.assertFalse(state["automatic_restart_allowed"])
        self.assertEqual(state["factory_ready_candidates"], 0)
        self.assertEqual(state["product_types_enabled_for_sale"], 0)
        self.assertEqual(state["legal_tax_profiles_ready"], 0)

        self.assertEqual(
            set(self.contract["factory_outputs"]),
            {"product_price", "payment_link", "webhook_binding", "catalog_sync"},
        )
        held = {
            row["output"]: row["state"]
            for row in self.contract["planned_held_outputs"]
        }
        self.assertTrue(all(state.startswith("HOLD_") for state in held.values()))
        for output in (
            "checkout",
            "subscription",
            "invoice",
            "connect_plan",
            "refund",
            "transfer",
            "payout",
        ):
            self.assertIn(output, held)
            self.assertTrue(held[output].startswith("HOLD_"))
            self.assertNotIn(output, self.contract["factory_outputs"])

        self.assertEqual(
            set(self.contract["executable_provider_operations"]),
            {
                "product.create",
                "product.retrieve",
                "price.create",
                "price.retrieve",
                "payment_link.create",
                "payment_link.retrieve",
                "webhook.reconcile",
                "catalog.sync",
            },
        )

        payout = self.contract["payout_rail"]
        self.assertEqual(payout["state"], "HOLD_DEFAULT_BANK_ERRORED")
        self.assertTrue(payout["account_payout_flag_is_not_health_evidence"])
        self.assertFalse(payout["automatic_money_movement_allowed"])

    def test_factory_contract_requires_sale_tax_entitlement_and_webhook_evidence(self):
        gates = set(self.contract["factory_preconditions"])
        self.assertTrue(
            {
                "product_type_enabled_for_sale",
                "provider_tax_code_verified",
                "legal_taxability_state_ready_or_verified",
                "tax_behavior_inclusive_or_exclusive",
                "entitlement_handler_ref_bound",
                "entitlement_binding_state_ready",
                "webhook_binding_key_bound",
                "signed_webhook_canary_current_with_required_event_matrix",
                "rights_state_ready",
                "fulfillment_state_ready",
                "quality_state_ready",
                "route_state_ready",
                "custody_state_ready",
                "docs_state_ready",
            }.issubset(gates)
        )

    def test_typed_transport_is_exact_route_versioned_and_private(self):
        self.assertIn(
            "create or replace function integration_control.stripe_os_provider_operation_v2(",
            self.hardening,
        )
        self.assertGreaterEqual(
            self.hardening.count("row('stripe-version','2026-07-29.dahlia')"),
            2,
        )
        self.assertIn("set search_path to 'pg_catalog'", self.hardening)
        self.assertIn("stripe_adapter_exact_path_required", self.hardening)
        self.assertIn("stripe_adapter_typed_route_not_allowed", self.hardening)
        self.assertIn("stripe_executing_request_binding_required", self.hardening)

        for operation in (
            "product.create",
            "product.retrieve",
            "price.create",
            "price.retrieve",
            "payment_link.create",
            "payment_link.retrieve",
        ):
            self.assertIn(f"p_operation='{operation}'", self.hardening)

        self.assertIn(
            "revoke all on function integration_control.stripe_os_provider_request_v1(text,text,text,text,text) from public,anon,authenticated,service_role;",
            self.hardening,
        )
        self.assertIn(
            "revoke all on function integration_control.stripe_os_provider_operation_v2(uuid,text,text,jsonb) from public,anon,authenticated,service_role;",
            self.hardening,
        )
        forbidden_grant = re.compile(
            r"grant execute on function integration_control\.stripe_os_provider_"
            r"(?:request_v1|operation_v2)\([^;]*\) to "
            r"(?:public|anon|authenticated|service_role)"
        )
        self.assertIsNone(forbidden_grant.search(self.hardening))

    def test_binder_supports_only_four_outputs_and_rechecks_every_gate(self):
        for pair in (
            "('product_price','product_price')",
            "('payment_link','payment_link')",
            "('webhook_binding','webhook_binding')",
            "('catalog_sync','catalog_sync')",
        ):
            self.assertIn(pair, self.repair)
        self.assertIn("hold_specialized_executor_required", self.repair)
        self.assertIn("q:=null; p:=null", self.repair)
        self.assertIn(
            "v_tax_code:=null; v_tax_behavior:=null; v_handler:=null; v_webhook:=null",
            self.repair,
        )
        self.assertIn("pt.enabled_for_sale=true", self.repair)
        self.assertIn("tr.stripe_code_state='provider_code_verified'", self.repair)
        self.assertIn("tr.legal_taxability_state", self.repair)
        self.assertIn("p.metadata->>'tax_behavior'", self.repair)
        self.assertIn("stripe_entitlement_handler_ref", self.repair)
        self.assertIn("stripe_webhook_binding_key", self.repair)
        self.assertIn("wr.signed_canary_ok=true", self.repair)
        self.assertIn("interval '24 hours'", self.repair)
        self.assertIn("provider_account_id", self.repair)
        self.assertIn("limit greatest(1,least(coalesce(p_limit,1),5))", self.repair)

    def test_truthful_readiness_keeps_clock_and_payout_rail_held(self):
        self.assertIn("'factory_clock_active',false", self.readiness)
        self.assertIn("'factory_ready_candidates',0", self.readiness)
        self.assertIn("'product_types_enabled_for_sale',0", self.readiness)
        self.assertIn("'legal_tax_profiles_ready',0", self.readiness)
        self.assertIn("hold_default_bank_errored", self.readiness)
        self.assertIn("ct.adapter.stripe.v1", self.readiness)
        self.assertIn("https://mcp.stripe.com", self.readiness)
        self.assertIn(
            "alter view integration_control.pentagreen_stripe_catalog_bridge_v1 set (security_invoker=true)",
            self.readiness,
        )
        self.assertIn(
            "revoke all on function integration_control.thriveevergreen_commerce_mesh_cycle_v1() from public,anon,authenticated",
            self.readiness,
        )
        self.assertIn(
            "revoke all on function integration_control.stripe_os_runtime_readiness_v2() from public,anon,authenticated",
            self.readiness,
        )
        for migration in (self.hardening, self.repair, self.readiness):
            self.assertNotIn("cron.unschedule(146)", migration)


if __name__ == "__main__":
    unittest.main()
