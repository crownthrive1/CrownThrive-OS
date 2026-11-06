"""Run the exact source resolver shell with inert GitHub reads and local Git."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/crownthrive-os-v2-release.yml"
TAG = "v3.95.3.0"
TARGET = "pentarelease/auto-deleted-source"

GH_STUB = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote
args = sys.argv[1:]
with open(os.environ["CALLS"], "a") as stream:
    stream.write(json.dumps(args) + "\n")
mode = os.environ["MODE"]
endpoint = "repos/crownthrive1/CrownThrive-OS"
if args == ["api", endpoint + "/releases", "--paginate", "--jq", ".[].tag_name"]:
    if mode == "read_error":
        raise SystemExit(1)
    print(Path(os.environ["RELEASE_TAGS_FILE"]).read_text())
elif args[:2] == ["api", endpoint + "/commits/" + os.environ["ENCODED_REF"]] and args[2:] == ["--jq", ".sha"]:
    if mode == "resolve_error":
        raise SystemExit(1)
    if mode == "malformed":
        print(os.environ["BAD_SHA"])
    else:
        # Model the commits endpoint: peel both lightweight and annotated tags.
        ref = unquote(os.environ["ENCODED_REF"])
        subprocess.run(["git", "rev-parse", ref + "^{commit}"], check=True)
else:
    raise SystemExit("unexpected API call or mutation: " + repr(args))
'''


def workflow_script(step):
    block = WORKFLOW.read_text().split("      - name: " + step + "\n", 1)[1]
    block = block.split("      - name:", 1)[0]
    return textwrap.dedent(block.split("        run: |\n", 1)[1])


class ReleaseSourceCheckoutTests(unittest.TestCase):
    def run_resolver(self, mode="existing", annotated=False, bad_sha="", tags=None, tag=TAG):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, text=True,
                                               stderr=subprocess.DEVNULL).strip()

            git("init", "--quiet")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            git("commit", "--quiet", "--allow-empty", "-m", "release source")
            sha = git("rev-parse", "HEAD")
            git("branch", TARGET)
            if annotated:
                git("tag", "-a", tag, "-m", "annotated release")
            else:
                git("tag", tag)
            # The requested branch is actually deleted; the tag still reaches it.
            git("branch", "-D", TARGET)
            git("commit", "--quiet", "--allow-empty", "-m", "later control commit")
            # A same-named branch must never win over the qualified release tag.
            git("branch", tag)
            binary = root / "bin"
            binary.mkdir()
            gh = binary / "gh"
            gh.write_text(GH_STUB)
            gh.chmod(0o755)
            calls = root / "calls.jsonl"
            output = root / "github-env"
            release_tags = root / "release-tags"
            release_tags.write_text(tag if tags is None else tags)
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                       MODE=mode, CALLS=str(calls), TAG=tag, TARGET=TARGET,
                       GITHUB_REPOSITORY="crownthrive1/CrownThrive-OS",
                       GITHUB_ENV=str(output), BAD_SHA=bad_sha,
                       ENCODED_REF=quote("refs/tags/" + tag, safe=""),
                       RELEASE_TAGS_FILE=str(release_tags))
            result = subprocess.run(["bash", "-c", workflow_script("Resolve immutable release source")],
                                    cwd=root, env=env, text=True, capture_output=True, timeout=10)
            emitted = output.read_text() if output.exists() else ""
            invoked = [json.loads(line) for line in calls.read_text().splitlines()]
            if result.returncode == 0 and emitted != "SOURCE_REF=" + TARGET + "\n":
                source = emitted.removeprefix("SOURCE_REF=").strip()
                git("checkout", "--detach", source)
                self.assertEqual(git("rev-parse", "HEAD"), sha)
            return result, invoked, emitted, sha

    def test_deleted_branch_uses_exact_tag_commit_for_both_tag_types(self):
        for annotated in (False, True):
            with self.subTest(annotated=annotated):
                result, calls, emitted, sha = self.run_resolver(annotated=annotated)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(emitted, "SOURCE_REF=" + sha + "\n")
                self.assertEqual(len(calls), 2)
                self.assertIn("/commits/refs%2Ftags%2F", calls[1][1])

    def test_unpublished_release_retains_requested_target(self):
        for tags in ("", "v3.95.3.00\nv3x95x3x0\nother-tag"):
            with self.subTest(tags=tags):
                result, calls, emitted, _ = self.run_resolver(tags=tags)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(emitted, "SOURCE_REF=" + TARGET + "\n")
                self.assertEqual(len(calls), 1)

    def test_all_release_pages_are_read_without_short_circuit_pipe_failure(self):
        tags = TAG + "\n" + "\n".join("other-tag-" + str(i) for i in range(10000))
        result, calls, emitted, sha = self.run_resolver(tags=tags)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--paginate", calls[0])
        self.assertEqual(emitted, "SOURCE_REF=" + sha + "\n")

    def test_slash_in_tag_is_encoded(self):
        result, calls, _, _ = self.run_resolver(tag="release/v3.95.3.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(calls[1][1].endswith("refs%2Ftags%2Frelease%2Fv3.95.3.0"))

    def test_read_and_resolution_errors_fail_before_checkout(self):
        for mode, count in (("read_error", 1), ("resolve_error", 2)):
            with self.subTest(mode=mode):
                result, calls, emitted, _ = self.run_resolver(mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(emitted, "")
                self.assertEqual(len(calls), count)

    def test_malformed_commit_sha_fails_closed(self):
        for sha in ("", "null", "main", "a" * 39, "a" * 41, "g" * 40,
                    "a" * 40 + "\nTARGET=evil", "a" * 40 + " trailing"):
            with self.subTest(sha=sha):
                result, calls, emitted, _ = self.run_resolver(mode="malformed", bad_sha=sha)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(emitted, "")
                self.assertEqual(len(calls), 2)

    def test_workflow_wires_authenticated_resolver_before_checkout(self):
        source = WORKFLOW.read_text()
        block = source.split("      - name: Resolve immutable release source\n", 1)[1]
        self.assertIn("GH_TOKEN: ${{ github.token }}", block.split("      - name:", 1)[0])
        checkout = block.split("      - name: Checkout requested release source\n", 1)[1].split("      - name:", 1)[0]
        self.assertIn("ref: ${{ env.SOURCE_REF }}", checkout)
        script = workflow_script("Resolve immutable release source")
        self.assertNotIn('echo "TARGET=', script)
        self.assertIn('= "$TARGET"', workflow_script("Validate PentaRelease package contract"))
        self.assertIn('= "$TARGET"', workflow_script("Publish or update GitHub Release"))


if __name__ == "__main__":
    unittest.main()
