import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pentarelease" / "sync_visible_tabs.py"
spec = importlib.util.spec_from_file_location("sync_visible_tabs", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


def record():
    return {
        "tag": "v3.15.0.1",
        "official_release_url": "https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v3.15.0.1",
        "title": "CrownThrive OS 3.15.0.1",
        "why": "certification fixture",
        "what_changed": ["a", "b"],
        "payload_costs": {"status": "not_available", "direct_cost_usd": None},
        "cie_score": {"status": "not_available", "score": None},
    }


def config():
    return {
        "enabled": True,
        "mode": "managed_blocks_only",
        "fail_closed_on_missing_surface": True,
        "surfaces": [
            {"path": "CONTRIBUTING.md", "label": "Contributing"},
            {"path": "SECURITY.md", "label": "Security"},
        ],
        "reconciliation": {"state_file": ".pentarelease/state/visible-tabs.json"},
    }


class VisibleTabSyncTests(unittest.TestCase):
    def test_preserves_unmanaged_content_and_updates_only_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("CONTRIBUTING.md", "SECURITY.md"):
                (root / name).write_text(f"# {name}\n\nHuman content.\n", encoding="utf-8")
            state = mod.synchronize(root, config(), record())
            self.assertEqual(len(state["surfaces"]), 2)
            for name in ("CONTRIBUTING.md", "SECURITY.md"):
                text = (root / name).read_text(encoding="utf-8")
                self.assertIn("Human content.", text)
                self.assertIn("Latest PentaRelease", text)
                self.assertEqual(text.count(mod.DEFAULT_START), 1)
                self.assertEqual(text.count(mod.DEFAULT_END), 1)

    def test_second_release_replaces_managed_block_without_duplication(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("CONTRIBUTING.md", "SECURITY.md"):
                (root / name).write_text("# Human\n\nKeep.\n", encoding="utf-8")
            mod.synchronize(root, config(), record())
            updated = record()
            updated["tag"] = "v3.15.0.2"
            updated["official_release_url"] = updated["official_release_url"].replace("0.1", "0.2")
            mod.synchronize(root, config(), updated)
            for name in ("CONTRIBUTING.md", "SECURITY.md"):
                text = (root / name).read_text(encoding="utf-8")
                self.assertIn("v3.15.0.2", text)
                self.assertNotIn("Latest PentaRelease — v3.15.0.1", text)
                self.assertEqual(text.count(mod.DEFAULT_START), 1)

    def test_missing_surface_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CONTRIBUTING.md").write_text("# Human\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                mod.synchronize(root, config(), record())

    def test_missing_release_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("CONTRIBUTING.md", "SECURITY.md"):
                (root / name).write_text("# Human\n", encoding="utf-8")
            broken = record()
            del broken["official_release_url"]
            with self.assertRaises(RuntimeError):
                mod.synchronize(root, config(), broken)


if __name__ == "__main__":
    unittest.main()
