import importlib.util
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CENSUS = ROOT / ".crownthrive" / "resources" / "github-provider-repository-census.v1.json"
SET = ROOT / ".crownthrive" / "resources" / "repository-resource-set.v1.json"
EXTENSION = ROOT / ".crownthrive" / "resources" / "repository-resources.extension.20260901.json"
SCRIPT = ROOT / "scripts" / "repository_resource_registry.py"

spec = importlib.util.spec_from_file_location("repository_resource_registry", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FullRepositoryEstateCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.census = json.loads(CENSUS.read_text(encoding="utf-8"))
        cls.registry_set = json.loads(SET.read_text(encoding="utf-8"))
        cls.extension = json.loads(EXTENSION.read_text(encoding="utf-8"))
        cls.materialized = module.compose(SET)
        cls.by_repo = {item["repository"]: item for item in cls.materialized["resources"]}

    def test_provider_census_is_complete_and_disjoint(self):
        accessible = self.census["accessible_repository_count"]
        nonempty_count = self.census["nonempty_repository_count"]
        empty_count = self.census["empty_placeholder_count"]
        self.assertEqual(accessible, nonempty_count + empty_count)
        self.assertEqual(len(self.census["nonempty_repositories"]), nonempty_count)
        self.assertEqual(len(self.census["empty_placeholders"]), empty_count)
        self.assertFalse(set(self.census["nonempty_repositories"]) & set(self.census["empty_placeholders"]))

    def test_composed_registry_accounts_for_every_nonempty_repository(self):
        self.assertEqual(
            self.materialized["governed_resource_count"],
            self.registry_set["composed_governed_resource_count"],
        )
        self.assertEqual(
            self.materialized["governed_resource_count"],
            self.census["governed_resource_registry_count_target"],
        )
        nonempty = {f"crownthrive1/{name}" for name in self.census["nonempty_repositories"]}
        governed = set(self.by_repo)
        self.assertTrue(nonempty <= governed)
        self.assertEqual(governed - nonempty, {"crownthrive1/private-chlom"})

    def test_new_source_extension_is_exact_and_non_authorizing(self):
        self.assertEqual(self.extension["resource_count"], 6)
        expected = {
            "crownthrive1/PentaContext",
            "crownthrive1/PentaCensus",
            "crownthrive1/PentaSELF",
            "crownthrive1/PentaDiscovery",
            "crownthrive1/PentaWire",
            "crownthrive1/PentaTreasury",
        }
        self.assertEqual({item["repository"] for item in self.extension["resources"]}, expected)
        for item in self.extension["resources"]:
            self.assertTrue(item["requires_exact_head_before_execution"])
            self.assertFalse(item["may_grant_provider_or_d3_authority"])
            self.assertEqual(item["authority"], "supporting_source")

    def test_merged_source_heads_are_bound_exactly(self):
        self.assertEqual(self.by_repo["crownthrive1/PentaContext"]["exact_head"], "4da803902ba2f077780461adf60e0ade1cf7b08e")
        self.assertEqual(self.by_repo["crownthrive1/PentaCensus"]["exact_head"], "2a411783e1f2335f6eaeb0384ca19acefe1510b6")
        self.assertEqual(self.by_repo["crownthrive1/PentaDiscovery"]["exact_head"], "e7de79507b282c6193c95b9d23c60f9e16061acb")
        self.assertEqual(self.by_repo["crownthrive1/PentaWire"]["exact_head"], "1c692488dc24cbb7ddbe6964c6f8a2cd5a95a804")
        self.assertEqual(self.by_repo["crownthrive1/PentaTreasury"]["exact_head"], "8d18582525fed5c9f65696cbd81af9628f4e2428")
        for repository in (
            "crownthrive1/PentaContext",
            "crownthrive1/PentaCensus",
            "crownthrive1/PentaDiscovery",
            "crownthrive1/PentaWire",
            "crownthrive1/PentaTreasury",
        ):
            self.assertEqual(self.by_repo[repository]["source_contract_ci"], "PASS")

    def test_pentaself_terminalized_source_custody_is_bound_without_authority(self):
        item = self.by_repo["crownthrive1/PentaSELF"]
        self.assertEqual(item["exact_head"], "f13f1d8bc5bcf54f63f6ea34a9e66f9ce0162142")
        self.assertEqual(item["governance_candidate_head"], "de090e92fabe61ce9dc0823e02320c5aef3ae031")
        self.assertEqual(item["source_contract_ci"], "PASS")
        self.assertEqual(item["merge_state"], "MERGED_READBACK")
        self.assertEqual(item["state"], "ACTIVE")
        self.assertFalse(item["runtime_authority_moved"])
        self.assertFalse(any(hold.get("repository") == "crownthrive1/PentaSELF" for hold in self.registry_set["holds"]))

    def test_empty_placeholders_are_inventory_only(self):
        self.assertFalse(self.census["authority"]["empty_placeholder_grants_authority"])
        self.assertFalse(self.census["classification_semantics"]["empty_placeholder"].startswith("Production"))
        for name in self.census["empty_placeholders"]:
            if name != "private-chlom":
                self.assertNotIn(f"crownthrive1/{name}", self.by_repo)

    def test_registry_set_preserves_no_reset_semantics(self):
        rules = self.registry_set["composition_rules"]
        self.assertTrue(rules["static_exact_head_is_observation_only"])
        self.assertTrue(rules["resolve_live_default_branch_before_execution"])
        self.assertTrue(rules["missing_or_rate_limited_readback_is_hold"])
        self.assertFalse(self.registry_set["authority"]["registry_set_grants_runtime_authority"])
        self.assertFalse(self.registry_set["authority"]["provider_write"])
        self.assertFalse(self.registry_set["authority"]["money_movement"])
        self.assertFalse(self.registry_set["authority"]["d3_authority"])


if __name__ == "__main__":
    unittest.main()
