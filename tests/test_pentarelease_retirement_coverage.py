"""Execute the workflow's exact-source guard with read-only provider fixtures."""
import copy
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/pentarelease-pr-backlog-reconciler.yml'


def entry(path, sha='blob', mode='100644'):
    return {'path': path, 'sha': sha, 'mode': mode, 'type': 'blob'}


class RetirementCoverageTests(unittest.TestCase):
    def setUp(self):
        text = WORKFLOW.read_text()
        code = text.split("<<'PY_COVERAGE'\n", 1)[1].split('          PY_COVERAGE', 1)[0]
        self.namespace = {'__name__': 'coverage_test'}
        exec('\n'.join(line[10:] for line in code.splitlines()), self.namespace)
        self.repo = 'crownthrive1/CrownThrive-OS'
        self.pr = {'state': 'open', 'user': {'login': 'github-actions[bot]'},
                   'head': {'sha': 'head', 'repo': {'full_name': self.repo}},
                   'base': {'sha': 'base', 'ref': 'main', 'repo': {'full_name': self.repo}},
                   'changed_files': 1}
        self.final_pr = copy.deepcopy(self.pr)
        self.files = [{'filename': 'pentarelease/latest.mdx', 'status': 'modified'}]
        self.main = {'truncated': False, 'tree': [entry(self.files[0]['filename'])]}
        self.head = copy.deepcopy(self.main)
        self.main_reads = 0
        self.pr_reads = 0
        self.final_main_sha = 'main'
        self.calls = []

    def api(self, repo, path):
        self.assertEqual(repo, self.repo)
        self.calls.append(path)
        if path == 'pulls/5358':
            self.pr_reads += 1
            return self.pr if self.pr_reads == 1 else self.final_pr
        if path == 'commits/main':
            self.main_reads += 1
            return {'sha': 'main' if self.main_reads == 1 else self.final_main_sha}
        if path.startswith('pulls/5358/files?'):
            page = int(path.rsplit('=', 1)[1])
            return self.files[(page - 1) * 100:page * 100]
        return {'git/trees/main?recursive=1': self.main,
                'git/trees/head?recursive=1': self.head}[path]

    def run_guard(self):
        self.namespace['api'] = self.api
        self.namespace['represented_on_main'](self.repo, 5358)

    def test_exact_content_passes_and_pr_is_last_read(self):
        self.run_guard()
        self.assertEqual(self.calls[-1], 'pulls/5358')

    def test_real_5358_unique_workflow_and_test_are_preserved(self):
        paths = ['.github/release-requests/crownthrive-os-3.95.3.0.json',
                 '.github/workflows/crownthrive-os-v2-release.yml',
                 'releases/3.95.3.0/MANIFEST.json',
                 'releases/3.95.3.0/RELEASE_NOTES.md',
                 'tests/test_pentarelease_source_checkout.py']
        self.files = [{'filename': p, 'status': 'modified'} for p in paths]
        self.pr['changed_files'] = self.final_pr['changed_files'] = len(paths)
        self.head['tree'] = [entry(p, 'candidate') for p in paths]
        self.main['tree'] = [entry(p, 'candidate') for p in paths if p != paths[4]]
        self.main['tree'][1]['sha'] = 'unrepaired'
        with self.assertRaisesRegex(ValueError, 'crownthrive-os-v2-release.yml'):
            self.run_guard()
        self.main['tree'][1]['sha'] = 'candidate'
        with self.assertRaisesRegex(ValueError, 'source_checkout.py'):
            self.run_guard()

    def test_human_edit_in_generated_path_is_preserved(self):
        self.head['tree'][0]['sha'] = 'human-followup'
        with self.assertRaises(ValueError):
            self.run_guard()

    def test_newer_but_different_generated_content_is_conservatively_held(self):
        self.main['tree'][0]['sha'] = 'newer-release'
        with self.assertRaises(ValueError):
            self.run_guard()

    def test_mode_change_is_preserved(self):
        self.head['tree'][0]['mode'] = '100755'
        with self.assertRaises(ValueError):
            self.run_guard()

    def test_paginated_files_include_late_unique_change(self):
        self.files = [{'filename': f'file-{i}', 'status': 'added'} for i in range(101)]
        self.pr['changed_files'] = self.final_pr['changed_files'] = 101
        self.main['tree'] = [entry(f['filename']) for f in self.files]
        self.head = copy.deepcopy(self.main)
        self.head['tree'][-1]['sha'] = 'unique'
        with self.assertRaisesRegex(ValueError, 'file-100'):
            self.run_guard()
        self.assertIn('pulls/5358/files?per_page=100&page=2', self.calls)

    def test_removed_file_requires_absence_in_both_complete_trees(self):
        self.files[0]['status'] = 'removed'
        self.head['tree'] = []
        with self.assertRaises(ValueError):
            self.run_guard()
        self.main['tree'] = []
        self.run_guard()

    def test_rename_requires_old_path_absent(self):
        self.files[0].update(status='renamed', previous_filename='old-name')
        self.main['tree'].append(entry('old-name'))
        with self.assertRaises(ValueError):
            self.run_guard()
        self.main['tree'].pop()
        self.run_guard()

    def test_truncated_tree_holds(self):
        for tree in (self.main, self.head):
            tree['truncated'] = True
            with self.assertRaises(ValueError):
                self.run_guard()
            tree['truncated'] = False

    def test_incomplete_files_hold(self):
        self.pr['changed_files'] = self.final_pr['changed_files'] = 2
        with self.assertRaises(ValueError):
            self.run_guard()

    def test_duplicate_files_hold(self):
        self.files *= 2
        self.pr['changed_files'] = self.final_pr['changed_files'] = 2
        with self.assertRaises(ValueError):
            self.run_guard()

    def test_api_failure_does_not_prove_absence(self):
        self.namespace['api'] = Mock(side_effect=RuntimeError('403'))
        with self.assertRaises(RuntimeError):
            self.namespace['represented_on_main'](self.repo, 5358)

    def test_provider_file_limit_holds(self):
        self.pr['changed_files'] = 3001
        with self.assertRaises(ValueError):
            self.run_guard()

    def test_pr_head_base_or_count_change_holds(self):
        for field in ('head', 'base', 'changed_files'):
            self.pr_reads = self.main_reads = 0
            self.final_pr = copy.deepcopy(self.pr)
            if field == 'changed_files':
                self.final_pr[field] = 2
            else:
                self.final_pr[field]['sha'] = 'moved'
            with self.assertRaisesRegex(ValueError, 'PR changed'):
                self.run_guard()

    def test_main_moving_holds(self):
        self.final_main_sha = 'moved'
        with self.assertRaises(ValueError):
            self.run_guard()

    def test_non_main_or_fork_holds(self):
        self.pr['base']['ref'] = 'other'
        with self.assertRaises(ValueError):
            self.run_guard()
        self.pr['base']['ref'] = 'main'
        self.pr['head']['repo']['full_name'] = 'other/repo'
        self.pr_reads = 0
        with self.assertRaises(ValueError):
            self.run_guard()

    def test_guard_runs_before_close_without_added_permissions(self):
        text = WORKFLOW.read_text()
        guard = text.index('if ! exact_source_coverage "$number"; then')
        close = text.index('gh pr close "$number"')
        self.assertLess(guard, close)
        self.assertIn('contents: read', text)
        self.assertNotIn('--delete-branch', text)


if __name__ == '__main__':
    unittest.main()
