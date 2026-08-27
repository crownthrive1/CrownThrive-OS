import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data/penta/penta-history-mesh.v2.json"
SOURCE = ROOT / "supabase/functions/penta-history-mesh/index.ts"


class PentaHistoryMeshContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_contract_identity_and_certification(self):
        c = self.contract
        self.assertEqual(c["schema"], "ct.penta.history-mesh.contract.v2")
        self.assertEqual(c["version"], "2.0.0")
        self.assertEqual(c["service_id"], "penta_history_mesh")
        self.assertEqual(c["certification"]["decision"], "pass")
        self.assertEqual(c["certification"]["routes_tested"], 21)
        self.assertEqual(c["certification"]["routes_http_200"], 21)
        self.assertEqual(c["certification"]["digest_headers_verified"], 21)
        self.assertTrue(c["certification"]["sensitive_projection_absent"])

    def test_authority_and_security_boundaries(self):
        a = self.contract["authority"]
        self.assertTrue(a["public_read_only"])
        self.assertEqual(a["history_authority_effect"], "none")
        self.assertFalse(a["writes_enabled"])
        self.assertFalse(a["money_movement"])
        self.assertFalse(a["checkout_activation"])
        projection = self.contract["public_projection"]
        self.assertFalse(projection["archived_snapshot_public"])
        self.assertFalse(projection["control_snapshot_public"])
        self.assertFalse(projection["internal_metadata_public"])
        self.assertFalse(projection["secret_material_public"])

    def test_required_api_surface(self):
        expected = {
            "stories", "story", "supersessions", "supersession", "archives", "archive",
            "observations", "observation", "controls", "control", "current_control", "lineage",
            "chain", "mesh", "openapi", "well_known", "manifest", "health",
        }
        self.assertEqual(set(self.contract["apis"]), expected)

    def test_mesh_registry_contract(self):
        m = self.contract["mesh_registration"]
        self.assertEqual(m["mcp_tool_count"], 14)
        self.assertEqual(m["enabled_tools"], 14)
        self.assertEqual(m["closed_input_schemas"], 14)
        self.assertEqual(m["risk_class"], "D0")
        self.assertFalse(m["requires_human_approval"])

    def test_source_is_read_only_and_allowlisted(self):
        source = self.source
        self.assertIn('["GET", "HEAD"]', source)
        self.assertIn('method_not_allowed', source)
        self.assertIn('x-crownthrive-history-authority-effect', source)
        self.assertIn('"none"', source)
        self.assertNotIn('archived_snapshot,', source)
        self.assertNotIn('control_snapshot,', source)
        self.assertNotIn('SUPABASE_SERVICE_ROLE_KEY', source)
        self.assertNotIn('Deno.env.get("GITHUB_TOKEN")', source)


if __name__ == "__main__":
    unittest.main()
