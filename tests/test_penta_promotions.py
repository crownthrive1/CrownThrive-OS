"""Contract tests for exact-evidence-bound Penta maturity promotions."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.penta_promotions import (  # noqa: E402
    PentaPromotionError,
    apply_promotions,
    load_promotion_manifest,
)


class PentaPromotionTests(unittest.TestCase):
    def test_live_registry_is_exact_evidence_bound_and_provider_neutral(self) -> None:
        manifest = load_promotion_manifest(ROOT, required=True)
        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(len(manifest["promotions"]), 5)
        self.assertEqual(
            {item["machine_key"] for item in manifest["promotions"]},
            {"penta.mail", "penta.status", "penta.credentials", "penta.build", "penta.certify"},
        )
        for item in manifest["promotions"]:
            self.assertEqual(item["provider_state_disposition"], "UNCHANGED_SEPARATELY_GATED")
            self.assertFalse(item["provider_effect_authorized"])
            self.assertFalse(item["self_certification_authorized"])
            self.assertTrue(item["evidence_bindings"])

    def test_apply_promotions_preserves_catalog_lineage_without_mutating_input(self) -> None:
        members = {
            item["machine_key"]: {"canonical_name": item["machine_key"], "maturity": item["from_maturity"]}
            for item in load_promotion_manifest(ROOT, required=True)["promotions"]  # type: ignore[index]
        }
        promoted, applied = apply_promotions(ROOT, members, required=True)
        self.assertEqual(len(applied), 5)
        for machine_key in applied:
            self.assertEqual(members[machine_key]["maturity"], "specified")
            self.assertEqual(promoted[machine_key]["catalog_maturity"], "specified")
            self.assertEqual(promoted[machine_key]["maturity"], "production")
            self.assertFalse(promoted[machine_key]["maturity_promotion"]["provider_effect_authorized"])

    @staticmethod
    def _fixture(root: Path, *, provider_effect_authorized: bool = False, digest: str | None = None) -> dict:
        evidence = root / "evidence.json"
        runtime = root / "runtime.py"
        evidence.write_text('{"status":"PASS"}\n', encoding="utf-8")
        runtime.write_text("# bounded runtime\n", encoding="utf-8")
        actual = sha256(evidence.read_bytes()).hexdigest()
        manifest = {
            "schema": "ct.penta.production-promotions.v1",
            "version": "1.1.0",
            "fail_closed": True,
            "self_promotion_prohibited": True,
            "provider_state_policy": "never_promoted_by_this_registry",
            "authority_invariant": "test",
            "promotions": [{
                "promotion_id": "promo-penta.test-20260827",
                "machine_key": "penta.test",
                "from_maturity": "specified",
                "to_maturity": "production",
                "effective_at": "2026-08-27T00:00:00Z",
                "authority_ref": "test:external-review",
                "evidence_status": "PASS",
                "evidence_bindings": [{"path": "evidence.json", "sha256": digest or actual, "claim": "test evidence"}],
                "runtime_refs": ["runtime.py"],
                "proof": ["bounded_test"],
                "scope": "test-only system maturity",
                "provider_state_disposition": "UNCHANGED_SEPARATELY_GATED",
                "provider_effect_authorized": provider_effect_authorized,
                "self_certification_authorized": False,
            }],
        }
        target = root / "data/penta"
        target.mkdir(parents=True)
        (target / "production-promotions.v1.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def test_evidence_digest_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root, digest="0" * 64)
            with self.assertRaisesRegex(PentaPromotionError, "digest mismatch"):
                load_promotion_manifest(root, required=True)

    def test_provider_effect_promotion_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root, provider_effect_authorized=True)
            with self.assertRaisesRegex(PentaPromotionError, "may not authorize provider effects"):
                load_promotion_manifest(root, required=True)

    def test_prior_maturity_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root)
            members = {"penta.test": {"canonical_name": "PentaTest", "maturity": "implemented"}}
            with self.assertRaisesRegex(PentaPromotionError, "prior maturity mismatch"):
                apply_promotions(root, members, required=True)


if __name__ == "__main__":
    unittest.main()
