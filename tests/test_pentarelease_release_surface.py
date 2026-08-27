import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pentarelease" / "release_surface.py"
spec = importlib.util.spec_from_file_location("release_surface", MODULE_PATH)
rs = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(rs)


def record():
    return {
        "tag": "v9.9.9",
        "title": "Test Release",
        "official_release_url": "https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v9.9.9",
        "why": "test",
        "what_changed": ["src/a.py"],
        "targets": ["main"],
        "what_pentarelease_is": "test publisher",
        "payload_costs": {"status": "not_available", "direct_cost_usd": None, "source": None},
        "cie_score": {"status": "not_available", "score": None, "source": None},
        "data_availability": {"changed_files": [], "release_asset_count": 0, "release_assets": []},
        "evidence": {"manifest_present": True},
        "provenance": {"release_target": "main", "generated_at": "now"},
        "penta_components": ["PentaRelease"],
        "ecosystem_lanes": ["src"],
    }


class ReleaseSurfaceTests(unittest.TestCase):
    def test_upsert_preserves_unmanaged_content(self):
        original = "# Human README\n\nKeep this.\n"
        block = "## Latest\nvalue"
        out = rs.upsert_managed_block(original, block, rs.DEFAULT_SURFACE_START, rs.DEFAULT_SURFACE_END)
        self.assertIn("# Human README", out)
        self.assertIn("Keep this.", out)
        self.assertIn("## Latest", out)

    def test_upsert_replaces_only_managed_block(self):
        old = rs.upsert_managed_block("# Human\n", "old", rs.DEFAULT_SURFACE_START, rs.DEFAULT_SURFACE_END)
        new = rs.upsert_managed_block(old, "new", rs.DEFAULT_SURFACE_START, rs.DEFAULT_SURFACE_END)
        self.assertIn("# Human", new)
        self.assertNotIn("\nold\n", new)
        self.assertIn("\nnew\n", new)

    def test_docs_page_injects_h1_when_body_starts_at_h2(self):
        page = rs.docs_page("Latest Release — v9.9.9", "## PentaRelease Comprehensive Release Record\n\nBody", "desc")
        self.assertIn("\n# Latest Release — v9.9.9\n\n## PentaRelease Comprehensive Release Record", page)

    def test_docs_page_preserves_existing_h1_without_duplicate(self):
        page = rs.docs_page("Release FAQ", "# Release FAQ — v9.9.9\n\nBody", "desc")
        self.assertEqual(page.count("# Release FAQ"), 1)

    def test_rejects_more_than_seven_repository_surfaces(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy = {
                "release_surface": {
                    "max_repository_surfaces": 7,
                    "repository_surfaces": [{"path": f"{i}.md", "label": str(i)} for i in range(8)],
                }
            }
            with self.assertRaises(RuntimeError):
                rs.sync_repository_surfaces(root, policy, record(), {})

    def test_preexisting_surface_is_never_whole_file_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "README.md"
            p.write_text("# Human README\n\nKeep me.\n")
            policy = {
                "release_surface": {
                    "max_repository_surfaces": 7,
                    "repository_surfaces": [{"path": "README.md", "label": "README"}],
                }
            }
            state = rs.sync_repository_surfaces(root, policy, record(), {})
            self.assertFalse(state["repository_surfaces"]["README.md"]["created_by_pentarelease"])

            # Retire from policy. Managed block is removed, human file remains.
            policy["release_surface"]["repository_surfaces"] = []
            state = rs.sync_repository_surfaces(root, policy, record(), state)
            self.assertTrue(p.exists())
            text = p.read_text()
            self.assertIn("Keep me.", text)
            self.assertNotIn(rs.DEFAULT_SURFACE_START, text)

    def test_owned_created_surface_can_be_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy = {
                "release_surface": {
                    "max_repository_surfaces": 7,
                    "repository_surfaces": [{"path": "FAQ.md", "label": "FAQ"}],
                }
            }
            state = rs.sync_repository_surfaces(root, policy, record(), {})
            self.assertTrue(state["repository_surfaces"]["FAQ.md"]["created_by_pentarelease"])
            self.assertTrue((root / "FAQ.md").exists())
            policy["release_surface"]["repository_surfaces"] = []
            rs.sync_repository_surfaces(root, policy, record(), state)
            self.assertFalse((root / "FAQ.md").exists())

    def test_owned_created_surface_is_preserved_if_human_text_added(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy = {
                "release_surface": {
                    "max_repository_surfaces": 7,
                    "repository_surfaces": [{"path": "FAQ.md", "label": "FAQ"}],
                }
            }
            state = rs.sync_repository_surfaces(root, policy, record(), {})
            p = root / "FAQ.md"
            p.write_text(p.read_text() + "\nHuman addition.\n")
            policy["release_surface"]["repository_surfaces"] = []
            rs.sync_repository_surfaces(root, policy, record(), state)
            self.assertTrue(p.exists())
            self.assertIn("Human addition.", p.read_text())

    def test_license_block_states_legal_text_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "LICENSE"
            p.write_text("ORIGINAL LEGAL TERMS\n")
            policy = {
                "release_surface": {
                    "max_repository_surfaces": 7,
                    "repository_surfaces": [{"path": "LICENSE", "label": "License"}],
                }
            }
            rs.sync_repository_surfaces(root, policy, record(), {})
            text = p.read_text()
            self.assertIn("ORIGINAL LEGAL TERMS", text)
            self.assertIn("does not amend, replace", text)

    def test_missing_cie_remains_null(self):
        with tempfile.TemporaryDirectory() as td:
            result = rs.discover_cie(Path(td), {})
            self.assertEqual(result["status"], "not_available")
            self.assertIsNone(result["score"])
            self.assertFalse(result["invented"])

    def test_missing_direct_cost_remains_null(self):
        with tempfile.TemporaryDirectory() as td:
            result = rs.discover_direct_cost({}, Path(td))
            self.assertEqual(result["status"], "not_available")
            self.assertIsNone(result["direct_cost_usd"])
            self.assertFalse(result["invented"])

    def test_pentadocs_tab_cap_and_owned_addition(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            docs = {
                "navigation": {
                    "tabs": [{"tab": f"Existing {i}", "pages": ["index"]} for i in range(5)]
                }
            }
            (root / "docs.json").write_text(json.dumps(docs))
            policy = {
                "release_surface": {
                    "max_pentadocs_tabs": 7,
                    "pentadocs": {
                        "enabled": True,
                        "config": "docs.json",
                        "tab": "Releases & Evidence",
                        "pages": ["pentarelease/latest"],
                    },
                }
            }
            state = rs.sync_pentadocs_nav(root, policy, {})
            result = json.loads((root / "docs.json").read_text())
            self.assertEqual(len(result["navigation"]["tabs"]), 6)
            self.assertTrue(state["pentadocs_nav"]["created_by_pentarelease"])

    def test_pentadocs_refuses_eighth_tab(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            docs = {
                "navigation": {
                    "tabs": [{"tab": f"Existing {i}", "pages": ["index"]} for i in range(7)]
                }
            }
            (root / "docs.json").write_text(json.dumps(docs))
            policy = {
                "release_surface": {
                    "max_pentadocs_tabs": 7,
                    "pentadocs": {
                        "enabled": True,
                        "config": "docs.json",
                        "tab": "Releases & Evidence",
                        "pages": ["pentarelease/latest"],
                    },
                }
            }
            with self.assertRaises(RuntimeError):
                rs.sync_pentadocs_nav(root, policy, {})


if __name__ == "__main__":
    unittest.main()
