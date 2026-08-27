import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts/validate_dail_evidence_spine_v2.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("dail_evidence_spine_validator", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DailEvidenceSpineContractTests(unittest.TestCase):
    def test_contract_and_manifest_are_complete(self):
        load_validator().validate()

    def test_all_layers_and_pallets_have_material_event_routes(self):
        data = json.loads(
            (ROOT / "developers/manifests/dail-evidence-spine.v2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(data["pentafabric_layer_bindings"]), 5)
        self.assertEqual(len(data["capability_pallet_bindings"]), 12)
        self.assertEqual(len(data["os_surface_bindings"]), 13)
        self.assertTrue(
            all(binding["event_families"] for binding in data["capability_pallet_bindings"])
        )

    def test_factory_digest_excludes_occurrence_timestamps(self):
        data = json.loads(
            (ROOT / "developers/manifests/dail-factory-continuation.v2.json").read_text(
                encoding="utf-8"
            )
        )
        excluded = set(data["determinism"]["content_digest_excludes"])
        self.assertTrue(
            {"started_at", "completed_at", "lease_acquired_at", "lease_until"} <= excluded
        )
        self.assertIs(data["determinism"]["random_uuid_in_content_digest"], False)

    def test_external_anchor_stays_unpromoted_without_readback(self):
        data = json.loads(
            (ROOT / "developers/manifests/dail-evidence-spine.v2.json").read_text(
                encoding="utf-8"
            )
        )
        anchor = next(
            binding
            for binding in data["runtime_bindings"]
            if binding["binding_id"] == "ct.dail.independent-anchor.v1"
        )
        self.assertEqual(
            anchor["state"],
            "SCHEMA_IMPLEMENTED_ADAPTER_NOT_BUILT_NO_PRODUCTION_CLAIM",
        )

    def test_component_registry_does_not_overstate_runtime_promotion(self):
        registry = json.loads(
            (ROOT / "docs/versioning/VERSION_REGISTRY.json").read_text(encoding="utf-8")
        )
        component = next(
            item for item in registry["components"] if item["component_id"] == "ct.dail.evidence-spine"
        )
        self.assertEqual(component["version"], "2.0.0")
        self.assertEqual(component["lifecycle_state"], "controlled_test")
        self.assertEqual(component["native_substrate_state"], "deferred_target_architecture")
        self.assertEqual(
            component["external_anchor_state"],
            "schema_implemented_adapter_not_built",
        )


if __name__ == "__main__":
    unittest.main()
