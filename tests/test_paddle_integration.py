from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts/validate_paddle_integration.py"

spec = importlib.util.spec_from_file_location("validate_paddle_integration", VALIDATOR_PATH)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class PaddleIntegrationContractTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        result = validator.validate(ROOT)
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["mcp_server_count"], 3)
        self.assertEqual(result["preserved_mcp_server_count"], 3)
        self.assertEqual(result["skill_count"], 10)
        self.assertEqual(result["production_state"], "HOLD")

    def test_literal_sandbox_secret_is_rejected(self) -> None:
        self.assertIsNotNone(validator.SECRET_PATTERN.search("pdl_sdbx_1234567890ABCDEF"))
        self.assertIsNone(validator.SECRET_PATTERN.search("${PADDLE_SANDBOX_API_KEY}"))


if __name__ == "__main__":
    unittest.main()
