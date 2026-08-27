from __future__ import annotations

import base64
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from penta.organic.body import OrganicControlPlane
from penta.repository_fabric.cold import ColdSnapshotVerifier
from penta.repository_fabric.fabric import (
    ConvergenceError,
    EmergencyJournal,
    RepositoryFabric,
    canonical_sha256,
    validate_control_plane,
)
from penta.repository_fabric.github import GitHubObservationError, GitHubRepositoryObserver


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads(
    (ROOT / "developers/manifests/repository-federation-control-plane.v1.json").read_text(
        encoding="utf-8"
    )
)
ORGANIC_CONTRACT = json.loads((ROOT / "penta/organic/contract.v1.json").read_text(encoding="utf-8"))
NOW = "2026-08-27T00:00:00+00:00"


def head_for(stable_id: str) -> str:
    return hashlib.sha256(stable_id.encode()).hexdigest()[:40]


def attestation(spec: Mapping[str, Any], version: str = "1.0.0") -> dict[str, Any]:
    return {
        "schema": "ct.penta.repository-node-attestation.v1",
        "version": "1.0.0",
        "stable_id": spec["stable_id"],
        "parent_id": "ct.repo.crownthrive-support",
        "mesh_contract_version": version,
        "default_branch": "main",
        "visibility_class": (
            "restricted" if spec["expected_provider_visibility"] == "private" else "public"
        ),
        "roles": list(spec["roles"]),
        "build_profile": "unit-test",
        "authority": {
            "direct_main_write": False,
            "self_activation": False,
            "d3_human_reserved": True,
            "provider_writes_require_exact_certification": True,
        },
        "information_flow": ["afferent", "efferent", "lateral"],
    }


def observation(spec: Mapping[str, Any], *, built: bool = True) -> dict[str, Any]:
    node = attestation(spec, POLICY["version"])
    head = head_for(str(spec["stable_id"]))
    body: dict[str, Any] = {
        "schema": "ct.penta.repository-observation.v1",
        "source_adapter": "ct.adapter.github-repository-read.v1",
        "stable_id": spec["stable_id"],
        "observed_at": NOW,
        "default_branch": "main",
        "provider_visibility": spec["expected_provider_visibility"],
        "head_sha": head,
        "node_attestation": node,
        "node_attestation_sha256": canonical_sha256(node),
        "build": {
            "state": "passed" if built else "unknown",
            "head_sha": head if built else None,
            "evidence": "unit_test",
        },
    }
    if spec["stable_id"] == POLICY["release_governance"]["stable_id"]:
        required = list(POLICY["release_governance"]["required_check_contexts"])
        body["release_governance"] = {
            "state": "passed",
            "head_sha": head,
            "active_default_branch_ruleset": True,
            "applicable_ruleset_count": 1,
            "bypass_actor_count": 0,
            "required_contexts": required,
            "successful_contexts": required,
            "all_ruleset_contexts_successful": True,
        }
    body["observation_sha256"] = canonical_sha256(body)
    return body


def nodes(policy: Mapping[str, Any] = POLICY) -> list[dict[str, Any]]:
    return validate_control_plane(policy)


class AcceptedObservationVerifier:
    def __init__(self, observations: Mapping[str, Mapping[str, Any]]):
        self.accepted = {
            (stable_id, str(value["observation_sha256"]))
            for stable_id, value in observations.items()
        }

    def __call__(self, spec: Mapping[str, Any], value: Mapping[str, Any]) -> bool:
        return (str(spec["stable_id"]), str(value.get("observation_sha256"))) in self.accepted


