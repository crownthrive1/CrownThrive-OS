from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "pentarelease"
    / "reconcile_pentadocs_metadata.py"
)
spec = importlib.util.spec_from_file_location("reconcile_pentadocs_metadata", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class PentaReleasePentaDocsMetadataTests(unittest.TestCase):
    def test_adds_sidebar_title_from_title_without_body_change(self) -> None:
        source = '---\ntitle: "Latest Release — v9.9.9.9"\ndescription: "x"\n---\n\n# Body\n'
        result, changed, reason = module.reconcile_text(source)
        self.assertTrue(changed)
        self.assertEqual(reason, "sidebar_title_added")
        self.assertIn('sidebarTitle: "Latest Release — v9.9.9.9"', result)
        self.assertTrue(result.endswith("\n# Body\n"))

    def test_updates_stale_sidebar_title(self) -> None:
        source = '---\ntitle: "Latest Release — v2"\nsidebarTitle: "Latest Release — v1"\n---\n\nBody\n'
        result, changed, reason = module.reconcile_text(source)
        self.assertTrue(changed)
        self.assertEqual(reason, "sidebar_title_updated")
        self.assertIn('sidebarTitle: "Latest Release — v2"', result)
        self.assertNotIn('sidebarTitle: "Latest Release — v1"', result)

    def test_is_idempotent(self) -> None:
        source = '---\ntitle: "Release FAQ"\nsidebarTitle: "Release FAQ"\n---\n\nBody\n'
        once, changed_once, _ = module.reconcile_text(source)
        twice, changed_twice, reason = module.reconcile_text(once)
        self.assertFalse(changed_once)
        self.assertFalse(changed_twice)
        self.assertEqual(reason, "already_converged")
        self.assertEqual(source, twice)

    def test_reconciles_exact_seven_release_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for relative in module.TARGET_PATHS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                title = Path(relative).stem
                path.write_text(
                    f'---\ntitle: "{title}"\ndescription: "x"\n---\n\nBody\n',
                    encoding="utf-8",
                )
            written = module.reconcile_root(root, write=True)
            checked = module.reconcile_root(root, write=False)
            self.assertEqual(written["state"], "RECONCILED")
            self.assertEqual(written["changed"], 7)
            self.assertEqual(checked["state"], "PASS")
            self.assertEqual(checked["changed"], 0)
            self.assertEqual(checked["targets"], 7)


if __name__ == "__main__":
    unittest.main()
