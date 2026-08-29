import unittest

from scripts.pentarelease import enrich_release_intelligence as eri


class PentaReleaseReleaseIntelligenceTests(unittest.TestCase):
    def test_runtime_evidence_preserves_cost_distinctions_and_cie_dimensions(self):
        record = {
            "tag": "v3.46.1.0",
            "title": "CrownThrive OS 3.46.1.0 — Autonomous PentaRelease",
            "publisher": "PentaRelease",
            "official_release_url": "https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v3.46.1.0",
            "why": "production fix/hardening delta",
            "what_changed": ["runtime/a.py"],
            "penta_components": ["PentaRelease"],
            "ecosystem_lanes": ["runtime"],
            "provenance": {"repository": "crownthrive1/CrownThrive-OS", "release_target": "abc123"},
        }
        runtime = {
            "ok": True,
            "result": {
                "projected": {
                    "footer": {
                        "penta_costs": {
                            "provider_actual_usd": 0,
                            "provider_estimated_usd": 0,
                            "internal_reserved_units": 0,
                            "internal_accounted_units": 0,
                        },
                        "penta_pay": {"gross_usd": 0, "settled_usd": 0},
                        "usd_summary": {"recognized_release_exposure_usd": 0},
                        "cie": {
                            "status": "PASS",
                            "score": 100,
                            "source": "public.ct_cie_score / ct.framework-package.cie",
                            "evidence_hash": "ciehash",
                            "evidence": {
                                "algorithm_id": "ct.algorithm.cie.v1",
                                "algorithm_version": "1.0.1",
                                "human_review_required": False,
                                "dimension_scores": {
                                    "identity_fit": 20,
                                    "community_value": 20,
                                    "story_alignment": 20,
                                    "brand_safety": 20,
                                    "legacy_impact": 20,
                                },
                            },
                        },
                        "evidence_sha256": "releasehash",
                    }
                },
                "evaluation": {
                    "cost": {
                        "direct_usd_cost": None,
                        "cost_status": "not_available",
                        "reason": "no certified release-specific provider usage bindings",
                    }
                },
            },
        }
        provider = {
            "author": {"login": "github-actions[bot]"},
            "target_commitish": "abc123",
            "tag_name": "v3.46.1.0",
            "created_at": "2026-08-29T07:43:13Z",
            "published_at": "2026-08-29T07:44:34Z",
            "assets": [{"name": "MANIFEST.json"}],
        }

        intel = eri.release_intelligence(record, runtime, provider)
        self.assertEqual(intel["costs"]["provider_actual_usd"], 0)
        self.assertEqual(intel["costs"]["recognized_release_exposure_usd"], 0)
        self.assertIsNone(intel["costs"]["direct_usage_calculation"]["direct_usd_cost"])
        self.assertEqual(intel["costs"]["direct_usage_calculation"]["cost_status"], "not_available")
        self.assertEqual(intel["cie"]["score"], 100)
        self.assertEqual(intel["cie"]["dimension_scores"]["legacy_impact"], 20)

        rendered = eri.render_markdown(record, intel)
        self.assertIn("Release intelligence", rendered)
        self.assertIn("Cost calculation and methodology", rendered)
        self.assertIn("missing direct-usage binding is reported as unavailable", rendered)
        self.assertIn("Cultural Imprint Engine (CIE)", rendered)
        self.assertIn("Legacy Impact", rendered)


if __name__ == "__main__":
    unittest.main()
