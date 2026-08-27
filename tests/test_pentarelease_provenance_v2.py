import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pentarelease" / "release_surface.py"
spec = importlib.util.spec_from_file_location("release_surface_v2", MODULE_PATH)
rs = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(rs)


class PentaReleaseProvenanceV2Tests(unittest.TestCase):
    def identity(self):
        return {
            "repository": "crownthrive1/CrownThrive-OS",
            "tag": "v3.17.0.0",
            "commit_sha": "a" * 40,
            "manifest_sha256": "b" * 64,
            "official_release_url": "https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v3.17.0.0",
        }

    def test_canonical_release_url_never_uses_support_repo(self):
        self.assertEqual(
            rs.canonical_release_url("crownthrive1/CrownThrive-OS", "v3.15.0.0"),
            "https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v3.15.0.0",
        )

    def test_historical_support_url_is_normalized(self):
        body = "Official release: https://github.com/crownthrive1/CrownThrive-Support/releases/tag/v3.15.0.0\n"
        fixed = rs.sanitize_original_release_body(body, "crownthrive1/CrownThrive-OS", "v3.15.0.0")
        self.assertNotIn("CrownThrive-Support", fixed)
        self.assertIn("crownthrive1/CrownThrive-OS/releases/tag/v3.15.0.0", fixed)

    def test_generic_cost_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "PENTARELEASE_COSTS.json").write_text(json.dumps({"direct_cost_usd": 12.34}))
            result = rs.discover_direct_cost({}, root, self.identity(), root)
            self.assertEqual(result["status"], "not_available")
            self.assertIsNone(result["direct_cost_usd"])

    def test_pentacosts_requires_exact_release_binding(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = {
                "authority": "PentaCosts",
                "status": "certified",
                "direct_cost_usd": 0,
                "evidence_hash": "c" * 64,
                "release_binding": {
                    "repository": "crownthrive1/CrownThrive-OS",
                    "tag": "v3.16.0.0",
                    "commit_sha": "a" * 40,
                },
            }
            (root / "PENTACOSTS_EVIDENCE.json").write_text(json.dumps(payload))
            result = rs.discover_direct_cost({}, root, self.identity(), root)
            self.assertEqual(result["status"], "not_available")

    def test_release_bound_pentacosts_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ident = self.identity()
            payload = {
                "authority": "PentaCosts",
                "status": "certified",
                "direct_cost_usd": 0,
                "evidence_hash": "c" * 64,
                "release_binding": {
                    "repository": ident["repository"],
                    "tag": ident["tag"],
                    "commit_sha": ident["commit_sha"],
                    "manifest_sha256": ident["manifest_sha256"],
                },
                "penta_market": {"status": "certified"},
                "smart_treasury": {"status": "settled"},
            }
            (root / "PENTACOSTS_EVIDENCE.json").write_text(json.dumps(payload))
            result = rs.discover_direct_cost({}, root, ident, root)
            self.assertEqual(result["status"], "certified")
            self.assertEqual(result["direct_cost_usd"], 0)
            self.assertEqual(result["authority"], "PentaCosts")

    def test_unbound_cie_score_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = {"authority": "CIE", "status": "certified", "score": 100, "evidence_hash": "d" * 64}
            (root / "CIE_RELEASE_EVIDENCE.json").write_text(json.dumps(payload))
            result = rs.discover_cie(root, {}, self.identity(), root)
            self.assertEqual(result["status"], "not_available")
            self.assertIsNone(result["score"])

    def test_release_bound_cie_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ident = self.identity()
            payload = {
                "authority": "CIE",
                "status": "certified",
                "score": 100,
                "engine_version": "production",
                "evidence_hash": "d" * 64,
                "release_binding": {
                    "repository": ident["repository"],
                    "tag": ident["tag"],
                    "commit_sha": ident["commit_sha"],
                },
            }
            (root / "CIE_RELEASE_EVIDENCE.json").write_text(json.dumps(payload))
            result = rs.discover_cie(root, {}, ident, root)
            self.assertEqual(result["status"], "certified")
            self.assertEqual(result["score"], 100)
            self.assertEqual(result["authority"], "CIE")


if __name__ == "__main__":
    unittest.main()
