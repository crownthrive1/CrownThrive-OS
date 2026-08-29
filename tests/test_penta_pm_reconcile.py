import importlib.util
import json
import pathlib
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("penta_pm_reconcile", ROOT / "scripts" / "penta_pm_reconcile.py")
pm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pm)
POLICY = json.loads((ROOT / "config" / "penta_pm_policy.json").read_text())


class PentaPMTests(unittest.TestCase):
    def test_docs_lane_routes_to_docs_milestone(self):
        c = pm.classify([
            {"name": "penta:authority:pr"},
            {"name": "penta:lane:docs"},
            {"name": "penta:risk:d2"},
            {"name": "penta:stage:nurture"},
        ], POLICY)
        self.assertEqual(c["milestone"], "Documentation & Institutional Knowledge")
        self.assertEqual(c["owner"], "pr")
        self.assertEqual(c["risk"], "d2")
        self.assertEqual(c["stage"], "nurture")

    def test_unknown_lane_falls_back_to_os_convergence(self):
        c = pm.classify([{"name": "penta:lane:unknown"}], POLICY)
        self.assertEqual(c["milestone"], "OS Production Convergence")

    def test_development_link_recognizes_closes_and_refs(self):
        self.assertIsNotNone(pm.LINK_RE.search("Closes #585\nRefs #584"))
        self.assertIsNotNone(pm.LINK_RE.search("refs #584"))

    def test_plain_issue_number_is_not_development_link(self):
        self.assertIsNone(pm.LINK_RE.search("See issue #584 for context"))

    def test_receipt_is_deterministically_hashed(self):
        r = pm.receipt("crownthrive1/CrownThrive-OS", "check", [], [])
        self.assertEqual(len(r["receipt_sha256"]), 64)
        self.assertEqual(r["schema"], "ct.penta.pm.receipt.v1")

    def test_policy_has_required_project_fields(self):
        required = {"Artifact ID", "Penta Owner", "Lane", "Stage", "Risk", "Milestone", "DAIL Receipt", "CHLOM Decision"}
        self.assertTrue(required.issubset(set(POLICY["project_fields"])))

    def test_policy_has_eight_initial_milestones(self):
        self.assertEqual(len(POLICY["milestones"]), 8)

    def test_user_owned_projects_prefer_explicit_rest_surface(self):
        identity = {
            "viewer": {"id": "U_1", "login": "crownthrive1"},
            "repository": {
                "owner": {"__typename": "User", "id": "U_1", "login": "crownthrive1"}
            },
        }
        projects = [{"node_id": "PVT_1", "title": "CrownThrive Roadmap", "number": 7}]
        with mock.patch.object(pm, "graphql", return_value=identity) as gql, \
             mock.patch.object(pm, "request", return_value=projects) as req:
            ctx = pm.owner_project_context("token", "crownthrive1", "CrownThrive-OS")
        self.assertEqual(ctx["access_path"], "user.projectsV2.rest")
        self.assertEqual(ctx["project_host"]["projectsV2"]["nodes"][0]["id"], "PVT_1")
        self.assertIn("/users/crownthrive1/projectsV2", req.call_args.args[1])
        self.assertEqual(gql.call_count, 1)

    def test_user_owned_projects_fall_back_to_explicit_user_graphql(self):
        identity = {
            "viewer": {"id": "U_1", "login": "crownthrive1"},
            "repository": {
                "owner": {"__typename": "User", "id": "U_1", "login": "crownthrive1"}
            },
        }
        user_host = {
            "user": {
                "id": "U_1",
                "login": "crownthrive1",
                "projectsV2": {"nodes": [{"id": "PVT_2", "title": "CrownThrive Roadmap", "number": 8}]},
            }
        }

        def fake_graphql(token, query, variables=None):
            if "repository(owner:$owner" in query:
                return identity
            if "user(login:$login)" in query:
                return user_host
            raise AssertionError(query)

        with mock.patch.object(pm, "graphql", side_effect=fake_graphql), \
             mock.patch.object(pm, "request", side_effect=RuntimeError("REST 403")):
            ctx = pm.owner_project_context("token", "crownthrive1", "CrownThrive-OS")
        self.assertEqual(ctx["access_path"], "user.projectsV2.graphql")
        self.assertEqual(ctx["project_host"]["projectsV2"]["nodes"][0]["id"], "PVT_2")

    def test_dual_user_project_rejection_is_compatibility_not_missing_permission_claim(self):
        identity = {
            "viewer": {"id": "U_1", "login": "crownthrive1"},
            "repository": {
                "owner": {"__typename": "User", "id": "U_1", "login": "crownthrive1"}
            },
        }

        def fake_graphql(token, query, variables=None):
            if "repository(owner:$owner" in query:
                return identity
            raise RuntimeError("GraphQL FORBIDDEN")

        with mock.patch.object(pm, "graphql", side_effect=fake_graphql), \
             mock.patch.object(pm, "request", side_effect=RuntimeError("REST 403")):
            with self.assertRaises(pm.ProjectsCompatibilityError) as caught:
                pm.owner_project_context("token", "crownthrive1", "CrownThrive-OS")
        self.assertEqual(
            caught.exception.reason_code,
            "user_owned_projects_token_or_transport_compatibility",
        )
        self.assertIn("does not by itself prove", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
