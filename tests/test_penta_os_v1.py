import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load_module("penta_os_v15_builder", ROOT / "scripts/build_penta_os_v1.py")
runtime_module = load_module("penta_os_v15_runtime", ROOT / "runtime/penta_os_v1.py")


class PentaOSV15Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = builder.build_registry(ROOT)
        cls.runtime = runtime_module.PentaOSV1(ROOT, cls.registry)

    def request(self, machine_key="penta.scribe", operation="render_glossary", **changes):
        values = {
            "machine_key": machine_key,
            "operation": operation,
            "authority_trace": "A1:test-authority",
            "idempotency_key": "test-001",
            "payload": {"scope": "public-safe"},
        }
        values.update(changes)
        return runtime_module.DispatchRequest(**values)

    def test_release_and_schema_version_are_separate(self):
        self.assertEqual(self.registry["version"], "1.5.0")
        self.assertEqual(self.registry["schema_version"], "1.1.0")
        self.assertEqual(self.registry["production_certification"], "HOLD")
        self.assertEqual(
            set(self.registry["operations"]),
            {"describe", "status", "readiness", "validate", "verify", "plan", "dispatch"},
        )

    def test_machine_key_grammar_accepts_hyphens_and_rejects_empty_segments(self):
        self.assertTrue(builder.MACHINE_KEY_PATTERN.fullmatch("penta.evi-builder"))
        invalid = {
            "machine_key": "penta.bad..key",
            "canonical_name": "PentaBadKey",
            "role": "Invalid key fixture for a fail-closed builder test.",
            "axis": "truth",
            "maturity": "specified",
            "risk_ceiling": "D0",
            "source": "test:invalid-machine-key",
            "source_kind": "governed_discovery",
        }
        with self.assertRaisesRegex(builder.PentaOSBuildError, "invalid machine key"):
            builder.merge_rows([invalid], [])

    def test_complete_member_census_preserves_maturity(self):
        checked = json.loads((ROOT / "data/penta/os-v1.registry.json").read_text(encoding="utf-8"))
        rows = self.registry["systems"]
        self.assertEqual(len(rows), checked["counts"]["total"])
        self.assertEqual(len(rows), len({row["machine_key"] for row in rows}))
        self.assertEqual(len(rows), len({row["canonical_name"] for row in rows}))
        self.assertEqual(self.registry["counts"], checked["counts"])
        census_member = self.runtime.resolve("penta.census")
        self.assertEqual(census_member["maturity"], "implemented")
        self.assertFalse(census_member["execution_eligible_by_registry"])

    def test_dependency_census_is_exact(self):
        checked = json.loads((ROOT / "data/penta/os-v1.registry.json").read_text(encoding="utf-8"))
        self.assertEqual(self.registry["counts"], checked["counts"])
        self.assertEqual(self.registry["dependency_graph"], checked["dependency_graph"])
        self.assertEqual(self.registry["counts"]["unresolved_penta_dependencies"], 0)
        self.assertEqual(self.registry["dependency_graph"]["external_refs"], ["chlom", "cie", "crownlytics", "crownpulse"])

    def test_strict_readiness_partition_is_exact_and_diagnostic(self):
        checked = json.loads((ROOT / "data/penta/os-v1.registry.json").read_text(encoding="utf-8"))
        expected = checked["dependency_graph"]["readiness_partition"]
        self.assertEqual(self.registry["dependency_graph"]["readiness_partition"], expected)
        self.assertTrue(self.registry["dependency_graph"]["strict_readiness_is_diagnostic"])
        self.assertEqual(sum(expected.values()), checked["counts"]["total"])

    def test_transitive_closure_and_scc_are_deterministic(self):
        first = builder.build_registry(ROOT)
        second = builder.build_registry(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(first["dependency_graph_sha256"], second["dependency_graph_sha256"])
        fabric = self.runtime.readiness("penta.fabric")
        self.assertEqual(fabric["strict_readiness_state"], "HOLD_UNCLASSIFIED_DEPENDENCY_CYCLE")
        self.assertIn("penta.mesh", fabric["direct_internal"])
        self.assertEqual(fabric["cycle"]["members"], ["penta.fabric", "penta.mesh"])
        self.assertEqual(len(fabric["cycle"]["cycle_sha256"]), 64)

    def test_external_dependencies_are_never_reported_as_verified(self):
        scribe = self.runtime.readiness("penta.scribe")
        self.assertEqual(scribe["direct_external"], ["chlom", "cie"])
        self.assertEqual(scribe["strict_readiness_state"], "HOLD_EXTERNAL_DEPENDENCY_UNBOUND")
        self.assertFalse(scribe["provider_effect_verified"])
        self.assertFalse(scribe["production_certification_granted"])

    def test_registry_digests_bind_full_contract(self):
        self.assertEqual(self.registry["systems_sha256"], runtime_module.sha256(self.registry["systems"]))
        self.assertEqual(self.registry["dependency_graph_sha256"], runtime_module.sha256(self.registry["dependency_graph"]))
        self.assertEqual(self.registry["operation_policy_sha256"], runtime_module.sha256(self.registry["operation_policy"]))
        body = {key: value for key, value in self.registry.items() if key != "registry_sha256"}
        self.assertEqual(self.registry["registry_sha256"], runtime_module.sha256(body))
        self.assertIn("data/penta/family.registry.json", self.registry["source_digests_sha256"])
        self.assertIn("data/penta/os-v1.operation-policies.json", self.registry["source_digests_sha256"])

    def test_full_registry_digest_detects_alias_tampering(self):
        fixture = copy.deepcopy(self.registry)
        fixture["aliases"][0]["reason"] += " tampered"
        with self.assertRaisesRegex(runtime_module.PentaOSV1Error, "full registry digest"):
            runtime_module.PentaOSV1(ROOT, fixture)

    def test_unsafe_source_path_fails_closed(self):
        fixture = copy.deepcopy(self.registry)
        fixture["source_digests_sha256"]["../escape.json"] = "0" * 64
        fixture["registry_sha256"] = runtime_module.sha256({key: value for key, value in fixture.items() if key != "registry_sha256"})
        with self.assertRaisesRegex(runtime_module.PentaOSV1Error, "unsafe registry source path"):
            runtime_module.PentaOSV1(ROOT, fixture)

    def test_describe_status_and_alias_resolution(self):
        self.assertEqual(self.runtime.resolve("PentaMailer")["machine_key"], "penta.mail")
        self.assertEqual(self.runtime.resolve("PentaLoadBalancer")["machine_key"], "penta.balancer")
        self.assertEqual(self.runtime.resolve("Penta Evidence Builder")["machine_key"], "penta.evi-builder")
        self.assertEqual(self.runtime.resolve("Penta Immune System")["machine_key"], "penta.immune")
        self.assertEqual(self.runtime.resolve("Penta Gate")["machine_key"], "penta.gate")
        self.assertEqual(self.runtime.resolve("Penta Heal")["machine_key"], "penta.heal")
        description = self.runtime.describe("PentaMail")
        self.assertEqual(description["member"]["machine_key"], "penta.mail")
        self.assertFalse(description["side_effect_performed"])
        status = self.runtime.status("penta.mail")
        self.assertEqual(status["version"], "1.5.0")
        self.assertIn("registry_sha256", status)

    def test_merge_precedence_preserves_governed_identity_semantics(self):
        authority = self.runtime.resolve("penta.authority")
        self.assertEqual((authority["kind"], authority["axis"], authority["risk_ceiling"]), ("layer", "authority", "D3"))
        self.assertIn("policy", authority["role"].casefold())
        context = self.runtime.resolve("penta.context")
        self.assertEqual((context["axis"], context["maturity"], context["risk_ceiling"]), ("truth", "implemented", "D2"))
        self.assertIn("operational-memory", context["role"])
        self.assertEqual(self.runtime.resolve("penta.health")["axis"], "truth")
        self.assertEqual(self.runtime.resolve("penta.results")["risk_ceiling"], "D2")
        self.assertEqual(self.runtime.resolve("penta.evi-builder")["axis"], "truth")
        self.assertEqual(self.runtime.resolve("penta.immune")["axis"], "continuity")
        self.assertEqual((self.runtime.resolve("penta.gate")["axis"], self.runtime.resolve("penta.gate")["maturity"]), ("truth", "implemented"))
        self.assertEqual((self.runtime.resolve("penta.heal")["axis"], self.runtime.resolve("penta.heal")["maturity"]), ("continuity", "implemented"))
        for key in ("penta.balancer", "penta.body", "penta.brain", "penta.costs", "penta.load", "penta.nerves", "penta.spine"):
            self.assertEqual(self.runtime.resolve(key)["maturity"], "implemented")
            self.assertIn("penta/organic/body.py", self.runtime.resolve(key)["evidence_paths"])
        self.assertEqual(self.runtime.resolve("penta.health")["maturity"], "specified")

    def test_unknown_and_unpromoted_members_fail_closed(self):
        unknown = self.runtime.gate_dispatch(self.request("penta.unknown", "inspect", authority_trace="A0:test-authority"))
        self.assertFalse(unknown["eligible"])
        specified = self.runtime.gate_dispatch(self.request("PentaRunners", "inspect", authority_trace="A0:test-authority"))
        self.assertFalse(specified["eligible"])
        self.assertIn("not execution eligible", " ".join(specified["reasons"]))
        for member in ("penta.gate", "penta.heal"):
            implemented = self.runtime.gate_dispatch(self.request(member, "inspect", authority_trace="A0:test-authority"))
            self.assertFalse(implemented["eligible"])
            self.assertIn("not execution eligible", " ".join(implemented["reasons"]))

    def test_unknown_operation_fails_closed_even_for_production_member(self):
        gate = self.runtime.gate_dispatch(self.request(operation="run"))
        self.assertFalse(gate["eligible"])
        self.assertIn("HOLD_UNKNOWN_OPERATION", " ".join(gate["reasons"]))

    def test_registry_derived_local_operation_can_emit_handoff(self):
        request = self.request()
        gate = self.runtime.gate_dispatch(request)
        self.assertTrue(gate["eligible"])
        self.assertEqual(gate["operation_policy"]["effect"], "local_compute")
        envelope = self.runtime.dispatch_envelope(request)
        self.assertEqual(envelope["disposition"], "READY_FOR_SPECIALIZED_EXECUTOR")
        self.assertFalse(envelope["side_effect_performed"])
        self.assertEqual(envelope["request_sha256"], runtime_module.sha256(envelope["request"]))

    def test_provider_write_cannot_be_hidden_from_policy(self):
        gate = self.runtime.gate_dispatch(self.request(
            operation="publish",
            authority_trace="A2:test-authority",
            provider_write=False,
        ))
        reasons = " ".join(gate["reasons"])
        self.assertFalse(gate["eligible"])
        self.assertIn("provider_write=true", reasons)
        self.assertIn("provider_binding", reasons)
        self.assertIn("readback_contract", reasons)

    def test_dependency_ready_policy_holds_current_bootstrap(self):
        gate = self.runtime.gate_dispatch(self.request(
            operation="publish",
            authority_trace="A2:test-authority",
            provider_write=True,
            provider_binding="provider:docs:v1",
            readback_contract="readback:docs:v1",
        ))
        self.assertFalse(gate["eligible"])
        self.assertIn("strict dependency readiness", " ".join(gate["reasons"]))

    def test_d3_policy_requires_human_approval(self):
        gate = self.runtime.gate_dispatch(self.request(
            operation="delete",
            authority_trace="A3:test-authority",
        ))
        self.assertFalse(gate["eligible"])
        self.assertIn("human_approval_ref", " ".join(gate["reasons"]))

    def test_operation_risk_cannot_exceed_member_ceiling(self):
        gate = self.runtime.gate_dispatch(self.request(
            machine_key="penta.beata",
            operation="delete",
            authority_trace="A3:test-authority",
            human_approval_ref="human:test-founder",
        ))
        self.assertFalse(gate["eligible"])
        self.assertIn("operation risk D3 exceeds member ceiling D0", " ".join(gate["reasons"]))

    def test_strict_request_parsing_rejects_bad_types_unknown_fields_and_nan(self):
        with self.assertRaisesRegex(runtime_module.PentaOSV1Error, "unknown request fields"):
            runtime_module.request_from_mapping({"machine_key": "penta.scribe", "operation": "inspect", "secret": "x"})
        bad = runtime_module.DispatchRequest("penta.scribe", "inspect", 7, "test-001")
        self.assertFalse(self.runtime.gate_dispatch(bad)["eligible"])
        bad_payload = runtime_module.DispatchRequest("penta.scribe", "inspect", "A0:test-authority", "test-001", payload=["not", "an", "object"])
        self.assertFalse(self.runtime.gate_dispatch(bad_payload)["eligible"])
        with self.assertRaisesRegex(runtime_module.PentaOSV1Error, "canonical JSON"):
            self.runtime.plan(self.request(payload={"value": math.nan}))
        malformed_plan = self.runtime.plan(self.request())
        malformed_plan["request"]["payload"] = {"value": math.nan}
        self.assertFalse(self.runtime.verify_plan(malformed_plan)["valid"])

    def test_plan_binds_entire_request_and_verifies(self):
        first = self.runtime.plan(self.request(payload={"value": 1}))
        second = self.runtime.plan(self.request(payload={"value": 2}))
        self.assertNotEqual(first["request_sha256"], second["request_sha256"])
        self.assertNotEqual(first["plan_sha256"], second["plan_sha256"])
        self.assertTrue(self.runtime.verify_plan(first)["valid"])
        tampered = copy.deepcopy(first)
        tampered["request"]["payload"]["value"] = 999
        self.assertFalse(self.runtime.verify_plan(tampered)["valid"])

    def test_unknown_member_plan_is_a_deterministic_hold_not_an_exception(self):
        request = self.request("penta.unknown", "inspect", authority_trace="A0:test-authority")
        plan = self.runtime.plan(request)
        self.assertFalse(plan["gate"]["eligible"])
        self.assertIsNone(plan["dependency_closure"])
        self.assertTrue(self.runtime.verify_plan(plan)["valid"])

    def test_batch_plan_is_order_independent_and_verifiable(self):
        first_request = self.request(idempotency_key="batch-001")
        second_request = self.request("penta.error", "inspect", authority_trace="A0:test-authority", idempotency_key="batch-002")
        one = self.runtime.batch_plan([first_request, second_request])
        two = self.runtime.batch_plan([second_request, first_request])
        self.assertEqual(one, two)
        self.assertTrue(one["eligible"])
        self.assertTrue(one["all_or_none_gate"])
        self.assertFalse(one["atomic_execution_performed"])
        self.assertTrue(self.runtime.verify_batch_plan(one)["valid"])
        tampered = copy.deepcopy(one)
        tampered["items"][0]["request"]["payload"] = {"tampered": True}
        self.assertFalse(self.runtime.verify_batch_plan(tampered)["valid"])

    def test_batch_duplicates_hold_and_cycles_remain_grouped(self):
        duplicate_one = self.request(idempotency_key="duplicate-001")
        duplicate_two = self.request("penta.error", "inspect", authority_trace="A0:test-authority", idempotency_key="duplicate-001")
        held = self.runtime.batch_plan([duplicate_one, duplicate_two])
        self.assertFalse(held["eligible"])
        self.assertIn("duplicate batch idempotency", " ".join(held["reasons"]))
        cyclic = self.runtime.batch_plan([
            self.request("penta.fabric", "inspect", authority_trace="A0:test-authority", idempotency_key="fabric-001"),
            self.request("penta.mesh", "inspect", authority_trace="A0:test-authority", idempotency_key="mesh-001"),
        ])
        cycle_ids = {item["cycle_id"] for stage in cyclic["stages"] for item in stage["items"]}
        self.assertEqual(len(cycle_ids), 1)
        self.assertNotIn(None, cycle_ids)

    def test_receipt_is_deterministic_and_tamper_evident(self):
        first = self.runtime.verification_receipt()
        second = self.runtime.verification_receipt()
        self.assertEqual(first, second)
        self.assertEqual(first["disposition"], "PASS_REPOSITORY_VERIFIED")
        self.assertTrue(self.runtime.verify_receipt(first)["valid"])
        member = self.runtime.verification_receipt("penta.scribe")
        self.assertEqual(member["disposition"], "HOLD_RECORDED")
        self.assertTrue(self.runtime.verify_receipt(member)["valid"])
        tampered = copy.deepcopy(first)
        tampered["production_certification_granted"] = True
        self.assertFalse(self.runtime.verify_receipt(tampered)["valid"])

    def test_stale_but_rehashed_receipt_fails_current_registry_binding(self):
        receipt = self.runtime.verification_receipt()
        body = {key: value for key, value in receipt.items() if key not in {"receipt_id", "receipt_sha256"}}
        body["registry_sha256"] = "0" * 64
        body["receipt_id"] = "pvr-" + runtime_module.sha256(body)[:24]
        stale = {**body, "receipt_sha256": runtime_module.sha256(body)}
        self.assertFalse(self.runtime.verify_receipt(stale)["valid"])

    def test_json_schema_accepts_generated_registry_when_jsonschema_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((ROOT / "schemas/penta/os-v1-registry.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(self.registry)

        plan = self.runtime.plan(self.request())
        batch = self.runtime.batch_plan([self.request(idempotency_key="schema-batch-001")])
        receipt = self.runtime.verification_receipt()
        for filename, value in (
            ("os-v1-plan.schema.json", plan),
            ("os-v1-batch-plan.schema.json", batch),
            ("os-v1-verification-receipt.schema.json", receipt),
        ):
            output_schema = json.loads((ROOT / "schemas/penta" / filename).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(output_schema).validate(value)


if __name__ == "__main__":
    unittest.main()
