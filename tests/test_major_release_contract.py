from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "pentarelease" / "validate_major_release.py"
TERMS_TEMPLATE = ROOT / ".pentarelease" / "templates" / "major-release-terms.v4.0.0.0.template.json"
REQUEST_TEMPLATE = ROOT / ".pentarelease" / "templates" / "major-release-request.v4.0.0.0.template.json"

SPEC = importlib.util.spec_from_file_location("validate_major_release", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MajorReleaseContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.terms_path = self.root / MODULE.EXPECTED_TERMS_PATH
        self.request_path = self.root / ".github/release-requests/crownthrive-os-v4.0.0.0.json"
        self.hold_path = self.root / "docs/versioning/RELEASE_RECONCILIATION_MANIFEST.v1.json"
        self.rollback_path = self.root / "docs/archive/RELEASE_SUPERSESSION_LEDGER.v1.json"
        self.package = self.root / MODULE.EXPECTED_PACKAGE
        for path in (
            self.terms_path,
            self.request_path,
            self.hold_path,
            self.rollback_path,
            self.package / "MANIFEST.json",
        ):
            path.parent.mkdir(parents=True, exist_ok=True)

        self.terms = json.loads(TERMS_TEMPLATE.read_text(encoding="utf-8"))
        self.terms["validity"] = {
            "requested_at": "2026-08-27T09:00:00Z",
            "not_before": "2026-08-27T10:00:00Z",
            "expires_at": "2026-08-27T13:00:00Z",
            "single_use_nonce": "ct-major-v4-test-nonce",
        }
        self.write_json(self.terms_path, self.terms)

        self.hold_path.write_text('{"schema":"hold-ledger-test"}\n', encoding="utf-8")
        self.rollback_path.write_text('{"schema":"rollback-test"}\n', encoding="utf-8")
        self.write_json(
            self.package / "MANIFEST.json",
            {
                "version": MODULE.EXPECTED_VERSION,
                "tag": MODULE.EXPECTED_TAG,
                "target_ref": "github_event_merge_sha",
                "institutional_phase": 3,
                "os_4x_effective_only_after_v4_provider_readback": True,
            },
        )
        (self.package / "RELEASE_NOTES.md").write_text("Exact v4 test notes.\n", encoding="utf-8")

        self.request = json.loads(REQUEST_TEMPLATE.read_text(encoding="utf-8"))
        self.request["authority_terms"]["sha256"] = sha256(self.terms_path)
        self.request["carry_forward_holds"]["sha256"] = sha256(self.hold_path)
        self.request["rollback_correction"]["sha256"] = sha256(self.rollback_path)
        self.request["idempotency_key"] = "ct.os.v4.0.0.0:test"
        self.request["requested_at"] = "2026-08-27T09:00:00Z"
        for gate in self.request["prepublication_gates"]:
            gate["state"] = "PASS"
            gate["evidence_refs"] = [f"evidence://{gate['gate_id']}"]
        self.write_json(self.request_path, self.request)

        self.head_sha = "1" * 40
        self.merge_sha = "2" * 40
        self.evidence = self.make_evidence()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def write_json(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def approval_body(self, *, head_sha: str | None = None) -> str:
        return "\n".join(
            (
                MODULE.EXPECTED_APPROVAL_MARKER,
                f"candidate_head_sha={head_sha or self.head_sha}",
                f"version={MODULE.EXPECTED_VERSION}",
                f"tag={MODULE.EXPECTED_TAG}",
                f"terms_sha256={sha256(self.terms_path)}",
                f"request_sha256={sha256(self.request_path)}",
            )
        )

    def make_evidence(self) -> dict:
        return {
            "repository": MODULE.EXPECTED_REPOSITORY,
            "event_name": "push",
            "event_ref": "refs/heads/main",
            "event_sha": self.merge_sha,
            "partial_retry": False,
            "approval_consumption": "unconsumed_or_same_release_identity",
            "pull_request": {
                "number": 41,
                "state": "closed",
                "merged": True,
                "merged_at": "2026-08-27T12:00:00Z",
                "base_ref": "main",
                "head_sha": self.head_sha,
                "head_repository": MODULE.EXPECTED_REPOSITORY,
                "merge_commit_sha": self.merge_sha,
            },
            "check_runs": [
                {
                    "name": "CrownThrive governed merge gate",
                    "head_sha": self.head_sha,
                    "status": "completed",
                    "conclusion": "success",
                }
            ],
            "required_checks": [
                {"name": "CrownThrive governed merge gate", "state": "SUCCESS"}
            ],
            "reviews": [
                {
                    "provider_id": "9001",
                    "actor_login": MODULE.EXPECTED_APPROVER,
                    "author_association": "OWNER",
                    "state": "APPROVED",
                    "commit_id": self.head_sha,
                    "body": self.approval_body(),
                    "approved_at": "2026-08-27T11:00:00Z",
                    "dismissed": False,
                    "revoked": False,
                }
            ],
            "comments": [],
        }

    def validate_ready_request(self) -> tuple[object, object]:
        window = MODULE.validate_terms(self.terms, ready=True)
        MODULE.validate_request(
            self.root,
            self.request,
            self.terms_path,
            sha256(self.terms_path),
            ready=True,
        )
        return window

    def validate_provider(self) -> dict:
        not_before, expires_at = self.validate_ready_request()
        return MODULE.validate_provider_evidence(
            self.evidence,
            sha256(self.request_path),
            sha256(self.terms_path),
            not_before,
            expires_at,
        )

    def test_unassigned_templates_are_hold_and_never_authorize_provider_write(self) -> None:
        result = subprocess.run(
            [
                "python3",
                str(VALIDATOR_PATH),
                "--repository-root",
                str(ROOT),
                "--mode",
                "template",
                "--request",
                str(REQUEST_TEMPLATE),
                "--terms",
                str(TERMS_TEMPLATE),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["status"], "HOLD_TEMPLATE_UNASSIGNED")
        self.assertIs(receipt["provider_write_authorized"], False)
        self.assertEqual(receipt["institutional_phase"], 3)

    def test_exact_live_owner_evidence_passes(self) -> None:
        binding = self.validate_provider()
        self.assertEqual(binding["candidate_head_sha"], self.head_sha)
        self.assertEqual(binding["merge_commit_sha"], self.merge_sha)
        self.assertEqual(binding["approval"]["provider_id"], "9001")

    def test_any_non_pass_prepublication_gate_holds(self) -> None:
        self.request["prepublication_gates"][7]["state"] = "HOLD"
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "gate_not_pass:CT-MAJOR-008"):
            self.validate_ready_request()

    def test_source_may_not_claim_provider_approval_identity(self) -> None:
        self.request["candidate_binding"]["provider_approval_id"] = "9001"
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "source_provider_approval_id"):
            self.validate_ready_request()

    def test_surrogate_or_agent_authority_holds(self) -> None:
        self.terms["authority_boundaries"]["agent_authority"] = True
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "agent_authority"):
            MODULE.validate_terms(self.terms, ready=True)

    def test_private_conversation_material_is_rejected(self) -> None:
        self.terms["privacy"]["chat_hash"] = "0" * 64
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "private_conversation_key"):
            MODULE.validate_terms(self.terms, ready=True)

    def test_wrong_actor_or_non_owner_association_holds(self) -> None:
        self.evidence["reviews"][0]["author_association"] = "MEMBER"
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "exact_owner_d3_approval_missing"):
            self.validate_provider()

    def test_stale_head_binding_holds(self) -> None:
        self.evidence["reviews"][0]["body"] = self.approval_body(head_sha="3" * 40)
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "exact_owner_d3_approval_missing"):
            self.validate_provider()

    def test_dismissed_or_revoked_review_holds(self) -> None:
        self.evidence["reviews"][0]["dismissed"] = True
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "exact_owner_d3_approval_missing"):
            self.validate_provider()

    def test_failed_required_check_holds(self) -> None:
        self.evidence["required_checks"][0]["state"] = "FAILURE"
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "required_check_failure"):
            self.validate_provider()

    def test_dispatch_without_existing_identity_retry_state_holds(self) -> None:
        self.evidence["event_name"] = "workflow_dispatch"
        self.evidence["event_ref"] = "refs/heads/main"
        self.evidence["partial_retry"] = False
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "dispatch_must_be_partial_retry"):
            self.validate_provider()

    def test_approval_after_merge_or_expiry_holds(self) -> None:
        self.evidence["reviews"][0]["approved_at"] = "2026-08-27T12:30:00Z"
        with self.assertRaisesRegex(MODULE.MajorReleaseValidationError, "exact_owner_d3_approval_missing"):
            self.validate_provider()


if __name__ == "__main__":
    unittest.main()
