import copy
import unittest

from penta.runtime.overlay import (
    CompareState,
    GitHubClient,
    PentaOverlayError,
    Reconciler,
    discover_upstream_workflow,
    enforce_static_authority_invariants,
)


class FakeClient(GitHubClient):
    def __init__(self):
        super().__init__("fake")
        self.repos = {}
        self.heads = {}
        self.compares = {}
        self.workflows = {}
        self.updated = []
        self.dispatched = []

    def get_repo(self, repo):
        return {"default_branch": self.repos[repo]}

    def get_head(self, repo, branch):
        return self.heads[(repo, branch)]

    def compare(self, repo, base, head):
        return self.compares[(repo, base, head)]

    def update_ref_fast_forward(self, repo, branch, sha):
        self.updated.append((repo, branch, sha))
        self.heads[(repo, branch)] = sha

    def list_workflows(self, repo, branch):
        return self.workflows.get((repo, branch), [])

    def dispatch_workflow(self, repo, workflow, ref):
        self.dispatched.append((repo, workflow, ref))


def base_resource(**overrides):
    data = {
        "repository": "crownthrive1/example",
        "visibility": "public",
        "default_branch": "master",
        "exact_head": "a" * 40,
        "resource_class": "REFERENCE_FORK",
        "role": "example_reference",
        "authority": "reference_only",
        "state": "ACTIVE",
        "upstream_repository": "upstream/example",
        "upstream_branch": "master",
        "upstream_head": "a" * 40,
        "sync_policy": "PURE_REFERENCE_FAST_FORWARD",
        "sync_state": "IDENTICAL",
        "requires_exact_head_before_execution": True,
        "may_grant_provider_or_d3_authority": False,
    }
    data.update(overrides)
    return data


class PentaOverlayTests(unittest.TestCase):
    def test_reference_fast_forward_only_when_no_crownthrive_commits(self):
        c = FakeClient()
        c.repos = {"crownthrive1/example": "master", "upstream/example": "master"}
        c.heads = {
            ("crownthrive1/example", "master"): "a" * 40,
            ("upstream/example", "master"): "b" * 40,
        }
        c.compares = {
            ("upstream/example", "a" * 40, "b" * 40): CompareState("ahead", 4, 0)
        }
        result = Reconciler(c, apply_reference_sync=True)._reference(base_resource())
        self.assertEqual(result["event"]["action"], "FAST_FORWARDED")
        self.assertEqual(c.updated, [("crownthrive1/example", "master", "b" * 40)])
        self.assertEqual(result["resource"]["exact_head"], "b" * 40)

    def test_reference_divergence_never_mutates(self):
        c = FakeClient()
        c.repos = {"crownthrive1/example": "master", "upstream/example": "master"}
        c.heads = {
            ("crownthrive1/example", "master"): "a" * 40,
            ("upstream/example", "master"): "b" * 40,
        }
        c.compares = {
            ("upstream/example", "a" * 40, "b" * 40): CompareState("diverged", 4, 2)
        }
        result = Reconciler(c, apply_reference_sync=True)._reference(base_resource())
        self.assertEqual(result["event"]["action"], "HOLD_DIVERGENT_OR_AHEAD")
        self.assertEqual(c.updated, [])

    def test_actual_default_branch_is_preserved(self):
        c = FakeClient()
        c.repos = {"crownthrive1/example": "main", "upstream/example": "master"}
        c.heads = {
            ("crownthrive1/example", "main"): "a" * 40,
            ("upstream/example", "master"): "a" * 40,
        }
        c.compares = {
            ("upstream/example", "a" * 40, "a" * 40): CompareState("identical", 0, 0)
        }
        result = Reconciler(c)._reference(base_resource())
        self.assertEqual(result["resource"]["default_branch"], "main")
        self.assertEqual(result["resource"]["upstream_branch"], "master")

    def test_managed_overlay_dispatches_existing_workflow(self):
        resource = base_resource(
            repository="crownthrive1/overlay",
            resource_class="MANAGED_OVERLAY_FORK",
            authority="managed_overlay",
            role="overlay",
            upstream_repository="upstream/overlay",
            exact_head="c" * 40,
            upstream_head="a" * 40,
            sync_policy="CROWNTHRIVE_OVERLAY_GOVERNED_MERGE",
            sync_state="CROWNTHRIVE_AHEAD",
        )
        c = FakeClient()
        c.repos = {"crownthrive1/overlay": "main", "upstream/overlay": "main"}
        c.heads = {
            ("crownthrive1/overlay", "main"): "c" * 40,
            ("upstream/overlay", "main"): "b" * 40,
        }
        c.compares = {
            ("upstream/overlay", "c" * 40, "b" * 40): CompareState("diverged", 3, 2)
        }
        c.workflows[("crownthrive1/overlay", "main")] = [
            {"name": "upstream-auto-merge.yml", "id": 55}
        ]
        result = Reconciler(c, dispatch_managed_overlay=True)._overlay(resource)
        self.assertEqual(result["event"]["action"], "DISPATCHED_UPSTREAM_WORKFLOW")
        self.assertEqual(c.dispatched, [("crownthrive1/overlay", 55, "main")])
        self.assertEqual(result["resource"]["exact_head"], "c" * 40)

    def test_supabase_cannot_become_canonical_thrivebase(self):
        resource = base_resource(
            repository="crownthrive1/Supabase",
            role="supabase_platform_reference",
        )
        enforce_static_authority_invariants(resource)
        bad = copy.deepcopy(resource)
        bad["authority"] = "canonical_source"
        with self.assertRaises(PentaOverlayError):
            enforce_static_authority_invariants(bad)

    def test_workflow_discovery_is_specific(self):
        wf = discover_upstream_workflow([
            {"name": "ci.yml", "id": 1},
            {"name": "upstream-follow.yml", "id": 2},
        ])
        self.assertEqual(wf["id"], 2)


if __name__ == "__main__":
    unittest.main()
