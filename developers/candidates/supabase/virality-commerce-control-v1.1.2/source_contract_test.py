#!/usr/bin/env python3
"""Fail-closed source contract checks for the staged Edge Function."""

from pathlib import Path
import unittest


FUNCTION_DIR = Path(__file__).resolve().parent
INDEX_SOURCE = (FUNCTION_DIR / "index.ts").read_text(encoding="utf-8")
CONTROL_SOURCE = (FUNCTION_DIR / "control.ts").read_text(encoding="utf-8")


class SourceContractTest(unittest.TestCase):
    def test_no_whole_body_prebuffer(self) -> None:
        self.assertNotIn("request.text()", INDEX_SOURCE)
        self.assertNotIn("request.text()", CONTROL_SOURCE)
        self.assertIn("request.body.getReader()", CONTROL_SOURCE)

    def test_exact_origin_is_pinned(self) -> None:
        self.assertIn(
            'ALLOWED_ORIGIN = "https://vm.crownthrive.com"', CONTROL_SOURCE
        )
        self.assertIn('request.method === "POST"', CONTROL_SOURCE)
        self.assertIn('request.method === "OPTIONS"', CONTROL_SOURCE)
        self.assertIn('return "origin_required"', CONTROL_SOURCE)

    def test_body_limit_and_cancellation_are_source_bound(self) -> None:
        self.assertIn("MAX_BODY_BYTES = 4_096", CONTROL_SOURCE)
        self.assertIn('reader.cancel("payload_too_large")', CONTROL_SOURCE)
        self.assertIn('throw new Error("payload_too_large")', CONTROL_SOURCE)

    def test_generalized_dispatch_never_inherits_registry_true(self) -> None:
        self.assertIn(
            "HOLD_REGISTRY_FLAG_TRUE_UNAUTHORIZED", CONTROL_SOURCE
        )
        self.assertIn(
            "HOLD_REGISTRY_STATE_MISSING_OR_UNREADABLE", CONTROL_SOURCE
        )
        self.assertIn("effective_enabled: false", CONTROL_SOURCE)
        self.assertIn("execution_authorized: false", CONTROL_SOURCE)

    def test_raw_metamask_project_key_is_not_selected(self) -> None:
        self.assertNotIn("select project_key,", INDEX_SOURCE)
        self.assertIn(
            "project_key is not null as project_key_configured", INDEX_SOURCE
        )

    def test_all_effect_authority_is_hard_false(self) -> None:
        for field in (
            "economic_mutation_authorized",
            "provider_mutation_authorized",
            "wallet_signing_authorized",
            "native_site_mutation_authorized",
            "generalized_dispatch_authorized",
            "raw_secret_export",
        ):
            self.assertIn(f"{field}: false", CONTROL_SOURCE)

    def test_deployment_entrypoint_uses_hardened_handler(self) -> None:
        self.assertIn("createHandler,", INDEX_SOURCE)
        self.assertIn('from "./control.ts";', INDEX_SOURCE)
        self.assertIn("Deno.serve(createHandler(manifest));", INDEX_SOURCE)

    def test_candidate_is_explicitly_not_deployed(self) -> None:
        self.assertIn('version: "1.1.2-staged-candidate"', INDEX_SOURCE)
        self.assertIn(
            'deployment_state: "STAGED_REPOSITORY_ONLY_NOT_DEPLOYED"',
            INDEX_SOURCE,
        )
        self.assertIn("live_edge_function_version: 4", INDEX_SOURCE)
        self.assertIn('live_state: "HOLD_UNCHANGED"', INDEX_SOURCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
