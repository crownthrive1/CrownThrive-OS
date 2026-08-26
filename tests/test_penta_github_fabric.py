import copy
import json
from pathlib import Path
import unittest

from penta.github_fabric.fabric import FabricError, digest, execute_request, validate_contract


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "penta/github_fabric/contract.v1.json").read_text())
REQUEST = json.loads((ROOT / "penta/github_fabric/request.example.json").read_text())


class GitHubFabricTests(unittest.TestCase):
    def test_contract_and_execution_are_production_eligible(self):
        validate_contract(CONTRACT)
        result = execute_request(CONTRACT, REQUEST, observed_at="2026-08-26T00:00:00+00:00")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.receipt["status"], "passed")
        self.assertEqual(result.receipt["runner_id"], "ct.runner.github-hosted.ubuntu.v1")
        sealed = dict(result.receipt)
        receipt_hash = sealed.pop("result_sha256")
        self.assertEqual(receipt_hash, digest(sealed))

    def test_unknown_action_fails_closed(self):
        request = {**REQUEST, "action_id": "ct.action.unregistered"}
        with self.assertRaises(FabricError):
            execute_request(CONTRACT, request)

    def test_self_hosted_production_request_fails_closed(self):
        request = {**REQUEST, "required_labels": ["self-hosted", "pentafabric"]}
        with self.assertRaises(FabricError):
            execute_request(CONTRACT, request)

    def test_shell_action_is_rejected(self):
        contract = copy.deepcopy(CONTRACT)
        contract["actions"][0]["shell"] = True
        with self.assertRaises(FabricError):
            validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
