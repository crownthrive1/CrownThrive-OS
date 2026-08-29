import json
import tempfile
import unittest
from pathlib import Path

from scripts.pentarelease import pentadocs_group as pg


def policy():
    return {
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


def docs(tab_count=8):
    tabs = [{"tab": "CrownThrive OS", "pages": [{"group": "Start Here", "pages": ["index"]}]}]
    tabs.extend({"tab": f"Existing {i}", "pages": ["index"]} for i in range(1, tab_count))
    return {"navigation": {"tabs": tabs}}


class PentaReleasePentaDocsGroupTests(unittest.TestCase):
    def write_fixture(self, root: Path, docs_value=None, policy_value=None):
        (root / ".pentarelease").mkdir(parents=True, exist_ok=True)
        (root / "docs.json").write_text(json.dumps(docs_value or docs()), encoding="utf-8")
        (root / ".pentarelease/policy.json").write_text(json.dumps(policy_value or policy()), encoding="utf-8")
        for page in (policy_value or policy())["release_surface"]["pentadocs"]["pages"]:
            p = root / f"{page}.mdx"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# Test\n", encoding="utf-8")

    def test_sync_adds_group_without_creating_ninth_tab(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_fixture(root)
            result = pg.sync(root, root / ".pentarelease/policy.json")
            current = json.loads((root / "docs.json").read_text())
            self.assertEqual(len(current["navigation"]["tabs"]), 8)
            crown = current["navigation"]["tabs"][0]
            self.assertEqual(crown["pages"][0]["group"], "Start Here")
            self.assertEqual(crown["pages"][-1]["group"], "PentaRelease")
            self.assertFalse(result["top_level_tab_created"])

    def test_sync_updates_only_managed_group(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_fixture(root)
            pg.sync(root, root / ".pentarelease/policy.json")
            current = json.loads((root / "docs.json").read_text())
            current["navigation"]["tabs"][0]["pages"].insert(1, {"group": "Human Group", "pages": ["human"]})
            (root / "docs.json").write_text(json.dumps(current), encoding="utf-8")
            pg.sync(root, root / ".pentarelease/policy.json")
            current = json.loads((root / "docs.json").read_text())
            groups = [x.get("group") for x in current["navigation"]["tabs"][0]["pages"] if isinstance(x, dict)]
            self.assertIn("Start Here", groups)
            self.assertIn("Human Group", groups)
            self.assertEqual(groups.count("PentaRelease"), 1)

    def test_supports_canonical_groups_navigation_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = policy()
            p["release_surface"]["pentadocs"]["tab"] = "Releases & Evidence"
            value = {
                "navigation": {
                    "tabs": [
                        {
                            "tab": "Releases & Evidence",
                            "groups": [
                                {"group": "Release Overview", "pages": ["releases/index"]},
                                {
                                    "group": "PentaRelease",
                                    "icon": "box-archive",
                                    "pages": ["pentarelease/latest", "pentarelease/evidence"],
                                },
                            ],
                        }
                    ]
                }
            }
            self.write_fixture(root, docs_value=value, policy_value=p)
            result = pg.sync(root, root / ".pentarelease/policy.json")
            self.assertEqual(result["navigation_key"], "groups")
            self.assertTrue(result["unique_route_ownership_verified"])
            self.assertTrue(pg.inspect(root, root / ".pentarelease/policy.json")["healthy"])

    def test_duplicate_route_outside_canonical_group_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            value = docs()
            value["navigation"]["tabs"][1]["pages"] = [
                {"group": "Other", "pages": ["pentarelease/latest"]}
            ]
            self.write_fixture(root, docs_value=value)
            with self.assertRaises(RuntimeError):
                pg.sync(root, root / ".pentarelease/policy.json")

    def test_conflicting_unmanaged_group_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            value = docs()
            value["navigation"]["tabs"][0]["pages"].append({"group": "PentaRelease", "pages": ["wrong"]})
            self.write_fixture(root, docs_value=value)
            with self.assertRaises(RuntimeError):
                pg.sync(root, root / ".pentarelease/policy.json")

    def test_missing_target_tab_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            value = docs()
            value["navigation"]["tabs"][0]["tab"] = "Other"
            self.write_fixture(root, docs_value=value)
            with self.assertRaises(RuntimeError):
                pg.sync(root, root / ".pentarelease/policy.json")

    def test_more_than_eight_tabs_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_fixture(root, docs_value=docs(9))
            with self.assertRaises(RuntimeError):
                pg.sync(root, root / ".pentarelease/policy.json")

    def test_health_requires_nested_group_and_pages(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_fixture(root)
            self.assertFalse(pg.inspect(root, root / ".pentarelease/policy.json")["healthy"])
            pg.sync(root, root / ".pentarelease/policy.json")
            self.assertTrue(pg.inspect(root, root / ".pentarelease/policy.json")["healthy"])


if __name__ == "__main__":
    unittest.main()
