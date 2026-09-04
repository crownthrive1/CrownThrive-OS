import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / ".crownthrive" / "resources" / "repository-resources.v1.json"
POLICY = ROOT / ".crownthrive" / "resources" / "repository-head-resolution.v1.json"


class RepositoryResourceHeadResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.by_repo = {item["repository"]: item for item in cls.registry["resources"]}

    def test_registry_is_complete_and_unique(self):
        self.assertEqual(self.registry["contract"], "ct.repository-resource-registry.v1")
        self.assertEqual(self.registry["version"], "1.1.0")
        self.assertEqual(self.registry["repository_count"], 32)
        self.assertEqual(len(self.registry["resources"]), 32)
        self.assertEqual(len(self.by_repo), 32)

    def test_static_heads_are_observations_not_reset_authority(self):
        self.assertIn("observed snapshot", self.registry["exact_head_semantics"])
        self.assertTrue(self.policy["rules"]["exact_head_is_observation"])
        self.assertTrue(self.policy["rules"]["resolve_default_branch_before_execution"])
        self.assertTrue(self.policy["rules"]["force_reset_to_snapshot_forbidden"])
        self.assertTrue(self.policy["rules"]["missing_or_rate_limited_readback_is_hold"])

    def test_registry_owner_self_reference_is_dynamic(self):
        owner = self.by_repo["crownthrive1/CrownThrive-OS"]
        self.assertEqual(owner["head_resolution"], "DYNAMIC_DEFAULT_BRANCH_HEAD")
        self.assertEqual(owner["static_exact_head_semantics"], "observed_snapshot_only")
        self.assertEqual(self.registry["self_reference_policy"]["mode"], "DYNAMIC_DEFAULT_BRANCH_HEAD")
        self.assertTrue(self.registry["self_reference_policy"]["static_exact_head_is_observation_only"])

    def test_merge_burst_history_is_preserved_without_freezing_current_heads(self):
        incident = {
            item["repository"]: item
            for item in self.policy["merge_burst_head_reconciliation"]
        }
        expected_history = {
            "crownthrive1/PRIVATE-PentaOS": (
                "1d21fa1127bbfb8d1bd44f0233be9ace00fc9f66",
                "eda12cf5b2585146f2a8e982fb6a754c9c3bd13a",
                "linear_merge_stack_preserved",
            ),
            "crownthrive1/PRIVATE-PentaInteroperation": (
                "2f1a09332792f204c945d75ad4f4472dccf134fe",
                "000629a25b851f4e6facd6ccb213a93817813975",
                "production_cutover_merge_preserved",
            ),
            "crownthrive1/PentaAds-Placement-OS": (
                "e80c78582ce9c41a458f190cdb2d8b99cdb6d950",
                "e80c78582ce9c41a458f190cdb2d8b99cdb6d950",
                "already_current",
            ),
        }
        for repository, (snapshot, readback, resolution) in expected_history.items():
            self.assertIn(repository, incident)
            self.assertEqual(incident[repository]["registry_snapshot_head"], snapshot)
            self.assertEqual(incident[repository]["incident_readback_head"], readback)
            self.assertEqual(incident[repository]["resolution"], resolution)

            current = self.by_repo[repository]["exact_head"]
            self.assertIsInstance(current, str)
            self.assertEqual(len(current), 40)
            int(current, 16)

    def test_reference_forks_remain_non_authoritative(self):
        reference = [item for item in self.registry["resources"] if item["resource_class"] == "REFERENCE_FORK"]
        self.assertTrue(reference)
        for item in reference:
            self.assertEqual(item["authority"], "reference_only")
            self.assertFalse(item["may_grant_provider_or_d3_authority"])
            self.assertIn(item["sync_policy"], {"PURE_REFERENCE_FAST_FORWARD"})

    def test_all_executable_resources_require_live_head_readback(self):
        for item in self.registry["resources"]:
            self.assertTrue(item["requires_exact_head_before_execution"], item["repository"])


if __name__ == "__main__":
    unittest.main()
