"""Exercise the actual publisher shell without network or GitHub writes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/crownthrive-os-v2-release.yml"

GH_STUB = r"""#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
args = sys.argv[1:]
with open(os.environ["CALLS"], "a") as stream:
    stream.write(json.dumps(args) + "\n")
mode = os.environ.get("MODE", "existing")
if args[:2] == ["release", "view"]:
    if mode in ("new", "unreadable"):
        raise SystemExit(1)
    print(os.environ["RELEASE_JSON"])
elif args[:2] == ["release", "download"]:
    if mode == "download_error":
        raise SystemExit(1)
    destination = Path(args[args.index("--dir") + 1])
    for name in ("MANIFEST.json", "RELEASE_NOTES.md"):
        data = (Path(os.environ["PACKAGE"]) / name).read_bytes()
        if name == os.environ.get("MISMATCH"):
            data += b"changed"
        (destination / name).write_bytes(data)
elif args[:2] == ["release", "create"]:
    if mode != "new":
        raise SystemExit(1)
elif args[:2] == ["release", "upload"]:
    if mode != "new":
        raise SystemExit(1)
else:
    raise SystemExit("unexpected mutation: " + repr(args))
"""


class ExistingReleasePreservationTests(unittest.TestCase):
    def run_publisher(self, mode="existing", mismatch="", metadata=None):
        workflow = yaml.safe_load(WORKFLOW.read_text())
        script = next(
            step["run"] for step in workflow["jobs"]["publish"]["steps"]
            if step["name"] == "Publish or update GitHub Release"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "package"
            package.mkdir()
            (package / "MANIFEST.json").write_text('{"tag":"v3.95.2.0"}\n')
            (package / "RELEASE_NOTES.md").write_text("# Original release notes\n")
            binary = root / "bin"
            binary.mkdir()
            gh = binary / "gh"
            gh.write_text(GH_STUB)
            gh.chmod(0o755)
            calls = root / "calls.jsonl"
            release = {
                "tagName": "v3.95.2.0",
                "name": "CrownThrive OS 3.95.2.0",
                "targetCommitish": "release/exact-source",
                "isDraft": False,
                "isPrerelease": False,
            }
            release.update(metadata or {})
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                       CALLS=str(calls), MODE=mode, MISMATCH=mismatch,
                       PACKAGE=str(package), TAG="v3.95.2.0",
                       TITLE="CrownThrive OS 3.95.2.0", TARGET="release/exact-source",
                       DRAFT="false", PRERELEASE="false",
                       ZIP="package.zip", TGZ="package.tar.gz",
                       RELEASE_JSON=json.dumps(release))
            result = subprocess.run(["bash", "-c", script], cwd=root, env=env,
                                    text=True, capture_output=True, timeout=10)
            invoked = [json.loads(line) for line in calls.read_text().splitlines()]
            return result, invoked

    def test_existing_release_is_read_only(self):
        result, calls = self.run_publisher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call[1] for call in calls], ["view", "download"])
        self.assertIn("preserving published notes and assets", result.stdout)

    def test_changed_original_inputs_fail_without_mutation(self):
        for name in ("MANIFEST.json", "RELEASE_NOTES.md"):
            with self.subTest(name=name):
                result, calls = self.run_publisher(mismatch=name)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([call[1] for call in calls], ["view", "download"])

    def test_identity_or_publication_state_mismatch_fails_without_mutation(self):
        for key, value in {
            "tagName": "v0.0.0.0", "name": "Different release",
            "targetCommitish": "different-source", "isDraft": True, "isPrerelease": True,
        }.items():
            with self.subTest(key=key):
                result, calls = self.run_publisher(metadata={key: value})
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([call[1] for call in calls], ["view"])

    def test_download_failure_preserves_existing_release(self):
        result, calls = self.run_publisher(mode="download_error")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([call[1] for call in calls], ["view", "download"])

    def test_new_release_can_be_created_without_clobber(self):
        result, calls = self.run_publisher(mode="new")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call[1] for call in calls], ["view", "create", "upload"])
        self.assertNotIn("--clobber", calls[-1])

    def test_failed_lookup_and_creation_never_upload(self):
        result, calls = self.run_publisher(mode="unreadable")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([call[1] for call in calls], ["view", "create"])


if __name__ == "__main__":
    unittest.main()
