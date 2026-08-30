import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pentarelease" / "provider_release.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "pentarelease-comprehensive-release-surface.yml"

spec = importlib.util.spec_from_file_location("provider_release", MODULE_PATH)
provider_release = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(provider_release)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def http_error(code, body=b'{"message":"provider unavailable"}'):
    return urllib.error.HTTPError(
        url="https://api.github.com/repos/crownthrive1/CrownThrive-OS/releases/tags/v3.63.3.0",
        code=code,
        msg="error",
        hdrs={"Retry-After": "1"},
        fp=io.BytesIO(body),
    )


class ProviderReleaseTests(unittest.TestCase):
    def test_select_latest_version_tag_uses_numeric_version_order(self):
        tags = ["v3.9.0.0", "v3.63.2.0", "v3.63.3.0", "not-a-release", "v3.10.0.0"]
        self.assertEqual(
            provider_release.select_latest_version_tag(tags),
            "v3.63.3.0",
        )

    def test_provider_403_retries_then_verifies_exact_release(self):
        calls = []
        sleeps = []
        payload = {
            "tag_name": "v3.63.3.0",
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v3.63.3.0",
            "assets": [],
        }

        def opener(request, timeout=20):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise http_error(403)
            return FakeResponse(payload)

        result = provider_release.fetch_provider_release(
            "crownthrive1/CrownThrive-OS",
            "v3.63.3.0",
            "token",
            attempts=2,
            sleep_fn=sleeps.append,
            opener=opener,
        )
        self.assertEqual(result["tag_name"], "v3.63.3.0")
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [1])

    def test_provider_retry_exhaustion_is_hold(self):
        def opener(request, timeout=20):
            raise http_error(403)

        with self.assertRaisesRegex(
            provider_release.ProviderReleaseError,
            "provider_read_retry_exhausted",
        ):
            provider_release.fetch_provider_release(
                "crownthrive1/CrownThrive-OS",
                "v3.63.3.0",
                "token",
                attempts=2,
                sleep_fn=lambda _: None,
                opener=opener,
            )

    def test_provider_404_does_not_fall_back_to_older_release(self):
        def opener(request, timeout=20):
            raise http_error(404, b'{"message":"Not Found"}')

        with self.assertRaisesRegex(
            provider_release.ProviderReleaseError,
            "provider_release_not_found:v3.63.3.0",
        ):
            provider_release.fetch_provider_release(
                "crownthrive1/CrownThrive-OS",
                "v3.63.3.0",
                "token",
                attempts=12,
                sleep_fn=lambda _: None,
                opener=opener,
            )

    def test_mismatched_or_draft_release_fails_closed(self):
        with self.assertRaisesRegex(
            provider_release.ProviderReleaseError,
            "provider_release_tag_mismatch",
        ):
            provider_release.validate_provider_release(
                {"tag_name": "v3.63.2.0", "draft": False},
                "v3.63.3.0",
            )

        with self.assertRaisesRegex(
            provider_release.ProviderReleaseError,
            "provider_release_not_published",
        ):
            provider_release.validate_provider_release(
                {"tag_name": "v3.63.3.0", "draft": True},
                "v3.63.3.0",
            )

    def test_verified_payload_normalizes_for_release_surface_without_second_lookup(self):
        payload = {
            "tag_name": "v3.63.3.0",
            "name": "PentaRelease v3.63.3.0",
            "html_url": "https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v3.63.3.0",
            "draft": False,
            "prerelease": False,
            "target_commitish": "pentarelease/auto-3.63.3.0-33335905255-1",
            "body": "release body",
            "published_at": "2026-08-30T21:27:48Z",
            "created_at": "2026-08-30T21:27:48Z",
            "assets": [
                {
                    "name": "MANIFEST.json",
                    "size": 123,
                    "browser_download_url": "https://example.invalid/MANIFEST.json",
                }
            ],
        }
        normalized = provider_release.normalize_for_release_surface(payload, "v3.63.3.0")
        self.assertEqual(normalized["tagName"], "v3.63.3.0")
        self.assertEqual(normalized["assets"][0]["name"], "MANIFEST.json")
        self.assertEqual(normalized["assets"][0]["size"], 123)
        self.assertFalse(normalized["isDraft"])

    def test_verified_release_file_rejects_tag_drift(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "release.json"
            path.write_text(
                json.dumps({"tag_name": "v3.63.2.0", "draft": False}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                provider_release.ProviderReleaseError,
                "provider_release_tag_mismatch",
            ):
                provider_release.load_verified_release(path, "v3.63.3.0")


class ProviderReleaseWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_workflow_uses_local_tag_plus_verified_provider_adapter(self):
        self.assertIn("scripts/pentarelease/provider_release.py", self.text)
        self.assertIn("provider_release.py \"${ARGS[@]}\"", self.text)
        self.assertIn("/tmp/pentarelease-release.json", self.text)
        self.assertNotIn("gh release list", self.text)
        self.assertNotIn("gh release view", self.text)

    def test_materialization_reuses_verified_release_payload(self):
        self.assertIn("provider_release.py surface", self.text)
        self.assertIn("--release-json /tmp/pentarelease-release.json", self.text)
        self.assertNotIn("python3 scripts/pentarelease/release_surface.py", self.text)

    def test_provider_writes_and_existing_asset_downloads_have_bounded_retry(self):
        self.assertIn("gh_retry gh release download", self.text)
        self.assertIn("gh_retry gh release upload", self.text)
        self.assertIn("gh_retry gh release edit", self.text)
        self.assertNotIn("--clobber || true", self.text)
        self.assertGreaterEqual(self.text.count("else\n                rc=$?"), 2)

    def test_provider_is_independently_read_back_after_write_and_in_production_proof(self):
        self.assertGreaterEqual(
            self.text.count("scripts/pentarelease/provider_release.py read"),
            2,
        )
        self.assertIn("Final independent provider proof", self.text)
        self.assertIn("Provider comprehensive release readback: verified", self.text)


if __name__ == "__main__":
    unittest.main()
