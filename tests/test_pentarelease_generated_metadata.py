"""Generated release metadata must converge without a downstream repair pass."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.pentarelease import enrich_release_intelligence as intelligence
from scripts.pentarelease import reconcile_pentadocs_metadata as metadata
from scripts.pentarelease import release_surface as surface


class GeneratedMetadataTests(unittest.TestCase):
    def assert_converged(self, root):
        report = metadata.reconcile_root(root, write=False)
        self.assertEqual(report["state"], "PASS", report)
        self.assertEqual(report["targets"], 7)
        self.assertEqual(report["changed"], 0)
        self.assertEqual(report["hard_failures"], 0)
        for relative in metadata.TARGET_PATHS:
            page = (root / relative).read_text(encoding="utf-8")
            reconciled, changed, reason = metadata.reconcile_text(page)
            self.assertFalse(changed)
            self.assertEqual(reason, "already_converged")
            self.assertEqual(reconciled, page)

    def test_helpers_preserve_body_and_escape_frontmatter(self):
        values = (
            "Latest Release — v3.93.0.1",
            'Release "quoted": # notes \\ path',
            "CrownThrive's release 👑",
            "Line one\n---\nsidebarTitle: injected\r\tend",
        )
        body = '# Original heading\n\n```json\n{"state": "HOLD"}\n```\n\n'
        for renderer in (surface.docs_page, intelligence.mdx):
            for value in values:
                with self.subTest(renderer=renderer.__name__, value=value):
                    rendered = renderer(title=value, description=value, body=body)
                    frontmatter, actual_body = rendered[4:].split("\n---\n\n", 1)
                    self.assertEqual(len(frontmatter.splitlines()), 3)
                    fields = dict(line.split(": ", 1) for line in frontmatter.splitlines())
                    self.assertEqual(set(fields), {"title", "sidebarTitle", "description"})
                    self.assertEqual(fields["title"], fields["sidebarTitle"])
                    for scalar in fields.values():
                        self.assertEqual(json.loads(scalar), value)
                    self.assertEqual(actual_body, body.rstrip() + "\n")
                    self.assertEqual(metadata.reconcile_text(rendered),
                                     (rendered, False, "already_converged"))

    def test_existing_heading_behavior_is_preserved(self):
        body = "## Detail\n\nContent\n\n"
        self.assertTrue(surface.docs_page("Title", body, "Description").endswith(
            "\n\n# Title\n\n" + body.rstrip() + "\n"))
        self.assertTrue(intelligence.mdx("Title", "Description", body).endswith(
            "\n\n" + body.rstrip() + "\n"))

    def write_surface(self, root, tag, state):
        record = {"tag": tag, "payload_costs": {}, "cie_score": {},
                  "data_availability": {}, "evidence": {}, "provenance": {}}
        # Body renderers are independent of metadata; keep fixture evidence inert.
        with mock.patch.object(surface, "render_comprehensive_block", return_value="# Release\n\nHOLD"), \
             mock.patch.object(surface, "render_faq", return_value="# FAQ\n\nUnknown"), \
             mock.patch.object(surface, "render_changelog", return_value="# Changelog\n\nFixture"):
            return surface.write_pentadocs_pages(root, record, state)

    def test_surface_writer_all_seven_pages_and_version_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {}
            for tag in ("v3.93.0.1", 'v3.94.0.1-"preview"'):
                state = self.write_surface(root, tag, state)
                self.assert_converged(root)
                latest = (root / "pentarelease/latest.mdx").read_text(encoding="utf-8")
                title = json.dumps(f"Latest Release — {tag}", ensure_ascii=False)
                self.assertIn(f"title: {title}\nsidebarTitle: {title}\n", latest)
                self.assertEqual(len(state["pentadocs_pages"]), 7)
                for entry in state["pentadocs_pages"].values():
                    self.assertTrue(entry["created_by_pentarelease"])
                    self.assertEqual(entry["last_release"], tag)

    def test_surface_writer_preserves_unmanaged_page_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "pentarelease/latest.mdx"
            page.parent.mkdir()
            original = '---\ntitle: "Unmanaged"\n---\n\nOriginal content\n'
            page.write_text(original, encoding="utf-8")
            state = self.write_surface(root, "v3.94.0.1", {})
            self.assertEqual(page.read_text(encoding="utf-8"), original)
            self.assertFalse(state["pentadocs_pages"]["pentarelease/latest.mdx"]["created_by_pentarelease"])
            self.assertEqual(state["pentadocs_pages"]["pentarelease/latest.mdx"]["status"], "collision_preserved")

    def test_intelligence_main_all_seven_pages_and_version_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root / "dist"
            dist.mkdir()
            evidence = root / "runtime.json"
            evidence.write_text("{}", encoding="utf-8")
            for tag in ("v3.93.0.1", 'v3.94.0.1-"preview"'):
                (dist / "PENTARELEASE_RELEASE_RECORD.json").write_text(
                    json.dumps({"tag": tag, "title": "Fixture release"}), encoding="utf-8")
                argv = ["enrich_release_intelligence.py", "--repository", "fixture/repository",
                        "--tag", tag, "--runtime-evidence", str(evidence),
                        "--dist", str(dist), "--root", str(root)]
                with mock.patch("sys.argv", argv), \
                     mock.patch.object(intelligence, "cmd_json", return_value={}) as provider, \
                     contextlib.redirect_stdout(io.StringIO()):
                    intelligence.main()
                provider.assert_called_once_with("gh", "api", f"/repos/fixture/repository/releases/tags/{tag}")
                self.assert_converged(root)
                latest = (root / "pentarelease/latest.mdx").read_text(encoding="utf-8")
                title = json.dumps(f"Latest Release — {tag}", ensure_ascii=False)
                self.assertIn(f"title: {title}\nsidebarTitle: {title}\n", latest)


if __name__ == "__main__":
    unittest.main()
