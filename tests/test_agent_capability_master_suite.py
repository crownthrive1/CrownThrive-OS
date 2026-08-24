from __future__ import annotations

import json
import hashlib
import re
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_capability_master_suite as suite  # noqa: E402
import archive_integrity  # noqa: E402
import framework_compiler  # noqa: E402
import internal_linkage  # noqa: E402
import supply_chain_integrity  # noqa: E402


class SuiteTests(unittest.TestCase):
    def test_suite_invariants(self) -> None:
        result = suite.validate()
        self.assertEqual(result["status"], "PASS_CONTROLLED_TEST_PENDING_INDEPENDENT_VERIFICATION")
        self.assertEqual(result["agent_count"], 26)
        self.assertEqual(result["committee_surface_count"], 14)
        self.assertEqual(result["schedule_count"], 8)
        self.assertEqual(set(result["mode_counts"]), {"rigid", "fluid", "hybrid"})

    def test_one_candidate_skill_per_agent(self) -> None:
        candidates = suite.skill_candidates()
        self.assertEqual(len(candidates["packages"]), 26)
        self.assertTrue(all(row["commercial_state"] == "HOLD" for row in candidates["packages"]))
        self.assertTrue(all(row["mcp_state"] == "DISABLED" for row in candidates["packages"]))

    def test_framework_compiler_is_deterministic_and_fail_closed(self) -> None:
        self_test = framework_compiler.self_test()
        self.assertTrue(self_test["deterministic"])
        candidate = json.loads((ROOT / "framework-candidates/thrivealumni-committee-support.v1.json").read_text(encoding="utf-8"))
        compiled = framework_compiler.compile_candidate(candidate)
        self.assertEqual(compiled["test_status"], "SELF_TEST_PASS_PENDING_INDEPENDENT_VERIFICATION")
        self.assertEqual(compiled["factory_integration"]["framework_count_delta"], 0)
        with self.assertRaises(framework_compiler.CompileError):
            framework_compiler.compile_candidate(dict(candidate, activation_allowed=True))
        with self.assertRaises(framework_compiler.CompileError):
            framework_compiler.compile_candidate(dict(candidate, activation_allowed="false"))
        with self.assertRaises(framework_compiler.CompileError):
            framework_compiler.compile_candidate(dict(candidate, framework_count_delta=False))
        for key in framework_compiler.CONSEQUENTIAL_FLAGS:
            for unsafe in (True, 1, "true", [], {}, None):
                with self.subTest(key=key, unsafe=unsafe):
                    with self.assertRaises(framework_compiler.CompileError):
                        framework_compiler.compile_candidate(dict(candidate, **{key: unsafe}))
            missing = dict(candidate)
            missing.pop(key)
            with self.assertRaises(framework_compiler.CompileError):
                framework_compiler.compile_candidate(missing)
        with self.assertRaises(framework_compiler.CompileError):
            framework_compiler.compile_candidate(dict(candidate, can_spend=True))
        with self.assertRaises(framework_compiler.CompileError):
            framework_compiler.compile_candidate(dict(candidate, candidate_id=["not", "an", "id"]))
        with self.assertRaises(framework_compiler.CompileError):
            framework_compiler.compile_candidate(dict(candidate, schema_version={"invalid": True}))

    def test_archive_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unsafe.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.txt", "blocked")
            result = archive_integrity.inspect_zip(path)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any("unsafe member" in error for error in result["errors"]))
            self.assertTrue(any("skipped" in warning for warning in result["warnings"]))

    def test_archive_normalization_collisions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "colliding.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("a/b", "one")
                archive.writestr("a/./b", "two")
                archive.writestr("a//b", "three")
            result = archive_integrity.inspect_zip(path, strict_names=True)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any("dot" in error or "empty" in error for error in result["errors"]))

    def test_archive_portability_special_files_and_exact_manifest_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive_path = root / "unsafe-portable.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("CON.txt", "reserved")
                special = zipfile.ZipInfo("fifo")
                special.create_system = 3
                special.external_attr = 0o010644 << 16
                archive.writestr(special, "special")
            result = archive_integrity.inspect_zip(archive_path, strict_names=True)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any("reserved" in error.lower() for error in result["errors"]))
            self.assertTrue(any("special-file" in error for error in result["errors"]))

            base = root / "files"
            base.mkdir()
            listed = base / "listed.txt"
            unlisted = base / "unlisted.txt"
            listed.write_text("listed\n", encoding="utf-8")
            unlisted.write_text("unlisted\n", encoding="utf-8")
            manifest = root / "SHA256SUMS"
            manifest.write_text(f"{archive_integrity.sha256_file(listed)}  listed.txt\n", encoding="utf-8")
            verification = archive_integrity.verify_manifest(
                manifest,
                base,
                exact=True,
                trusted_manifest_sha256=archive_integrity.sha256_file(manifest),
            )
            self.assertEqual(verification["status"], "FAIL")
            self.assertTrue(any("unlisted file" in error for error in verification["errors"]))

    def test_link_application_requires_receipt_and_is_additive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            docs = root / "docs"
            docs.mkdir()
            source = docs / "source.mdx"
            target = docs / "target.mdx"
            source.write_text("---\ntitle: Source\n---\n\nBody\n", encoding="utf-8")
            target.write_text("---\ntitle: Target\n---\n\nBody\n", encoding="utf-8")
            manifest = root / "links.json"
            edge = {
                "edge_id": "edge-1",
                "originator_id": "ct.chlom.agent.linkage-curator",
                "source": "docs/source.mdx",
                "target": "docs/target.mdx",
                "status": "CANDIDATE",
                "approval_receipt": None,
            }
            manifest.write_text(json.dumps({"edges": [edge]}), encoding="utf-8")
            result = internal_linkage.apply_approved(root, manifest)
            self.assertEqual(result["status"], "NO_CHANGE")
            edge.update(status="APPROVED", approval_receipt="weak-receipt")
            manifest.write_text(json.dumps({"edges": [edge]}), encoding="utf-8")
            result = internal_linkage.apply_approved(root, manifest)
            self.assertEqual(result["status"], "HOLD")
            now = datetime.now(timezone.utc)
            receipt = {
                "edge_id": "edge-1",
                "decision": "APPROVED",
                "scope": "INTERNAL_LINK_ADD",
                "originator_id": edge["originator_id"],
                "reviewer_kind": "human",
                "reviewer_id": "human:authorized-reviewer",
                "review_execution_id": "review:test:001",
                "issued_at": (now - timedelta(minutes=1)).isoformat(),
                "expires_at": (now + timedelta(days=1)).isoformat(),
                "source_sha256": internal_linkage.sha256_file(source),
                "target_sha256": internal_linkage.sha256_file(target),
                "independent": True,
            }
            receipt["receipt_sha256"] = hashlib.sha256(
                internal_linkage.canonical_receipt_payload(receipt)
            ).hexdigest()
            receipts = root / "receipts"
            receipts.mkdir()
            receipt_path = receipts / "edge-1.json"
            receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            edge.pop("approval_receipt", None)
            edge["approval_receipt_ref"] = "receipts/edge-1.json"
            edge["approval_receipt_file_sha256"] = internal_linkage.sha256_file(receipt_path)
            manifest.write_text(json.dumps({"edges": [edge]}), encoding="utf-8")
            trusted_digest = internal_linkage.sha256_file(receipt_path)
            result = internal_linkage.apply_approved(
                root,
                manifest,
                trusted_receipt_sha256=trusted_digest,
                authorized_reviewer_ids={"human:authorized-reviewer"},
            )
            self.assertEqual(result["delete_count"], 0)
            self.assertIn("edge-1", result["applied"])
            self.assertIn("CT-MANAGED-LINK:edge-1", source.read_text(encoding="utf-8"))

    def test_link_application_cannot_mutate_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflows = root / ".github" / "workflows"
            docs = root / "docs"
            workflows.mkdir(parents=True)
            docs.mkdir()
            source = workflows / "unsafe.mdx"
            target = docs / "target.mdx"
            source.write_text("workflow\n", encoding="utf-8")
            target.write_text("target\n", encoding="utf-8")
            manifest = root / "links.json"
            edge = {
                "edge_id": "edge-sensitive",
                "originator_id": "ct.chlom.agent.linkage-curator",
                "source": ".github/workflows/unsafe.mdx",
                "target": "docs/target.mdx",
                "status": "APPROVED",
                "approval_receipt": {},
            }
            manifest.write_text(json.dumps({"edges": [edge]}), encoding="utf-8")
            result = internal_linkage.apply_approved(root, manifest)
            self.assertEqual(result["status"], "HOLD")
            self.assertEqual(source.read_text(encoding="utf-8"), "workflow\n")

    def test_link_batch_and_expired_receipts_make_zero_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            docs = root / "docs"
            receipts = root / "receipts"
            docs.mkdir()
            receipts.mkdir()
            source = docs / "source.mdx"
            target = docs / "target.mdx"
            source.write_text("source\n", encoding="utf-8")
            target.write_text("target\n", encoding="utf-8")
            receipt = {
                "edge_id": "expired-edge",
                "decision": "APPROVED",
                "scope": "INTERNAL_LINK_ADD",
                "originator_id": "ct.chlom.agent.linkage-curator",
                "reviewer_kind": "human",
                "reviewer_id": "human:authorized-reviewer",
                "review_execution_id": "review:expired:001",
                "issued_at": "2025-01-01T00:00:00+00:00",
                "expires_at": "2025-01-02T00:00:00+00:00",
                "source_sha256": internal_linkage.sha256_file(source),
                "target_sha256": internal_linkage.sha256_file(target),
                "independent": True,
            }
            receipt["receipt_sha256"] = hashlib.sha256(
                internal_linkage.canonical_receipt_payload(receipt)
            ).hexdigest()
            receipt_path = receipts / "expired.json"
            receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            edge = {
                "edge_id": "expired-edge",
                "originator_id": "ct.chlom.agent.linkage-curator",
                "source": "docs/source.mdx",
                "target": "docs/target.mdx",
                "status": "APPROVED",
                "approval_receipt_ref": "receipts/expired.json",
                "approval_receipt_file_sha256": internal_linkage.sha256_file(receipt_path),
            }
            manifest = root / "links.json"
            manifest.write_text(json.dumps({"edges": [edge]}), encoding="utf-8")
            result = internal_linkage.apply_approved(
                root,
                manifest,
                trusted_receipt_sha256=internal_linkage.sha256_file(receipt_path),
                authorized_reviewer_ids={"human:authorized-reviewer"},
            )
            self.assertEqual(result["status"], "HOLD")
            self.assertTrue(any("expired" in row["reason"] for row in result["skipped"]))
            self.assertEqual(source.read_text(encoding="utf-8"), "source\n")

    def test_link_receipt_requires_out_of_band_trust_and_current_issuance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            docs = root / "docs"
            receipts = root / "linkage" / "receipts"
            docs.mkdir()
            receipts.mkdir(parents=True)
            source = docs / "source.mdx"
            target = docs / "target.mdx"
            source.write_text("source\n", encoding="utf-8")
            target.write_text("target\n", encoding="utf-8")
            now = datetime.now(timezone.utc)
            receipt = {
                "edge_id": "forged-edge",
                "decision": "APPROVED",
                "scope": "INTERNAL_LINK_ADD",
                "originator_id": "ct.chlom.agent.linkage-curator",
                "reviewer_kind": "human",
                "reviewer_id": "human:attacker",
                "review_execution_id": "self-asserted",
                "issued_at": (now + timedelta(days=1)).isoformat(),
                "expires_at": (now + timedelta(days=2)).isoformat(),
                "source_sha256": internal_linkage.sha256_file(source),
                "target_sha256": internal_linkage.sha256_file(target),
                "independent": True,
            }
            receipt["receipt_sha256"] = hashlib.sha256(
                internal_linkage.canonical_receipt_payload(receipt)
            ).hexdigest()
            receipt_path = receipts / "forged.json"
            receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            edge = {
                "edge_id": "forged-edge",
                "originator_id": "ct.chlom.agent.linkage-curator",
                "source": "docs/source.mdx",
                "target": "docs/target.mdx",
                "status": "APPROVED",
                "approval_receipt_ref": "receipts/forged.json",
                "approval_receipt_file_sha256": internal_linkage.sha256_file(receipt_path),
            }
            manifest = root / "linkage" / "links.json"
            manifest.write_text(json.dumps({"edges": [edge]}), encoding="utf-8")
            trusted_digest = internal_linkage.sha256_file(receipt_path)

            no_digest = internal_linkage.apply_approved(
                root,
                manifest,
                authorized_reviewer_ids={"human:attacker"},
            )
            self.assertEqual(no_digest["status"], "HOLD")
            self.assertTrue(any("trusted receipt digest absent" in row["reason"] for row in no_digest["skipped"]))
            no_reviewer_allowlist = internal_linkage.apply_approved(
                root,
                manifest,
                trusted_receipt_sha256=trusted_digest,
            )
            self.assertEqual(no_reviewer_allowlist["status"], "HOLD")
            self.assertTrue(
                any("out-of-band authorized set" in row["reason"] for row in no_reviewer_allowlist["skipped"])
            )
            untrusted_reviewer = internal_linkage.apply_approved(
                root,
                manifest,
                trusted_receipt_sha256=trusted_digest,
                authorized_reviewer_ids={"human:authorized-reviewer"},
            )
            self.assertEqual(untrusted_reviewer["status"], "HOLD")
            future_issuance = internal_linkage.apply_approved(
                root,
                manifest,
                trusted_receipt_sha256=trusted_digest,
                authorized_reviewer_ids={"human:attacker"},
            )
            self.assertEqual(future_issuance["status"], "HOLD")
            self.assertEqual(source.read_text(encoding="utf-8"), "source\n")

            second = dict(edge, edge_id="second-edge")
            manifest.write_text(json.dumps({"edges": [edge, second]}), encoding="utf-8")
            result = internal_linkage.apply_approved(root, manifest)
            self.assertEqual(result["status"], "HOLD")
            self.assertEqual(source.read_text(encoding="utf-8"), "source\n")

    def test_suite_workflow_supply_chain_controls(self) -> None:
        result = supply_chain_integrity.inspect_workflow(ROOT / ".github/workflows/agent-capability-master-suite-governance.yml")
        self.assertNotEqual(result["status"], "FAIL")

    def test_workflow_adversarial_permissions_and_pins_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unsafe.yml"
            path.write_text(
                "name: unsafe\n"
                "on: [pull_request]\n"
                "permissions:\n  contents: read\n"
                "concurrency:\n  group: test\n  cancel-in-progress: true\n"
                "jobs:\n  test:\n    permissions:\n      contents: write\n"
                "    timeout-minutes: 5\n    steps:\n"
                "      - uses: owner/action@main\n"
                "      - uses: docker://example/image:latest\n",
                encoding="utf-8",
            )
            result = supply_chain_integrity.inspect_workflow(path)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any("not pinned" in error for error in result["errors"]))
            self.assertTrue(any("write-capable" in error for error in result["errors"]))

    def test_workflow_quoted_keys_and_spaced_uses_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unsafe-quoted.yml"
            path.write_text(
                "name: unsafe\n"
                '"on":\n  "pull_request_target":\n  workflow_dispatch:\n'
                "permissions:\n  contents: read\n"
                "concurrency:\n  group: test\n  cancel-in-progress: true\n"
                'jobs:\n  test:\n    "permissions": write-all\n'
                "    runs-on: ubuntu-latest\n    timeout-minutes: 5\n    steps:\n"
                "      - uses : owner/action@main\n",
                encoding="utf-8",
            )
            result = supply_chain_integrity.inspect_workflow(path)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any("not pinned" in error for error in result["errors"]))
            self.assertTrue(any("write-capable" in error for error in result["errors"]))
            self.assertTrue(any("pull_request_target" in error for error in result["errors"]))

    def test_workflow_flow_style_security_keys_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            for name, trigger, steps in (
                ("mapping", "on: {pull_request_target: {}}\n", "steps:\n      - {uses: owner/action@main}\n"),
                ("sequence", "on: [pull_request_target]\n", "steps: [{uses: owner/action@main}]\n"),
            ):
                with self.subTest(name=name):
                    path = Path(temp) / f"unsafe-flow-{name}.yml"
                    path.write_text(
                        "name: unsafe-flow\n"
                        + trigger
                        + "permissions:\n  contents: read\n"
                        + "concurrency:\n  group: test\n  cancel-in-progress: true\n"
                        + "jobs:\n  test:\n    runs-on: ubuntu-latest\n"
                        + "    timeout-minutes: 5\n    "
                        + steps,
                        encoding="utf-8",
                    )
                    result = supply_chain_integrity.inspect_workflow(path)
                    self.assertEqual(result["status"], "FAIL")
                    self.assertTrue(any("not pinned" in error for error in result["errors"]))
                    self.assertTrue(any("pull_request_target" in error for error in result["errors"]))

    def test_registry_schema_rejects_missing_and_extra_agent_fields(self) -> None:
        registry = suite.load_json(suite.REGISTRY)
        schema = suite.load_json(suite.SCHEMA)
        extra = json.loads(json.dumps(registry))
        extra["agents"][0]["unexpected"] = True
        self.assertTrue(suite.validate_schema_instance(extra, schema, schema))
        missing = json.loads(json.dumps(registry))
        del missing["agents"][0]["parent_binding"]
        self.assertTrue(suite.validate_schema_instance(missing, schema, schema))

    def test_missing_control_artifacts_and_canonical_baseline_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing.json"
            for attribute in ("MASTER", "SCHEMA", "LINKAGE"):
                with self.subTest(attribute=attribute), mock.patch.object(suite, attribute, missing):
                    with self.assertRaises(OSError):
                        suite.validate()
            with self.assertRaises(suite.SuiteValidationError):
                suite.resolve_baseline_agents(Path(temp), True)

    def test_public_payload_targeted_manifests_and_recursive_scan_are_sanitized(self) -> None:
        schedule = suite.load_json(suite.SCHEDULES)
        self.assertEqual(schedule["dispatcher"]["external_task_reference"], "PRIVATE_CONTROL_PLANE_REFERENCE")
        self.assertFalse(any(re.fullmatch(r"[0-9a-f]{32}", value) for value in schedule["dispatcher"].values() if isinstance(value, str)))

        custody = suite.load_json(suite.CUSTODY)
        self.assertEqual(
            {row["store_class"] for row in custody["destinations"]},
            {"human_recovery_archive", "replaceable_private_object_store", "secret_seal_store"},
        )
        self.assertEqual(custody["provider_bindings"], "PRIVATE_CONTROL_PLANE_REFERENCE")

        pricing = suite.load_json(suite.PRICING)
        self.assertEqual(pricing["top_up_candidates"], [])
        self.assertNotIn("minimum_credit_transaction", pricing)

        quarantine = suite.load_json(suite.QUARANTINE)
        self.assertEqual(quarantine["classification"], "PUBLIC_STANDARD_METADATA_ONLY")
        self.assertFalse(any(isinstance(value, int) and not isinstance(value, bool) for value in quarantine.values()))
        self.assertIsNone(re.search(r"HC-\d{4}", json.dumps(quarantine)))

        public_roots = [
            ROOT / ".github" / "workflows",
            ROOT / "automation",
            ROOT / "changelog",
            ROOT / "developers" / "agents",
            ROOT / "developers" / "manifests",
            ROOT / "developers" / "schemas",
            ROOT / "framework-candidates",
            ROOT / "governance",
            ROOT / "linkage",
            ROOT / "runbooks",
            ROOT / "scripts",
            ROOT / "tests",
        ]
        forbidden = {
            "vault_locator": re.compile("vault" + r"://"),
            "provider_folder_locator": re.compile("folder" + r":[A-Za-z0-9_-]{20,}"),
            "provider_bucket_locator": re.compile("bucket" + r":[A-Za-z0-9._-]+"),
            "private_control_field": re.compile(
                r'"(?:external_task' + r'_id|destination_' + r'ref|manifest_hmac_' + r'sha256)"\s*:'
            ),
            "controlled_price_field": re.compile(
                r'"(?:usd_' + r'cents|minimum_credit_' + r'transaction)"\s*:'
            ),
            "help_center_record_id": re.compile(r"HC-\d{4}"),
            "opaque_32_hex_identifier": re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])"),
        }
        violations: list[str] = []
        for public_root in public_roots:
            for path in sorted(public_root.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".mdx", ".py", ".yml", ".yaml"}:
                    continue
                text = path.read_text(encoding="utf-8")
                for label, pattern in forbidden.items():
                    if pattern.search(text):
                        violations.append(f"{path.relative_to(ROOT)}:{label}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