class RepositoryFabricTests(unittest.TestCase):
    def all_observations(self, *, built: bool = True) -> dict[str, dict[str, Any]]:
        return {spec["stable_id"]: observation(spec, built=built) for spec in nodes()}

    def fabric(self, observations: Mapping[str, Mapping[str, Any]], **kwargs: Any) -> RepositoryFabric:
        return RepositoryFabric(
            POLICY,
            observation_verifier=AcceptedObservationVerifier(observations),
            **kwargs,
        )

    def test_complete_authenticated_census_is_hot_and_public_safe(self):
        observations = self.all_observations()
        result = self.fabric(observations).reconcile(observations, evaluated_at=NOW)
        self.assertEqual(result["system_state"], "hot_operational")
        self.assertEqual(result["route_counts"], {
            "hot_primary": 13,
            "cold_recovery": 0,
            "silent_emergency": 0,
        })
        self.assertEqual(result["restricted_node_count"], 10)
        restricted_json = json.dumps(result["restricted_nodes"], sort_keys=True)
        for spec in nodes():
            if spec["visibility_class"] == "restricted":
                self.assertNotIn(head_for(spec["stable_id"]), restricted_json)
        self.assertNotIn("repository", result["restricted_nodes"][0])
        body = dict(result)
        claimed = body.pop("result_sha256")
        self.assertEqual(canonical_sha256(body), claimed)

    def test_build_drift_creates_candidate_but_never_dispatch_authority(self):
        observations = self.all_observations(built=False)
        result = self.fabric(observations).reconcile(observations, evaluated_at=NOW)
        self.assertEqual(len(result["build_candidates"]), 13)
        self.assertTrue(all(item["dispatch_allowed"] is False for item in result["build_candidates"]))
        restricted_ids = {
            spec["stable_id"] for spec in nodes() if spec["visibility_class"] == "restricted"
        }
        self.assertTrue(
            all(
                item["head_sha"] == "restricted"
                for item in result["build_candidates"]
                if item["stable_id"] in restricted_ids
            )
        )

    def test_self_asserted_provider_verification_cannot_open_hot_route(self):
        observations = self.all_observations()
        for value in observations.values():
            value["provider_readback_verified"] = True
            value["observation_sha256"] = canonical_sha256(
                {key: item for key, item in value.items() if key != "observation_sha256"}
            )
        result = RepositoryFabric(POLICY).reconcile(observations, evaluated_at=NOW)
        self.assertEqual(result["route_counts"]["silent_emergency"], 13)
        self.assertTrue(
            all(
                "provider_observation_unverified" in item["reason_codes"]
                for item in result["public_nodes"] + result["restricted_nodes"]
            )
        )

    def test_tampered_authenticated_observation_fails_closed(self):
        observations = self.all_observations()
        fabric = self.fabric(observations)
        target = next(iter(observations.values()))
        target["head_sha"] = "f" * 40
        result = fabric.reconcile(observations, evaluated_at=NOW)
        held = [item for item in result["public_nodes"] if item["route"] == "silent_emergency"]
        self.assertEqual(len(held), 1)
        self.assertIn("observation_digest_invalid", held[0]["reason_codes"])

    def test_independently_verified_cold_snapshot_is_read_only(self):
        observations = self.all_observations()
        target_id = sorted(observations)[0]
        observations.pop(target_id)
        verifier = ColdSnapshotVerifier(b"c" * 32)
        cold: dict[str, Any] = {
            "schema": "ct.penta.repository-cold-snapshot.v1",
            "stable_id": target_id,
            "created_at": NOW,
            "head_sha": head_for(target_id),
            "signature_verified": True,
            "restore_mode": "read_only",
        }
        cold["signature"] = verifier.signature(cold)
        cold["snapshot_sha256"] = canonical_sha256(cold)
        result = RepositoryFabric(
            POLICY,
            observation_verifier=AcceptedObservationVerifier(observations),
            cold_snapshot_verifier=verifier,
        ).reconcile(observations, cold_snapshots={target_id: cold}, evaluated_at=NOW)
        self.assertEqual(result["system_state"], "degraded_read_only")
        self.assertEqual(result["route_counts"]["cold_recovery"], 1)
        selected = next(
            item
            for item in result["public_nodes"] + result["restricted_nodes"]
            if item["stable_id"] == target_id
        )
        self.assertEqual(selected["build_state"], "not_executable_from_cold_awareness")

    def test_self_asserted_cold_signature_cannot_open_recovery_route(self):
        target = nodes()[0]
        cold: dict[str, Any] = {
            "schema": "ct.penta.repository-cold-snapshot.v1",
            "stable_id": target["stable_id"],
            "created_at": NOW,
            "head_sha": head_for(target["stable_id"]),
            "signature_verified": True,
            "signature": "hmac-sha256:" + "1" * 64,
        }
        cold["snapshot_sha256"] = canonical_sha256(cold)
        result = RepositoryFabric(POLICY).reconcile(
            {}, cold_snapshots={target["stable_id"]: cold}, evaluated_at=NOW
        )
        self.assertEqual(result["route_counts"]["cold_recovery"], 0)
        self.assertEqual(result["route_counts"]["silent_emergency"], 13)

    def test_emergency_journal_is_durable_and_tamper_evident(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "emergency.jsonl"
            first = RepositoryFabric(POLICY, emergency_journal=path)
            result = first.reconcile({}, evaluated_at=NOW)
            self.assertEqual(result["emergency"]["queued_count"], 13)
            second = EmergencyJournal(path)
            self.assertTrue(second.verify())
            self.assertEqual(len(second.events), 13)
            path.write_text(path.read_text().replace("cold_snapshot_missing", "fabricated"), encoding="utf-8")
            with self.assertRaisesRegex(ConvergenceError, "integrity"):
                EmergencyJournal(path)

    def test_emergency_journal_rejects_symlink_redirection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.jsonl"
            outside.write_text("safe\n", encoding="utf-8")
            journal = root / "emergency.jsonl"
            journal.symlink_to(outside)
            with self.assertRaisesRegex(ConvergenceError, "symlink"):
                EmergencyJournal(journal)
            self.assertEqual(outside.read_text(encoding="utf-8"), "safe\n")

            journal.unlink()
            fabric = RepositoryFabric(POLICY, emergency_journal=journal)
            journal.symlink_to(outside)
            with self.assertRaisesRegex(ConvergenceError, "symlink"):
                fabric.reconcile({}, evaluated_at=NOW)
            self.assertEqual(outside.read_text(encoding="utf-8"), "safe\n")

    def test_private_coordinate_in_public_policy_is_rejected(self):
        broken = copy.deepcopy(POLICY)
        broken["inventory"]["restricted_nodes"][0]["repository"] = "owner/private-name"
        with self.assertRaisesRegex(ConvergenceError, "restricted node"):
            validate_control_plane(broken)

    def test_private_visibility_cannot_be_declared_in_public_inventory(self):
        broken = copy.deepcopy(POLICY)
        broken["inventory"]["public_nodes"][0]["expected_provider_visibility"] = "private"
        with self.assertRaisesRegex(ConvergenceError, "restricted runtime bindings"):
            validate_control_plane(broken)

    def test_hidden_coordinate_fields_cannot_bypass_public_policy_shape(self):
        top_level = copy.deepcopy(POLICY)
        top_level["private_repository_coordinates"] = "must-not-appear"
        with self.assertRaisesRegex(ConvergenceError, "fields drifted"):
            validate_control_plane(top_level)

        nested = copy.deepcopy(POLICY)
        nested["failover"]["hot_primary"]["repository"] = "must-not-appear"
        with self.assertRaisesRegex(ConvergenceError, "route fields drifted"):
            validate_control_plane(nested)

    def test_unknown_cold_snapshot_identity_is_rejected(self):
        with self.assertRaisesRegex(ConvergenceError, "cold snapshots contain unknown"):
            RepositoryFabric(POLICY).reconcile(
                {}, cold_snapshots={"ct.repo.unknown": {}}, evaluated_at=NOW
            )

    def test_release_ruleset_bypass_forces_silent_emergency(self):
        observations = self.all_observations()
        support = observations[POLICY["canonical_hub_id"]]
        support["release_governance"]["bypass_actor_count"] = 1
        support["release_governance"]["state"] = "hold"
        support["observation_sha256"] = canonical_sha256(
            {key: value for key, value in support.items() if key != "observation_sha256"}
        )
        result = self.fabric(observations).reconcile(observations, evaluated_at=NOW)
        held = next(
            item
            for item in result["public_nodes"]
            if item["stable_id"] == POLICY["canonical_hub_id"]
        )
        self.assertEqual(held["route"], "silent_emergency")
        self.assertIn("release_ruleset_bypass_present", held["reason_codes"])

    def test_cancelled_exact_head_gate_forces_silent_emergency(self):
        observations = self.all_observations()
        support = observations[POLICY["canonical_hub_id"]]
        support["release_governance"]["successful_contexts"] = []
        support["release_governance"]["all_ruleset_contexts_successful"] = False
        support["release_governance"]["state"] = "hold"
        support["observation_sha256"] = canonical_sha256(
            {key: value for key, value in support.items() if key != "observation_sha256"}
        )
        result = self.fabric(observations).reconcile(observations, evaluated_at=NOW)
        held = next(
            item
            for item in result["public_nodes"]
            if item["stable_id"] == POLICY["canonical_hub_id"]
        )
        self.assertEqual(held["route"], "silent_emergency")
        self.assertIn("release_exact_head_gate_unsuccessful", held["reason_codes"])

    def test_unknown_node_and_invalid_time_fail_closed(self):
        with self.assertRaisesRegex(ConvergenceError, "unknown nodes"):
            RepositoryFabric(POLICY).reconcile({"ct.repo.unknown": {}}, evaluated_at=NOW)
        observations = self.all_observations()
        observations[next(iter(observations))]["observed_at"] = "not-a-time"
        with self.assertRaisesRegex(ConvergenceError, "ISO-8601"):
            self.fabric(observations).reconcile(observations, evaluated_at=NOW)

    def test_organic_projection_verifies_result_and_routes_all_nodes(self):
        observations = self.all_observations()
        fabric = self.fabric(observations)
        result = fabric.reconcile(observations, evaluated_at=NOW)
        organic = OrganicControlPlane(ORGANIC_CONTRACT)
        projected = fabric.project_to_organic(
            result,
            organic,
            identity={
                "vault_id": "vault:ct.identity.repository-fabric-unit",
                "public_key_fingerprint": "sha256:" + "1" * 64,
                "key_algorithm": "unit-test",
            },
            observed_at=NOW,
        )
        self.assertEqual(projected["organic_snapshot"]["event_count"], 13)
        self.assertTrue(projected["organic_snapshot"]["spine_integrity"])
        tampered = copy.deepcopy(result)
        tampered["system_state"] = "fabricated"
        with self.assertRaisesRegex(ConvergenceError, "integrity"):
            fabric.project_to_organic(
                tampered,
                OrganicControlPlane(ORGANIC_CONTRACT),
                identity={
                    "vault_id": "vault:ct.identity.repository-fabric-unit",
                    "public_key_fingerprint": "sha256:" + "1" * 64,
                },
                observed_at=NOW,
            )


class GitHubObserverTests(unittest.TestCase):
    @staticmethod
    def restricted_bindings() -> dict[str, str]:
        return {
            spec["stable_id"]: "restricted-owner/" + spec["stable_id"].replace("ct.repo.", "")
            for spec in nodes()
            if spec["visibility_class"] == "restricted"
        }

    def test_authenticated_adapter_binds_exact_provider_readback(self):
        policy = copy.deepcopy(POLICY)
        policy["inventory"]["public_nodes"] = [policy["inventory"]["public_nodes"][0]]
        policy["inventory"]["restricted_nodes"] = []
        policy["inventory"]["expected_physical_repository_count"] = 1
        spec = validate_control_plane(policy)[0]
        node = attestation(spec, policy["version"])
        head = head_for(spec["stable_id"])

        def transport(path: str, stable_id: str) -> Any:
            self.assertEqual(stable_id, spec["stable_id"])
            if "/git/ref/heads/" in path:
                return {"object": {"sha": head}}
            if "/contents/" in path:
                return {
                    "type": "file",
                    "encoding": "base64",
                    "content": base64.b64encode(json.dumps(node).encode()).decode(),
                }
            if "/actions/runs?" in path:
                return {
                    "workflow_runs": [{
                        "head_sha": head,
                        "head_branch": "main",
                        "status": "completed",
                        "conclusion": "success",
                        "event": "push",
                        "path": ".github/workflows/penta-repository-convergence.yml@main",
                    }]
                }
            if path.endswith("/rulesets?per_page=100&page=1"):
                return [{"id": 123}]
            if path.endswith("/rulesets/123"):
                return {
                    "id": 123,
                    "enforcement": "active",
                    "target": "branch",
                    "conditions": {
                        "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
                    },
                    "bypass_actors": [],
                    "rules": [{
                        "type": "required_status_checks",
                        "parameters": {
                            "required_status_checks": [{
                                "context": "CrownThrive governed merge gate"
                            }]
                        },
                    }],
                }
            if "/check-runs?" in path:
                return {
                    "check_runs": [{
                        "id": 9001,
                        "name": "CrownThrive governed merge gate",
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"id": 15368},
                    }]
                }
            if "/status?" in path:
                return {"statuses": []}
            return {
                "full_name": spec["repository"],
                "default_branch": "main",
                "visibility": "public",
                "archived": False,
                "disabled": False,
            }

        observer = GitHubRepositoryObserver(
            policy,
            token="unit-test-token",
            restricted_bindings={},
            transport=transport,
        )
        observations, errors = observer.collect(observed_at=NOW)
        self.assertEqual(errors, {})
        self.assertNotIn(spec["repository"], json.dumps(observations))
        result = RepositoryFabric(
            policy, observation_verifier=observer.verify_observation
        ).reconcile(observations, evaluated_at=NOW)
        self.assertEqual(result["system_state"], "hot_operational")

    def test_production_transport_rejects_non_github_credential_destination(self):
        with self.assertRaisesRegex(GitHubObservationError, "not allowlisted"):
            GitHubRepositoryObserver(
                POLICY,
                token="unit-test-token",
                restricted_bindings=self.restricted_bindings(),
                api_base="https://example.invalid",
            )

    def test_required_check_cannot_be_satisfied_by_wrong_github_app(self):
        def transport(path: str, stable_id: str) -> Any:
            if path.endswith("/rulesets?per_page=100&page=1"):
                return [{"id": 123}]
            if path.endswith("/rulesets/123"):
                return {
                    "id": 123,
                    "enforcement": "active",
                    "target": "branch",
                    "conditions": {
                        "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
                    },
                    "bypass_actors": [],
                    "rules": [{
                        "type": "required_status_checks",
                        "parameters": {"required_status_checks": [{
                            "context": "CrownThrive governed merge gate",
                            "integration_id": 111,
                        }]},
                    }],
                }
            if "/check-runs?" in path:
                return {"check_runs": [{
                    "id": 99,
                    "name": "CrownThrive governed merge gate",
                    "status": "completed",
                    "conclusion": "success",
                    "app": {"id": 222},
                }]}
            if "/status?" in path:
                return {"statuses": []}
            raise AssertionError(path)

        observer = GitHubRepositoryObserver(
            POLICY,
            token="unit-test-token",
            restricted_bindings=self.restricted_bindings(),
            transport=transport,
        )
        result = observer._release_governance_readback(
            "/repos/crownthrive1/CrownThrive-Support",
            "a" * 40,
            "main",
            POLICY["canonical_hub_id"],
        )
        self.assertEqual(result["state"], "hold")
        self.assertEqual(result["successful_contexts"], [])

    def test_ruleset_excluding_default_branch_cannot_open_release_gate(self):
        self.assertFalse(
            GitHubRepositoryObserver._ruleset_applies_to_default_branch(
                {
                    "enforcement": "active",
                    "target": "branch",
                    "conditions": {
                        "ref_name": {
                            "include": ["~ALL"],
                            "exclude": ["refs/heads/*"],
                        }
                    },
                },
                "main",
            )
        )


class CandidateSyncDispositionTests(unittest.TestCase):
    def test_untracked_provider_write_pack_remains_held_and_absent(self):
        status = json.loads(
            (ROOT / "developers/manifests/repository-convergence-status.v1.json").read_text(
                encoding="utf-8"
            )
        )
        disposition = status["candidate_sync_disposition"]
        self.assertEqual(disposition["state"], "HOLD_SUPERSEDED_NOT_INTEGRATED")
        self.assertFalse(disposition["source_code_copied_into_canonical"])
        self.assertFalse(disposition["provider_effect_performed"])
        self.assertEqual(len(disposition["observed_candidate_digests"]), 5)
        self.assertFalse(
            disposition["captured_adversarial_evidence"]["tests_cover_all_blocking_findings"]
        )
        for path in disposition["observed_candidate_digests"]:
            self.assertFalse((ROOT / path).exists(), path)


if __name__ == "__main__":
    unittest.main()
