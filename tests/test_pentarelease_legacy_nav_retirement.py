import json
import tempfile
import unittest
from pathlib import Path

from scripts.pentarelease import pentadocs_group
from scripts.pentarelease import release_surface


POLICY = {
    "release_surface": {
        "max_pentadocs_tabs": 8,
        "state_file": ".pentarelease/state/release-surface.json",
        "pentadocs": {
            "enabled": True,
            "config": "docs.json",
            "tab": "CrownThrive OS",
            "group": "PentaRelease",
            "pages": ["pentarelease/latest", "pentarelease/evidence"],
        },
    }
}


class PentaReleaseLegacyNavRetirementTests(unittest.TestCase):
    def test_retired_top_level_ownership_cannot_replace_canonical_tab(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".pentarelease").mkdir(parents=True)
            (root / "pentarelease").mkdir(parents=True)
            for page in POLICY["release_surface"]["pentadocs"]["pages"]:
                (root / f"{page}.mdx").write_text("# page\n", encoding="utf-8")

            original_pages = [{"group": "Start Here", "pages": ["index"]}]
            docs = {
                "navigation": {
                    "tabs": [
                        {"tab": "CrownThrive OS", "pages": original_pages.copy()},
                        *[{"tab": f"Existing {i}", "pages": ["index"]} for i in range(1, 8)],
                    ]
                }
            }
            (root / "docs.json").write_text(json.dumps(docs), encoding="utf-8")
            (root / ".pentarelease/policy.json").write_text(json.dumps(POLICY), encoding="utf-8")

            state = {
                "pentadocs_nav": {
                    "tab": "CrownThrive OS",
                    "created_by_pentarelease": False,
                    "status": "legacy_top_level_ownership_retired",
                },
                "pentadocs_group": {
                    "tab": "CrownThrive OS",
                    "group": "PentaRelease",
                    "managed_by_pentarelease": True,
                    "top_level_tab_created": False,
                    "pages": POLICY["release_surface"]["pentadocs"]["pages"],
                },
            }

            state = release_surface.sync_pentadocs_nav(root, POLICY, state)
            after_legacy = json.loads((root / "docs.json").read_text(encoding="utf-8"))
            crown = after_legacy["navigation"]["tabs"][0]
            self.assertIn("pages", crown)
            self.assertNotIn("groups", crown)
            self.assertEqual(crown["pages"], original_pages)
            self.assertFalse(state["pentadocs_nav"]["created_by_pentarelease"])

            pentadocs_group.sync(root, root / ".pentarelease/policy.json")
            final = json.loads((root / "docs.json").read_text(encoding="utf-8"))
            crown = final["navigation"]["tabs"][0]
            self.assertEqual(len(final["navigation"]["tabs"]), 8)
            self.assertEqual(crown["pages"][0], original_pages[0])
            self.assertEqual(crown["pages"][-1]["group"], "PentaRelease")
            self.assertNotIn("groups", crown)

    def test_repository_state_never_claims_canonical_tab_ownership(self):
        root = Path(__file__).resolve().parents[1]
        state = json.loads((root / ".pentarelease/state/release-surface.json").read_text(encoding="utf-8"))
        legacy = state.get("pentadocs_nav") or {}
        group = state.get("pentadocs_group") or {}
        self.assertEqual(legacy.get("tab"), "CrownThrive OS")
        self.assertFalse(legacy.get("created_by_pentarelease"))
        self.assertEqual(group.get("group"), "PentaRelease")
        self.assertFalse(group.get("top_level_tab_created"))
        self.assertTrue(group.get("managed_by_pentarelease"))


if __name__ == "__main__":
    unittest.main()
