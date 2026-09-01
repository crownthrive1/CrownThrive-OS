from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from runtime.penta_survival import (
    PentaSurvivalError,
    coverage_report,
    digest,
    evaluate_contract,
    evaluate_proof_bundle,
    ratchet_report,
    release_gate,
    validate_policy,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "data/penta/survival-policy.v1.json").read_text(encoding="utf-8"))
TEMPLATE = json.loads((ROOT / "data/penta/survival-contract.template.v1.json").read_text(encoding="utf-8"))
PROOF_TEMPLATE = json.loads((ROOT / "data/penta/survival-proof.template.v1.json").read_text(encoding="utf-8"))
PLAN = json.loads((ROOT / "tests/survival/model-off-survival-test-plan.v1.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def replace_strings(value, old: str, new: str):
    if isinstance(value, dict):
        return {key: replace_strings(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_strings(item, old, new) for item in value]
    if isinstance(value, str):
        return value.replace(old, new)
    return value


def production_contract(penta_id: str = "penta.alpha", canonical_name: str = "PentaAlpha") -> dict:
    suffix = penta_id.split(".", 1)[1]
    contract = replace_strings(deepcopy(TEMPLATE), "example", suffix)
    contract["contract_id"] = f"ct.penta.survival.{suffix}.v1"
    contract["penta_id"] = penta_id
    contract["canonical_name"] = canonical_name
    contract["maturity"] = "production"
    contract["persistent_identity"]["stable_id"] = penta_id
    contract["evidence"]["bundle_ref"] = f"penta/survival/evidence/{penta_id}.v1.json"
    contract["attestation"].update(
        {
            "status": "verified",
            "declared_by": penta_id,
            "verifier_independent": True,
            "verified_by": "penta.certify",
            "verified_at": "2026-08-31T12:00:00Z",
            "notes": "Exact-subject test fixture.",
        }
    )
    function_hash = digest(contract["deterministic_functions"]["functions"])
    contract["deterministic_functions"]["function_set_sha256"] = function_hash
    contract["evidence"]["subject"]["function_set_sha256"] = function_hash
    return contract


def production_proof(contract: dict) -> dict:
    proof = replace_strings(deepcopy(PROOF_TEMPLATE), "example", "alpha")
    proof = replace_strings(proof, "template", "fixture")
    proof["proof_id"] = f"ct.penta.survival-proof.{contract['penta_id']}.fixture.v1"
    proof["penta_id"] = contract["penta_id"]
    proof["subject"] = {
        "source_commit": contract["release_binding"]["source_commit"],
        "artifact_sha256": contract["release_binding"]["artifact_sha256"],
        "doctrine_version": contract["release_binding"]["doctrine_version"],
        "compiled_behavior_hash": contract["release_binding"]["compiled_behavior_hash"],
        "function_set_sha256": contract["deterministic_functions"]["function_set_sha256"],
        "runtime_version": contract["release_binding"]["runtime_version"],
        "build_id": contract["release_binding"]["build_id"],
    }
    proof["test_plan_sha256"] = digest(PLAN)
    proof["executed_at"] = "2026-08-31T11:55:00Z"
    proof["verified_at"] = contract["attestation"]["verified_at"]
    proof["expires_at"] = contract["evidence"]["expires_at"]
    proof["verifier"].update(
        {
            "verifier_id": contract["attestation"]["verified_by"],
            "identity_ref": "data/penta/test.catalog.json#penta.certify",
            "verification_run_ref": "workflow:fixture-run-1001",
            "receipt_chain_ref": "dail:fixture-chain-1001",
        }
    )
    return proof


def bind_proof(contract: dict, proof: dict) -> None:
    proof_sha = digest(proof)
    contract["evidence"]["manifest_sha256"] = proof_sha
    contract["attestation"]["evidence_bundle_sha256"] = proof_sha


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixture_root(*, include_contract: bool = True, corrupt_hash: bool = False) -> tempfile.TemporaryDirectory:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    write_json(root / "data/penta/survival-policy.v1.json", POLICY)
    write_json(root / "tests/survival/model-off-survival-test-plan.v1.json", PLAN)
    family = {
        "registry_id": "crownthrive.penta.family",
        "catalogs": [{"catalog_id": "test", "path": "data/penta/test.catalog.json", "required": True}],
    }
    write_json(root / "data/penta/family.registry.json", family)
    catalog = {
        "systems": [
            {"machine_key": "penta.alpha", "canonical_name": "PentaAlpha", "maturity": "production"},
            {"machine_key": "penta.beta", "canonical_name": "PentaBeta", "maturity": "specified"},
        ]
    }
    write_json(root / "data/penta/test.catalog.json", catalog)
    contracts = []
    if include_contract:
        contract = production_contract()
        proof = production_proof(contract)
        bind_proof(contract, proof)
        write_json(root / contract["evidence"]["bundle_ref"], proof)
        contract_ref = "data/penta/survival-contracts/penta.alpha.v1.json"
        write_json(root / contract_ref, contract)
        contracts.append(
            {
                "penta_id": "penta.alpha",
                "contract_ref": contract_ref,
                "contract_sha256": "f" * 64 if corrupt_hash else digest(contract),
            }
        )
    registry = {
        "registry_id": "ct.penta.survival-contracts.v1",
        "registry_version": "1.0.0",
        "policy_ref": "data/penta/survival-policy.v1.json",
        "family_registry_ref": "data/penta/family.registry.json",
        "contract_directory": "data/penta/survival-contracts",
        "failure_disposition": "HOLD_FAIL_CLOSED",
        "contracts": contracts,
    }
    write_json(root / "data/penta/survival-contracts.registry.json", registry)
    return temp


def declaration_contract(penta_id: str, canonical_name: str, maturity: str = "specified") -> dict:
    suffix = penta_id.split(".", 1)[1]
    contract = replace_strings(deepcopy(TEMPLATE), "example", suffix)
    contract["contract_id"] = f"ct.penta.survival.{suffix}.v1"
    contract["penta_id"] = penta_id
    contract["canonical_name"] = canonical_name
    contract["maturity"] = maturity
    contract["persistent_identity"]["stable_id"] = penta_id
    contract["attestation"]["declared_by"] = penta_id
    function_hash = digest(contract["deterministic_functions"]["functions"])
    contract["deterministic_functions"]["function_set_sha256"] = function_hash
    contract["evidence"]["subject"]["function_set_sha256"] = function_hash
    return contract


def git_fixture_root() -> tuple[tempfile.TemporaryDirectory, Path, str]:
    temp = fixture_root(include_contract=True)
    root = Path(temp.name)
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Penta Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "penta-test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, capture_output=True)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    return temp, root, base_sha


class PentaSurvivalContractTests(unittest.TestCase):
    def test_policy_is_strict_and_complete(self) -> None:
        validate_policy(POLICY)

    def test_template_is_structurally_valid_but_not_production_eligible(self) -> None:
        report = evaluate_contract(TEMPLATE, policy=POLICY, now=NOW)
        self.assertEqual([], report["errors"])
        self.assertEqual("DECLARED", report["disposition"])
        self.assertFalse(report["production_eligible"])

    def test_valid_production_contract_is_not_self_verified(self) -> None:
        report = evaluate_contract(production_contract(), policy=POLICY, now=NOW)
        self.assertEqual([], report["errors"])
        self.assertEqual("VERIFICATION_CLAIM", report["disposition"])
        self.assertFalse(report["production_eligible"])
        self.assertFalse(report["self_asserted_verification_accepted"])

    def test_executed_proof_bundle_validates_exact_subject(self) -> None:
        contract = production_contract()
        proof = production_proof(contract)
        bind_proof(contract, proof)
        report = evaluate_proof_bundle(proof, contract, PLAN, now=NOW)
        self.assertEqual([], report["errors"])
        self.assertEqual("PASS", report["disposition"])

    def test_executed_proof_rejects_missing_case(self) -> None:
        contract = production_contract()
        proof = production_proof(contract)
        proof["cases"] = proof["cases"][:-1]
        proof["summary"]["case_count"] -= 1
        proof["summary"]["pass_count"] -= 1
        report = evaluate_proof_bundle(proof, contract, PLAN, now=NOW)
        self.assertEqual("HOLD_FAIL_CLOSED", report["disposition"])
        self.assertTrue(any("proof cases missing" in item for item in report["errors"]))

    def test_contract_id_is_canonical(self) -> None:
        contract = production_contract()
        contract["contract_id"] = "survival-alpha"
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn(
            "contract_id must use ct.penta.survival.<identity>.v<integer> form",
            report["errors"],
        )

    def test_receipt_is_deterministic(self) -> None:
        contract = production_contract()
        first = evaluate_contract(contract, policy=POLICY, now=NOW)
        second = evaluate_contract(deepcopy(contract), policy=POLICY, now=NOW)
        self.assertEqual(first["contract_sha256"], second["contract_sha256"])
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])

    def test_identity_must_match_penta_id(self) -> None:
        contract = production_contract()
        contract["persistent_identity"]["stable_id"] = "penta.other"
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn("persistent_identity.stable_id must equal penta_id", report["errors"])

    def test_authoritative_state_cannot_be_memory_only(self) -> None:
        contract = production_contract()
        contract["persistent_state"]["externalized"] = False
        contract["persistent_state"]["in_memory_authoritative"] = True
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn("externalized must be true", report["errors"])
        self.assertIn("in_memory_authoritative must be false", report["errors"])

    def test_model_cannot_authorize_or_mutate(self) -> None:
        contract = production_contract()
        contract["authority_enforcement"]["model_can_authorize"] = True
        contract["authority_enforcement"]["model_can_mutate_authoritative_state"] = True
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn("model_can_authorize must be false", report["errors"])
        self.assertIn("model_can_mutate_authoritative_state must be false", report["errors"])

    def test_queue_requires_idempotency_and_durability(self) -> None:
        contract = production_contract()
        binding = contract["queues"]["bindings"][0]
        binding["durable"] = False
        binding["idempotent_consumer"] = False
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn("durable must be true", report["errors"])
        self.assertIn("idempotent_consumer must be true", report["errors"])

    def test_lease_requires_fencing_and_valid_renewal(self) -> None:
        contract = production_contract()
        binding = contract["leases"]["bindings"][0]
        binding["fencing_token"] = False
        binding["renewal_seconds"] = binding["ttl_seconds"]
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn("fencing_token must be true", report["errors"])
        self.assertTrue(any("renewal_seconds must be less" in item for item in report["errors"]))

    def test_function_set_digest_must_match(self) -> None:
        contract = production_contract()
        contract["deterministic_functions"]["function_set_sha256"] = "a" * 64
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn(
            "deterministic_functions.function_set_sha256 does not match canonical functions array",
            report["errors"],
        )

    def test_evidence_must_bind_exact_release(self) -> None:
        contract = production_contract()
        contract["evidence"]["subject"]["source_commit"] = "2" * 40
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn(
            "evidence.subject.source_commit must equal release_binding.source_commit",
            report["errors"],
        )

    def test_expired_evidence_blocks_production(self) -> None:
        contract = production_contract()
        contract["evidence"]["expires_at"] = "2026-08-30T12:00:00Z"
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn("production/certified survival evidence is expired", report["errors"])

    def test_production_requires_independent_verified_attestation(self) -> None:
        contract = production_contract()
        contract["attestation"]["status"] = "declared"
        contract["attestation"]["verifier_independent"] = False
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn("certified/production maturity requires attestation.status=verified", report["errors"])
        self.assertIn("certified/production maturity requires an independent verifier", report["errors"])

    def test_model_replacement_is_required_when_model_is_used(self) -> None:
        contract = production_contract()
        contract["replaceable_model"]["applicable"] = False
        contract["replaceable_model"]["not_applicable_reason"] = "No replacement path"
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn(
            "replaceable_model.applicable must be true when model_dependency.mode is not none",
            report["errors"],
        )

    def test_proposal_required_model_cannot_claim_full_service_without_model(self) -> None:
        contract = production_contract()
        contract["model_dependency"]["mode"] = "proposal_required"
        contract["degraded_without_model"]["mode"] = "full_deterministic_service"
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn(
            "proposal_required model dependency cannot claim full_deterministic_service without the model",
            report["errors"],
        )

    def test_degraded_operations_are_unique_nonempty_strings(self) -> None:
        contract = production_contract()
        contract["degraded_without_model"]["allowed_operations"] = ["queue_work", "", "queue_work"]
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertIn("allowed_operations[1] must be a non-empty string", report["errors"])
        self.assertIn("allowed_operations must not contain duplicate values", report["errors"])

    def test_restart_matrix_requires_all_core_cases(self) -> None:
        contract = production_contract()
        contract["restart_behavior"]["tested_cases"].remove("model_replaced")
        report = evaluate_contract(contract, policy=POLICY, now=NOW)
        self.assertTrue(any("restart_behavior.tested_cases missing" in item for item in report["errors"]))

    def test_coverage_holds_missing_production_contract_and_tracks_preproduction_debt(self) -> None:
        temp = fixture_root(include_contract=False)
        self.addCleanup(temp.cleanup)
        report = coverage_report(Path(temp.name))
        self.assertEqual("HOLD_FAIL_CLOSED", report["disposition"])
        self.assertIn("penta.alpha", report["production_blockers"])
        self.assertIn("penta.beta", report["declaration_debt"])

    def test_coverage_passes_production_and_keeps_preproduction_debt_visible(self) -> None:
        temp = fixture_root(include_contract=True)
        self.addCleanup(temp.cleanup)
        report = coverage_report(Path(temp.name))
        self.assertEqual("PASS", report["disposition"])
        self.assertEqual([], report["production_blockers"])
        self.assertIn("penta.beta", report["declaration_debt"])

    def test_retired_member_retains_survival_declaration_debt(self) -> None:
        temp = fixture_root(include_contract=True)
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        catalog_path = root / "data/penta/test.catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["systems"].append(
            {"machine_key": "penta.retired", "canonical_name": "PentaRetired", "maturity": "retired"}
        )
        write_json(catalog_path, catalog)
        report = coverage_report(root)
        self.assertIn("penta.retired", report["declaration_debt"])

    def test_registry_hash_mismatch_holds(self) -> None:
        temp = fixture_root(include_contract=True, corrupt_hash=True)
        self.addCleanup(temp.cleanup)
        report = coverage_report(Path(temp.name))
        self.assertEqual("HOLD_FAIL_CLOSED", report["disposition"])
        alpha = next(item for item in report["members"] if item["penta_id"] == "penta.alpha")
        self.assertIn("registry contract_sha256 does not match contract", alpha["reasons"])

    def test_release_gate_requires_exact_source_and_artifact(self) -> None:
        temp = fixture_root(include_contract=True)
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Penta Test"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "penta-test@example.invalid"], cwd=root, check=True)
        candidate_path = root / "runtime/candidate.bin"
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_text("exact candidate", encoding="utf-8")
        subprocess.run(["git", "add", "runtime/candidate.bin"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "candidate"], cwd=root, check=True, capture_output=True)
        candidate_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()

        contract_path = root / "data/penta/survival-contracts/penta.alpha.v1.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["release_binding"]["source_commit"] = candidate_sha
        contract["release_binding"]["exact_source_ref"] = f"repo:test@{candidate_sha}"
        contract["evidence"]["subject"]["source_commit"] = candidate_sha
        proof = production_proof(contract)
        bind_proof(contract, proof)
        write_json(root / contract["evidence"]["bundle_ref"], proof)
        write_json(contract_path, contract)
        registry_path = root / "data/penta/survival-contracts.registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["contracts"][0]["contract_sha256"] = digest(contract)
        write_json(registry_path, registry)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "proof metadata"], cwd=root, check=True, capture_output=True)

        good = release_gate(
            root,
            "penta.alpha",
            source_commit=candidate_sha,
            artifact_sha256=contract["release_binding"]["artifact_sha256"],
            doctrine_version=contract["release_binding"]["doctrine_version"],
            compiled_behavior_hash=contract["release_binding"]["compiled_behavior_hash"],
        )
        self.assertEqual("PASS", good["disposition"])
        self.assertTrue(good["metadata_split_preserved"])
        bad = release_gate(
            root,
            "penta.alpha",
            source_commit="9" * 40,
            artifact_sha256=contract["release_binding"]["artifact_sha256"],
        )
        self.assertEqual("HOLD_FAIL_CLOSED", bad["disposition"])
        self.assertIn("requested source_commit does not match survival contract", bad["reasons"])

    def test_ratchet_blocks_modified_member_without_declaration(self) -> None:
        temp, root, base_sha = git_fixture_root()
        self.addCleanup(temp.cleanup)
        catalog_path = root / "data/penta/test.catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["systems"][1]["purpose"] = "Changed behavior requires a survival declaration."
        write_json(catalog_path, catalog)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "change beta"], cwd=root, check=True, capture_output=True)
        report = ratchet_report(root, base_sha)
        self.assertEqual("HOLD_FAIL_CLOSED", report["disposition"])
        beta = next(item for item in report["checked_members"] if item.get("penta_id") == "penta.beta")
        self.assertIn("missing survival registry entry", beta["reasons"])

    def test_ratchet_accepts_modified_member_with_valid_declaration(self) -> None:
        temp, root, base_sha = git_fixture_root()
        self.addCleanup(temp.cleanup)
        catalog_path = root / "data/penta/test.catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["systems"][1]["purpose"] = "Changed behavior with declared survival semantics."
        write_json(catalog_path, catalog)
        contract = declaration_contract("penta.beta", "PentaBeta")
        contract_ref = "data/penta/survival-contracts/penta.beta.v1.json"
        write_json(root / contract_ref, contract)
        registry_path = root / "data/penta/survival-contracts.registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["contracts"].append(
            {"penta_id": "penta.beta", "contract_ref": contract_ref, "contract_sha256": digest(contract)}
        )
        write_json(registry_path, registry)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "declare beta"], cwd=root, check=True, capture_output=True)
        report = ratchet_report(root, base_sha)
        self.assertEqual("PASS", report["disposition"])
        self.assertEqual(0, report["blocker_count"])

    def test_ratchet_blocks_unregistered_contract_file(self) -> None:
        temp, root, base_sha = git_fixture_root()
        self.addCleanup(temp.cleanup)
        orphan = declaration_contract("penta.beta", "PentaBeta")
        write_json(root / "data/penta/survival-contracts/orphan.v1.json", orphan)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "orphan contract"], cwd=root, check=True, capture_output=True)
        report = ratchet_report(root, base_sha)
        self.assertEqual("HOLD_FAIL_CLOSED", report["disposition"])
        self.assertTrue(
            any(item.get("change") == "unregistered_contract_file" for item in report["blockers"])
        )

    def test_ratchet_revalidates_owner_when_proof_bundle_changes(self) -> None:
        temp, root, base_sha = git_fixture_root()
        self.addCleanup(temp.cleanup)
        proof_path = root / "penta/survival/evidence/penta.alpha.v1.json"
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        proof["verifier"]["verification_run_ref"] = "workflow:tampered-after-binding"
        write_json(proof_path, proof)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "tamper proof"], cwd=root, check=True, capture_output=True)
        report = ratchet_report(root, base_sha)
        self.assertEqual("HOLD_FAIL_CLOSED", report["disposition"])
        self.assertIn("penta/survival/evidence/penta.alpha.v1.json", report["changed_proof_paths"])
        alpha = next(
            item
            for item in report["blockers"]
            if item.get("penta_id") == "penta.alpha"
            and item.get("change") == "contract_or_registry_modified"
        )
        self.assertTrue(any("does not match executed proof bundle" in reason for reason in alpha["reasons"]))

    def test_ratchet_blocks_unreferenced_proof_bundle(self) -> None:
        temp, root, base_sha = git_fixture_root()
        self.addCleanup(temp.cleanup)
        write_json(root / "penta/survival/evidence/orphan.v1.json", PROOF_TEMPLATE)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "orphan proof"], cwd=root, check=True, capture_output=True)
        report = ratchet_report(root, base_sha)
        self.assertEqual("HOLD_FAIL_CLOSED", report["disposition"])
        self.assertTrue(any(item.get("change") == "unreferenced_proof_bundle" for item in report["blockers"]))

    def test_policy_rejects_mismatched_canonical_test_plan_digest(self) -> None:
        temp = fixture_root(include_contract=True)
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        policy_path = root / "data/penta/survival-policy.v1.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["model_off_test_plan_sha256"] = "0" * 64
        write_json(policy_path, policy)
        with self.assertRaises(PentaSurvivalError):
            coverage_report(root)

    def test_release_gate_rejects_existing_non_ancestor_candidate(self) -> None:
        temp, root, _ = git_fixture_root()
        self.addCleanup(temp.cleanup)
        empty_tree = subprocess.run(
            ["git", "mktree"],
            cwd=root,
            check=True,
            input="",
            capture_output=True,
            text=True,
        ).stdout.strip()
        foreign_sha = subprocess.run(
            ["git", "commit-tree", empty_tree],
            cwd=root,
            check=True,
            input="foreign candidate\n",
            capture_output=True,
            text=True,
        ).stdout.strip()
        report = release_gate(
            root,
            "penta.alpha",
            source_commit=foreign_sha,
            artifact_sha256="0" * 64,
        )
        self.assertEqual("HOLD_FAIL_CLOSED", report["disposition"])
        self.assertIn(
            "candidate source_commit is not an ancestor of the control-plane proof commit",
            report["reasons"],
        )

    def test_invalid_policy_cannot_weaken_model_authority_rule(self) -> None:
        policy = deepcopy(POLICY)
        policy["production_rule"]["no_model_authority"] = False
        with self.assertRaises(PentaSurvivalError):
            validate_policy(policy)

    def test_governed_merge_gate_enforces_survival_ratchet(self) -> None:
        workflow = (ROOT / ".github/workflows/governed-merge-gate.yml").read_text(encoding="utf-8")
        self.assertIn("Run deterministic Penta survival tests", workflow)
        self.assertIn("Audit complete Penta survival coverage", workflow)
        self.assertIn("Enforce deterministic Penta survival ratchet", workflow)
        self.assertIn('--base-ref "$CT_GIT_MERGE_BASE_SHA"', workflow)

    def test_exact_release_workflow_requires_candidate_ancestry(self) -> None:
        workflow = (ROOT / ".github/workflows/penta-survival-release-gate.yml").read_text(encoding="utf-8")
        self.assertIn('git merge-base --is-ancestor "${EXPECTED_SOURCE_COMMIT}" HEAD', workflow)
        self.assertIn("Proof metadata must be generated outside the immutable candidate commit.", workflow)

    def test_survival_workflows_pin_external_actions(self) -> None:
        workflows = sorted((ROOT / ".github/workflows").glob("penta-survival-*.yml"))
        self.assertEqual(2, len(workflows))
        pattern = re.compile(r"^\s*uses:\s+[^@\s]+@([0-9a-f]{40})(?:\s+#.*)?$")
        for workflow in workflows:
            uses_lines = [line for line in workflow.read_text(encoding="utf-8").splitlines() if "uses:" in line]
            self.assertTrue(uses_lines, workflow)
            for line in uses_lines:
                self.assertRegex(line, pattern, workflow)


if __name__ == "__main__":
    unittest.main()
