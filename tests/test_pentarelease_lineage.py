import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECIDE = ROOT / "scripts" / "pentarelease" / "decide.py"
POLICY = ROOT / ".pentarelease" / "policy.json"
AUTONOMOUS_WORKFLOW = ROOT / ".github" / "workflows" / "pentarelease-autonomous-awareness.yml"
PUBLISHER_WORKFLOW = ROOT / ".github" / "workflows" / "crownthrive-os-v2-release.yml"


class PentaReleaseLineageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temporary.name)
        self.repo = self.temp_root / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "PentaRelease Test")
        self.git("config", "user.email", "pentarelease@example.test")
        self.write("README.md", "source baseline\n")
        self.commit("chore: establish source baseline")
        self.base_sha = self.rev_parse("HEAD")

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args, check=True):
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=check,
            text=True,
            capture_output=True,
        )

    def rev_parse(self, ref):
        return self.git("rev-parse", ref).stdout.strip()

    def write(self, relative_path, content):
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, subject):
        self.git("add", ".")
        self.git("commit", "-m", subject)

    def add_divergent_release_tag(self, *, recorded_source=None, extra_path=None):
        version = "3.13.0.1"
        tag = f"v{version}"
        self.git("checkout", "-b", "release-side-branch")
        decision = {"tag": tag}
        manifest = {"version": version, "tag": tag, "decision": decision}
        if recorded_source is not None:
            manifest["source_head_sha"] = recorded_source
            decision["source_head_sha"] = recorded_source
        self.write(f"releases/{version}/MANIFEST.json", json.dumps(manifest))
        self.write(f"releases/{version}/RELEASE_NOTES.md", "generated release evidence\n")
        self.write(
            f".github/release-requests/crownthrive-os-{version}.json",
            json.dumps({"tag": tag, "target": "release-side-branch"}),
        )
        if extra_path is not None:
            self.write(extra_path, "not generated release evidence\n")
        self.commit(f"pentarelease(auto): materialize CrownThrive OS {version}")
        self.git("tag", tag)
        tag_sha = self.rev_parse(tag)
        self.git("checkout", "main")
        return tag_sha

    def add_target_delta(self):
        self.write(".github/workflows/new-governed-check.yml", "name: governed check\n")
        self.commit("ci: add governed check")
        return self.rev_parse("HEAD")

    def decide(self, *, legacy_allowlist=None):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        if legacy_allowlist is not None:
            policy["lineage"]["legacy_generated_release_parent_allowlist"] = legacy_allowlist
        policy_path = self.temp_root / "policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        output = self.temp_root / "decision.json"
        result = subprocess.run(
            [
                "python3",
                str(DECIDE),
                "--policy",
                str(policy_path),
                "--output",
                str(output),
            ],
            cwd=self.repo,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_legacy_generated_side_branch_uses_its_exact_parent_source(self):
        tag_sha = self.add_divergent_release_tag()
        head_sha = self.add_target_delta()

        decision = self.decide(
            legacy_allowlist=[
                {
                    "tag": "v3.13.0.1",
                    "tag_sha": tag_sha,
                    "source_head_sha": self.base_sha,
                }
            ]
        )

        self.assertTrue(decision["release"])
        self.assertEqual(decision["latest_tag"], "v3.13.0.1")
        self.assertEqual(decision["latest_tag_sha"], tag_sha)
        self.assertEqual(decision["source_baseline_sha"], self.base_sha)
        self.assertEqual(decision["source_head_sha"], head_sha)
        self.assertEqual(decision["lineage_resolution"], "generated_release_parent_legacy")
        self.assertEqual(decision["changed_files"], [".github/workflows/new-governed-check.yml"])
        self.assertEqual(decision["commit_count"], 1)

    def test_unrecorded_generated_side_branch_without_exact_legacy_entry_holds(self):
        self.add_divergent_release_tag()
        self.add_target_delta()

        decision = self.decide(legacy_allowlist=[])

        self.assertFalse(decision["release"])
        self.assertEqual(decision["decision"], "hold")
        self.assertEqual(decision["reason"], "divergent_latest_tag_source_head_missing")
        self.assertNotIn("version", decision)

    def test_recorded_generated_side_branch_uses_bound_source_head(self):
        self.add_divergent_release_tag(recorded_source=self.base_sha)
        self.add_target_delta()

        decision = self.decide()

        self.assertTrue(decision["release"])
        self.assertEqual(decision["source_baseline_sha"], self.base_sha)
        self.assertEqual(decision["lineage_resolution"], "generated_release_recorded_source")

    def test_recorded_source_that_is_not_tag_parent_holds(self):
        self.add_divergent_release_tag(recorded_source="f" * 40)
        self.add_target_delta()

        decision = self.decide()

        self.assertFalse(decision["release"])
        self.assertEqual(decision["decision"], "hold")
        self.assertEqual(decision["reason"], "divergent_latest_tag_source_head_parent_mismatch")
        self.assertNotIn("version", decision)

    def test_generated_tag_with_untrusted_content_holds(self):
        self.add_divergent_release_tag(
            recorded_source=self.base_sha,
            extra_path="runtime/unreviewed_release_payload.py",
        )
        self.add_target_delta()

        decision = self.decide()

        self.assertFalse(decision["release"])
        self.assertEqual(decision["decision"], "hold")
        self.assertEqual(decision["reason"], "divergent_latest_tag_changed_untrusted_paths")
        self.assertNotIn("version", decision)

    def test_generated_tag_parent_outside_target_history_holds(self):
        self.add_divergent_release_tag(recorded_source=self.base_sha)
        self.git("checkout", "--orphan", "unrelated-target")
        self.write(".github/workflows/unrelated.yml", "name: unrelated target\n")
        self.commit("ci: establish unrelated target")

        decision = self.decide()

        self.assertFalse(decision["release"])
        self.assertEqual(decision["decision"], "hold")
        self.assertEqual(decision["reason"], "divergent_latest_tag_source_not_in_target_history")
        self.assertNotIn("version", decision)


class PentaReleaseLineageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.autonomous = AUTONOMOUS_WORKFLOW.read_text(encoding="utf-8")
        cls.publisher = PUBLISHER_WORKFLOW.read_text(encoding="utf-8")

    def test_policy_requires_fail_closed_divergent_tag_resolution(self):
        lineage = self.policy["lineage"]
        self.assertIs(lineage["fail_closed_on_divergent_latest_tag"], True)
        self.assertIs(lineage["allow_legacy_generated_release_parent"], True)
        self.assertEqual(
            lineage["legacy_generated_release_parent_allowlist"],
            [
                {
                    "tag": "v3.13.0.1",
                    "tag_sha": "3b5ab399cc4a3014554f95736fcea7032972989a",
                    "source_head_sha": "eb2662b57e47384a85bdaa97df5a7ad9c13c78f2",
                }
            ],
        )
        self.assertIn("releases/{version}/MANIFEST.json", lineage["required_generated_release_files"])
        self.assertIn(
            ".github/release-requests/crownthrive-os-{version}.json",
            lineage["required_generated_release_files"],
        )

    def test_autonomous_package_persists_exact_lineage(self):
        for field in (
            "previous_release_tag_sha",
            "source_baseline_sha",
            "source_head_sha",
            "lineage_resolution",
        ):
            self.assertIn(field, self.autonomous)
        self.assertIn('test "$(git rev-parse HEAD^)" = "$SOURCE_HEAD_SHA"', self.autonomous)
        self.assertIn('if [ "$CURRENT_MAIN_SHA" != "$SOURCE_HEAD_SHA" ]', self.autonomous)

    def test_publisher_fails_closed_on_lineage_mismatch(self):
        self.assertIn(
            'test "$(git rev-parse "${PREVIOUS_RELEASE_TAG}^{commit}")" = "$PREVIOUS_RELEASE_TAG_SHA"',
            self.publisher,
        )
        self.assertIn(
            'git merge-base --is-ancestor "$SOURCE_BASELINE_SHA" "$SOURCE_HEAD_SHA"',
            self.publisher,
        )
        self.assertIn('git merge-base --is-ancestor "$SOURCE_HEAD_SHA" HEAD', self.publisher)
        self.assertIn('test "$SOURCE_BASELINE_SHA" = "$TAG_PARENT"', self.publisher)
        self.assertIn('generated_release_recorded_source|generated_release_parent_legacy)', self.publisher)
        self.assertIn('.lineage.legacy_generated_release_parent_allowlist[]', self.publisher)


if __name__ == "__main__":
    unittest.main()
