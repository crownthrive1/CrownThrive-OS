import json
import tempfile
import unittest
from pathlib import Path

from scripts.pentarelease import build_cie_subject as cie


class PentaReleaseCieSubjectTests(unittest.TestCase):
    def test_materializes_all_governed_dimensions_without_inventing_findings(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "MANIFEST.json"
            notes = root / "RELEASE_NOTES.md"
            provider = root / "provider.json"
            sums = root / "SHA256SUMS"
            manifest.write_text(json.dumps({
                "publisher": "PentaRelease",
                "why": "repair release convergence",
                "changed_files": ["README.md", "scripts/pentarelease/example.py"],
                "target_ref": "main",
            }), encoding="utf-8")
            notes.write_text("# Release\n\nRepair release convergence.\n", encoding="utf-8")
            provider.write_text(json.dumps({
                "html_url": "https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v3.48.0.0",
                "target_commitish": "main",
                "draft": False,
                "prerelease": False,
                "published_at": "2026-08-29T09:37:16Z",
                "created_at": "2026-08-29T09:35:24Z",
                "author": {"login": "github-actions[bot]"},
                "assets": [{"name": "MANIFEST.json"}, {"name": "SHA256SUMS"}],
            }), encoding="utf-8")
            sums.write_text("abc  MANIFEST.json\n", encoding="utf-8")

            subject = cie.build(
                "crownthrive1/CrownThrive-OS",
                "v3.48.0.0",
                "3.48.0.0",
                manifest,
                notes,
                provider,
                sums,
            )

            self.assertEqual(subject["subject_type"], "release")
            self.assertEqual(subject["findings"], [])
            self.assertEqual(set(subject["dimension_evidence"]), set(cie.DIMENSIONS))
            for dimension in cie.DIMENSIONS:
                self.assertGreaterEqual(len(subject["dimension_evidence"][dimension]), 1)
            self.assertFalse(subject["provenance"]["score_calculated_here"])
            self.assertFalse(subject["provenance"]["authority_manufactured"])

    def test_manifest_and_provider_readback_are_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(RuntimeError):
                cie.build(
                    "crownthrive1/CrownThrive-OS",
                    "v3.48.0.0",
                    "3.48.0.0",
                    root / "missing-manifest.json",
                    root / "missing-notes.md",
                    root / "missing-provider.json",
                    root / "missing-sums",
                )


if __name__ == "__main__":
    unittest.main()
