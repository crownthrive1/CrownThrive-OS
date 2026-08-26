import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "runtime" / "penta_context.py"
SPEC = importlib.util.spec_from_file_location("penta_context", MODULE_PATH)
assert SPEC and SPEC.loader
penta_context = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = penta_context
SPEC.loader.exec_module(penta_context)


class CaptureClient(penta_context.PentaContextClient):
    def __init__(self):
        self.payloads = []

    def _post(self, payload):
        self.payloads.append(payload)
        return {"ok": True, "payload": payload, "authority_created": False}


class PentaContextRuntimeTests(unittest.TestCase):
    def test_scope_normalization(self):
        self.assertEqual(penta_context.normalize_scope("  Penta.Build  "), "penta.build")
        with self.assertRaises(ValueError):
            penta_context.normalize_scope("x")

    def test_tag_normalization_is_stable(self):
        self.assertEqual(
            penta_context.normalize_tags(["Context", "context", " BUILD ", ""]),
            ["build", "context"],
        )

    def test_local_redaction(self):
        sample = (
            "person@example.test 123-45-6789 "
            "Bearer ABCDEFGHIJKLMNOPQRST api_key=ABCDEFGHIJKLMNOPQRST"
        )
        redacted = penta_context.redact_local(sample)
        self.assertNotIn("person@example.test", redacted)
        self.assertNotIn("123-45-6789", redacted)
        self.assertNotIn("ABCDEFGHIJKLMNOPQRST", redacted)
        self.assertIn("[redacted-email]", redacted)
        self.assertIn("[redacted-ssn]", redacted)
        self.assertIn("[redacted-secret]", redacted)

    def test_query_payload_is_bounded(self):
        client = CaptureClient()
        result = client.query(
            "Penta.Context.Canary",
            "context routing",
            limit=8,
            max_chars=4000,
            tags=["Context"],
            classification_ceiling="internal",
        )
        payload = result["payload"]
        self.assertEqual(payload["scope_key"], "penta.context.canary")
        self.assertEqual(payload["tags"], ["context"])
        self.assertEqual(payload["classification_ceiling"], "internal")
        self.assertFalse(result["authority_created"])

    def test_query_rejects_invalid_classification(self):
        client = CaptureClient()
        with self.assertRaises(ValueError):
            client.query("penta.context", classification_ceiling="super-secret")

    def test_ingest_validates_source_and_redacts_before_transport(self):
        client = CaptureClient()
        result = client.ingest(
            "Penta.Context",
            "SYSTEM",
            "unit-test",
            "Contact test@example.test api_key=ABCDEFGHIJKLMNOPQRST",
            tags=["Test", "test"],
        )
        payload = result["payload"]
        self.assertEqual(payload["source_type"], "system")
        self.assertEqual(payload["tags"], ["test"])
        self.assertNotIn("test@example.test", payload["content"])
        self.assertNotIn("ABCDEFGHIJKLMNOPQRST", payload["content"])

    def test_ingest_rejects_unknown_source(self):
        client = CaptureClient()
        with self.assertRaises(ValueError):
            client.ingest("penta.context", "unknown-provider", "x", "content")

    def test_character_budget_contract(self):
        client = CaptureClient()
        with self.assertRaises(ValueError):
            client.query("penta.context", max_chars=511)
        with self.assertRaises(ValueError):
            client.query("penta.context", max_chars=100001)


if __name__ == "__main__":
    unittest.main()
