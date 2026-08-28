import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data/penta/penta-wire.v2.json"
SOURCE = ROOT / "supabase/functions/penta-wire-mesh/index.ts"


class PentaWireContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_canonical_identity_and_runtime(self):
        c = self.contract
        self.assertEqual(c["schema"], "ct.penta.wire.v2")
        self.assertEqual(c["canonical_name"], "PentaWire")
        self.assertEqual(c["agent_id"], "ct.agent.penta-wire")
        self.assertEqual(c["service_id"], "penta_wire_mesh")
        self.assertEqual(c["version"], "2.0.0")
        self.assertEqual(c["runtime"]["function_slug"], "penta-wire-mesh")
        self.assertRegex(c["runtime"]["edge_function_sha256"], r"^[0-9a-f]{64}$")

    def test_fabric_binding_and_clock_reuse(self):
        c = self.contract
        self.assertEqual(
            c["fabrics"],
            ["PentaMesh", "PentaFabric", "PentaFactory", "PentaCertify", "PentaStatus", "PentaPolice"],
        )
        self.assertEqual(c["scheduler"]["existing_job"], "ct-software-factory-tick-v2")
        self.assertEqual(c["scheduler"]["cron"], "*/5 * * * *")
        self.assertEqual(c["scheduler"]["external_scheduler_slot_delta"], 0)
        self.assertFalse(c["scheduler"]["new_external_clock"])

    def test_authority_boundaries(self):
        a = self.contract["authority"]
        self.assertEqual(a["authority_ceiling"], "D2")
        self.assertTrue(a["d3_human_reserved"])
        self.assertTrue(a["no_self_approval"])
        self.assertFalse(a["provider_write"])
        self.assertFalse(a["credential_forwarding"])
        self.assertFalse(a["money_movement"])
        self.assertFalse(a["checkout_activation"])
        self.assertEqual(a["authority_effect"], "none")

    def test_exact_adapters_are_allowlisted(self):
        adapters = {item["service_id"]: item for item in self.contract["exact_read_adapters"]}
        self.assertEqual(
            set(adapters),
            {
                "chlom_public_resolver",
                "crownthrive_io_product_sandbox",
                "pentabeata",
                "framework_factory_v2",
                "penta_heartbeat",
                "penta_od",
                "thivebase",
            },
        )
        self.assertEqual(adapters["chlom_public_resolver"]["operations"], ["identity.resolve"])
        self.assertEqual(adapters["framework_factory_v2"]["operations"], ["status.read"])
        self.assertEqual(adapters["penta_od"]["operations"], ["status.read"])
        self.assertEqual(adapters["thivebase"]["operations"], ["health.read"])
        self.assertIn("statistics.read", adapters["crownthrive_io_product_sandbox"]["operations"])

    def test_runtime_does_not_accept_arbitrary_transport(self):
        s = self.source
        self.assertIn('const PUBLIC_ID=/^ctid_[0-9a-f]{32}$/;', s)
        self.assertIn('const LINK_ID=/^sandbox-link-[0-9]{3}$/;', s)
        self.assertIn('exact_read_adapter_not_available', s)
        self.assertIn('operation_not_allowed', s)
        self.assertNotIn('url.searchParams.get("url")', s)
        self.assertNotIn('url.searchParams.get("sql")', s)
        self.assertNotIn('Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")', s)
        self.assertNotIn('authorization:', s.lower())

    def test_runtime_is_read_only_public_surface(self):
        s = self.source
        self.assertIn('if(!["GET","HEAD"].includes(req.method))', s)
        self.assertIn('"access-control-allow-methods":"GET,HEAD,OPTIONS"', s)
        self.assertIn('provider_write:false', s)
        self.assertIn('credential_forwarding:false', s)
        self.assertFalse(self.contract["authority"]["money_movement"])
        for forbidden in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE", "TRUNCATE "):
            self.assertNotIn(forbidden, s.upper())

    def test_certification_receipt_is_pass(self):
        cert = self.contract["certification"]
        self.assertEqual(cert["certification_id"], "ct.cert.penta-wire.mesh-v2.20260827.v1")
        self.assertEqual(cert["decision"], "PASS")
        self.assertRegex(cert["evidence_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(cert["public_routes"], "14/14")
        self.assertEqual(cert["exact_read_adapters"], "7/7")
        self.assertEqual(cert["public_probes"], "5/5")
        self.assertEqual(cert["direct_mcp_contracts"], "22/22 enabled and closed-schema")
        self.assertEqual(cert["negative_tests"]["post_blocked_http"], 405)
        self.assertEqual(cert["negative_tests"]["unknown_adapter_http"], 409)


if __name__ == "__main__":
    unittest.main()
