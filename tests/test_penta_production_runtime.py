import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


scribe_runtime = load_module("pentascribe_runtime", ROOT / "penta/scribe/runtime.py")
marketer_runtime = load_module("pentamarketer_runtime", ROOT / "penta/marketer/runtime.py")


class PentaProductionRuntimeTests(unittest.TestCase):
    def test_scribe_cycle_persists_candidate_and_receipt_without_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            scan = root / "source.md"
            scan.write_text("PentaFuture™ is a candidate only.", encoding="utf-8")
            result = scribe_runtime.cycle(
                ROOT / "penta/scribe/registry.json",
                root / "state",
                [scan],
                "test-authority",
            )
            self.assertEqual("HOLD_CANDIDATES", result["summary"]["status"])
            discovery = json.loads((pathlib.Path(result["run_dir"]) / "discovery.json").read_text())
            self.assertEqual(1, discovery["candidate_count"])
            self.assertEqual(["™"], discovery["candidates"][0]["symbols"])
            self.assertEqual("NO_AUTOMATIC_PROMOTION", result["summary"]["promotion_state"])
            self.assertEqual(64, len(result["receipt"]["receipt_sha256"]))

    def test_marketer_cycle_routes_artifacts_and_holds_unbound_channels(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            result = marketer_runtime.cycle(
                ROOT / "penta/marketer/campaign.example.json",
                root,
                ROOT / "penta/marketer/adapters.registry.json",
                ROOT / "penta/scribe/registry.json",
                ROOT / "penta/marketer/policy.json",
            )
            self.assertEqual("PARTIAL_HOLD", result["summary"]["status"])
            by_channel = {r["channel"]: r for r in result["summary"]["results"]}
            self.assertEqual("ARTIFACT_READY", by_channel["owned_web"]["status"])
            self.assertEqual("HOLD", by_channel["email"]["status"])
            self.assertEqual("HOLD", by_channel["social"]["status"])
            payload = json.loads(pathlib.Path(by_channel["owned_web"]["path"]).read_text())
            self.assertFalse(payload["provider_write_authority"])
            self.assertEqual("ARTIFACT_READY_NOT_PUBLISHED", payload["publication_state"])


if __name__ == "__main__":
    unittest.main()
