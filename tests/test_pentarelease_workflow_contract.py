import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPREHENSIVE_WORKFLOW = ROOT / ".github" / "workflows" / "pentarelease-comprehensive-release-surface.yml"
AWARENESS_WORKFLOW = ROOT / ".github" / "workflows" / "pentarelease-autonomous-awareness.yml"
RECONCILER_WORKFLOW = ROOT / ".github" / "workflows" / "pentarelease-pr-backlog-reconciler.yml"
DECISION_ENGINE = ROOT / "scripts" / "pentarelease" / "decide.py"


class PentaReleaseWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = COMPREHENSIVE_WORKFLOW.read_text(encoding="utf-8")
        cls.awareness_text = AWARENESS_WORKFLOW.read_text(encoding="utf-8")
        cls.reconciler_text = RECONCILER_WORKFLOW.read_text(encoding="utf-8")
        cls.decision_text = DECISION_ENGINE.read_text(encoding="utf-8")

    def test_never_direct_pushes_protected_main(self):
        self.assertNotIn('git push origin "$HEAD_SHA":refs/heads/main', self.text)
        self.assertNotIn('git push origin HEAD:main', self.text)

    def test_provider_identity_gap_is_explicit_hold(self):
        self.assertIn("HOLD_PR_PROVIDER_IDENTITY", self.text)
        self.assertIn("HOLD_PR_MERGE_IDENTITY", self.text)

    def test_action_required_is_hold_without_assuming_provider_cause(self):
        self.assertIn('RUN_CONCLUSION" = "action_required', self.text)
        self.assertIn("PR workflow returned action_required", self.text)
        self.assertIn("specific provider approval or eligibility requirement", self.text)
        self.assertIn("PR-bound validation is not yet proven", self.text)
        self.assertNotIn("recursive identity", self.text)
        self.assertIn('promotion_state=HOLD_PR_PROVIDER_IDENTITY', self.text)
        self.assertIn('RUN_CONCLUSION" != "success', self.text)
        self.assertIn("exit 46", self.text)

    def test_action_required_branch_preserves_exact_head_hold_and_exit(self):
        # Execute only the real diagnostic branch with synthetic provider state.
        # No provider commands, approval, rerun, or merge are executed.
        guard = '            if [ "$RUN_HEAD" = "$HEAD_SHA" ] && [ "$RUN_STATUS" = "completed" ] && [ "$RUN_CONCLUSION" = "action_required" ]; then'
        start = self.text.index(guard)
        end = self.text.index("\n            fi", start) + len("\n            fi")
        script = (
            "set -euo pipefail\n"
            + self.text[start:end]
            + '\nprintf "continued=true\\n" >> "$GITHUB_OUTPUT"\n'
        )
        head = "a" * 40
        cases = (
            (head, "completed", "action_required", True),
            ("b" * 40, "completed", "action_required", False),
            (head, "in_progress", "action_required", False),
            (head, "completed", "success", False),
            (head, "completed", "failure", False),
        )
        for run_head, status, conclusion, held in cases:
            with self.subTest(run_head=run_head, status=status, conclusion=conclusion):
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / "github-output"
                    result = subprocess.run(
                        ["bash", "-c", script],
                        env={
                            "RUN_HEAD": run_head,
                            "HEAD_SHA": head,
                            "RUN_STATUS": status,
                            "RUN_CONCLUSION": conclusion,
                            "GITHUB_OUTPUT": str(output),
                            "PR_URL": "https://github.com/example/repository/pull/1",
                            "BRANCH": "pentarelease/surface-test",
                        },
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if held:
                        self.assertEqual(
                            output.read_text(),
                            "promotion_state=HOLD_PR_PROVIDER_IDENTITY\n"
                            "pr_url=https://github.com/example/repository/pull/1\n"
                            "branch=pentarelease/surface-test\n",
                        )
                        self.assertIn("PR workflow returned action_required", result.stdout)
                        self.assertIn("PR-bound validation is not yet proven", result.stdout)
                        self.assertNotIn("recursive identity", result.stdout)
                    else:
                        self.assertEqual(output.read_text(), "continued=true\n")
                        self.assertEqual(result.stdout, "")

    def test_reconciliation_has_local_and_provider_preflight(self):
        self.assertIn("Determine reconciliation need", self.text)
        self.assertIn("local_ready=", self.text)
        self.assertIn("provider_ready=", self.text)
        self.assertIn("needs_sync=", self.text)

    def test_same_release_can_short_circuit(self):
        self.assertIn("ALREADY_SYNCHRONIZED", self.text)
        self.assertIn("steps.preflight.outputs.needs_sync == 'true'", self.text)

    def test_pending_branch_is_stable_per_release_and_base(self):
        self.assertIn('BRANCH="pentarelease/surface-${SAFE_TAG}-${BASE_SHA:0:12}"', self.text)
        self.assertIn('git ls-remote --heads origin "$BRANCH"', self.text)

    def test_pr_specific_gate_is_required_before_merge(self):
        self.assertIn("--event pull_request", self.text)
        self.assertIn('RUN_HEAD" = "$HEAD_SHA', self.text)
        self.assertIn('RUN_CONCLUSION" = "success', self.text)
        self.assertIn('gh pr merge "$PR_URL"', self.text)

    def test_release_payload_contract_is_complete(self):
        for name in (
            "PENTARELEASE_COMPREHENSIVE_RELEASE.md",
            "PENTARELEASE_RELEASE_RECORD.json",
            "PENTARELEASE_COSTS.json",
            "PENTARELEASE_CIE_SCORE.json",
            "PENTARELEASE_DATA_CATALOG.json",
            "PENTARELEASE_EVIDENCE.json",
            "PENTARELEASE_FAQ.md",
            "PENTARELEASE_CHANGELOG.md",
        ):
            self.assertIn(name, self.text)

    def test_generated_pentadocs_are_normalized_before_governance(self):
        self.assertIn("python3 scripts/pentarelease/pentadocs_group.py", self.text)
        self.assertIn("python3 scripts/pentadocs_quality.py --apply", self.text)
        self.assertIn("python3 scripts/validate_docs.py", self.text)
        self.assertIn("data/documentation/pentadocs-page-profiles.v1.json", self.text)

    def test_release_surface_uses_existing_canonical_tab_without_ninth_tab(self):
        self.assertIn("PentaDocs top-level tabs: <=8", self.text)
        self.assertIn("managed PentaRelease group inside the existing CrownThrive OS PentaDocs tab", self.text)
        self.assertIn("pentadocs_group.inspect", self.text)
        self.assertNotIn('names.count("Releases & Evidence") == 1', self.text)

    def test_reconciler_keeps_least_privilege_and_retains_branches(self):
        self.assertIn("contents: read", self.reconciler_text)
        self.assertIn('gh pr close "$number" --repo "$REPO" --comment "$NOTE"', self.reconciler_text)
        self.assertNotIn("--delete-branch", self.reconciler_text)
        self.assertIn("Generated branches retained under least privilege", self.reconciler_text)
        self.assertIn("Remote branch deletion remains advisory", self.reconciler_text)

    def test_reconciler_still_requires_release_evidence_and_bot_identity(self):
        self.assertIn('index("MANIFEST.json")', self.reconciler_text)
        self.assertIn('index("RELEASE_NOTES.md")', self.reconciler_text)
        self.assertIn('index("PENTARELEASE_COMPREHENSIVE_RELEASE.md")', self.reconciler_text)
        self.assertIn('index("PENTARELEASE_EVIDENCE.json")', self.reconciler_text)
        self.assertIn('author=$(gh api "repos/$REPO/pulls/$number"', self.reconciler_text)
        self.assertIn('github-actions[bot]', self.reconciler_text)

    def test_reconciler_requires_managed_source_convergence_before_retirement(self):
        self.assertIn(".pentarelease/state/release-surface.json?ref=main", self.reconciler_text)
        self.assertIn("pentarelease/latest.mdx?ref=main", self.reconciler_text)
        self.assertIn("source_covers_tag", self.reconciler_text)
        self.assertIn("source projection not converged", self.reconciler_text)
        self.assertIn("provider publication/assets alone never authorize PR-shell retirement", self.reconciler_text)
        source_guard = self.reconciler_text.index('if [ -z "$SOURCE_TAG" ] || ! source_covers_tag "$SOURCE_TAG" "$tag"; then')
        close_call = self.reconciler_text.index('gh pr close "$number" --repo "$REPO" --comment "$NOTE"')
        self.assertLess(source_guard, close_call)

    def test_reconciler_accepts_only_forward_source_coverage(self):
        self.assertIn("source >= candidate", self.reconciler_text)
        self.assertIn("same release or a newer forward-only projection", self.reconciler_text)
        self.assertNotIn("provider evidence is authoritative for cleanup", self.reconciler_text)

    def test_source_surface_squash_merge_cannot_create_recursive_release(self):
        self.assertIn('"PentaRelease comprehensive surface "', self.decision_text)
        self.assertIn('"PentaRelease surface "', self.decision_text)
        self.assertIn("GENERATED_SURFACE_MERGE_PREFIXES", self.decision_text)
        self.assertIn("generated_release_commit_guard", self.decision_text)
        combined_guard = self.decision_text.index("generated_prefixes =")
        decision_diff = self.decision_text.index('files = [x for x in sh("git", "diff"')
        self.assertLess(combined_guard, decision_diff)

    def test_secret_gate_allows_public_templates_but_still_blocks_real_env_files(self):
        self.assertIn(r"\.env\.(example|sample|template)$", self.awareness_text)
        self.assertIn(r"\.env($|\.)", self.awareness_text)
        self.assertIn("prohibited secret-bearing path", self.awareness_text)


if __name__ == "__main__":
    unittest.main()
