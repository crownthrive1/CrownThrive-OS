"""Regression tests for the executable Penta Family member control plane."""
from __future__ import annotations
import copy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.penta_exec import PentaExecutionError, family_list, family_validate, invoke_member, load_adapter_registry, member_status, validate_adapter_registry  # noqa: E402
from runtime.penta_family import load_family  # noqa: E402
from runtime.penta_compliance_license import verify_receipt  # noqa: E402


def expect_error(fn, contains: str) -> None:
    try: fn()
    except PentaExecutionError as exc: assert contains in str(exc), (contains, str(exc))
    else: raise AssertionError(f"expected PentaExecutionError containing {contains!r}")


def test_every_registered_member_is_control_plane_addressable() -> None:
    _, snapshot = load_family(ROOT); result = family_list(snapshot)
    assert result["disposition"] == "completed_read_only" and result["details"]["member_count"] == snapshot["member_count"]
    assert {row["machine_key"] for row in result["details"]["members"]} == set(snapshot["members"])


def test_evidence_promoted_mail_has_real_status_and_gate() -> None:
    _, snapshot = load_family(ROOT); result = member_status(snapshot, "penta.mail")
    assert result["details"]["maturity"] == "production"
    assert result["details"]["execution_gate"]["eligible"] is True
    assert result["details"]["maturity_promotion"]["authority_ref"].startswith("PR-511/")
    assert result["details"]["portal_route"] == "/penta/mail"


def test_execution_adapter_registry_is_static_and_fail_closed() -> None:
    registry = load_adapter_registry(ROOT)
    assert registry["fail_closed"] is True and registry["version"] == "1.4.0" and len(registry["adapters"]) == 21
    assert all(adapter["provider_effect"] is False for adapter in registry["adapters"])


def test_provider_effect_builtin_adapter_is_rejected() -> None:
    broken = copy.deepcopy(load_adapter_registry(ROOT)); broken["adapters"][0]["provider_effect"] = True
    expect_error(lambda: validate_adapter_registry(broken), "does not permit provider-effect handlers")


def test_unknown_handler_is_rejected() -> None:
    broken = copy.deepcopy(load_adapter_registry(ROOT)); broken["adapters"][0]["handler"] = "shell"
    expect_error(lambda: validate_adapter_registry(broken), "unregistered builtin handler")


def test_family_execution_contract_covers_all_production_members() -> None:
    registry, snapshot = load_family(ROOT); result = family_validate(ROOT, registry, snapshot)
    assert result["disposition"] == "pass", result
    assert result["details"]["blockers"] == [] and result["details"]["adapter_count"] == 21 and result["details"]["promotion_count"] == 5
    coverage = result["details"]["execution_adapter_coverage"]
    assert coverage == {"eligible_member_count": 21, "eligible_members_with_adapter": 21, "missing_adapter_members": [], "complete": True}


def test_beata_heartbeat_and_mesh_routing_execute() -> None:
    heartbeat = invoke_member(ROOT, source_member="penta.status", target_member="penta.beata", operation="heartbeat", evidence_refs=["test:beata"], risk_class="D0")
    assert heartbeat["disposition"] == "completed" and heartbeat["details"]["result"]["machine_key"] == "penta.beata"
    route = invoke_member(ROOT, source_member="penta.status", target_member="penta.mesh", operation="route_check", evidence_refs=["test:mesh"], payload={"candidate_target": "penta.mail"}, risk_class="D0")
    assert route["disposition"] == "completed" and route["details"]["result"]["maturity"] == "production" and route["details"]["result"]["execution_eligible"] is True


def test_observability_adapters_execute_and_redact() -> None:
    error = invoke_member(ROOT, source_member="penta.status", target_member="penta.error", operation="normalize", evidence_refs=["test:error"], payload={"message": "internal", "context": {"api_key": "secret", "safe": "ok"}}, risk_class="D0")
    assert error["details"]["result"]["context"]["api_key"] == "[REDACTED]"
    log = invoke_member(ROOT, source_member="penta.status", target_member="penta.logger", operation="emit", evidence_refs=["test:logger"], payload={"message": "live", "context": {"token": "do-not-leak"}}, risk_class="D0")
    assert log["details"]["result"]["record"]["context"]["token"] == "[REDACTED]"
    trace = invoke_member(ROOT, source_member="penta.status", target_member="penta.trace", operation="new_context", evidence_refs=["test:trace"], risk_class="D0")
    assert len(trace["details"]["result"]["trace_id"]) == 32
    metric = invoke_member(ROOT, source_member="penta.status", target_member="penta.metric", operation="snapshot", evidence_refs=["test:metric"], payload={"counters": {"penta.exec.calls": 2}}, risk_class="D0")
    assert metric["details"]["result"]["counters"]["penta.exec.calls"] == 2.0


def test_heartbeat_and_od_see_all_production_members() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.heartbeat", operation="control_plane_probe", evidence_refs=["test:heartbeat"], risk_class="D0")
    probe = result["details"]["result"]
    assert result["disposition"] == "completed" and probe["production_member_count"] == 21
    assert all(row["adapter_bound"] for row in probe["members"])
    assert isinstance(probe["healthy"], bool)
    od = invoke_member(ROOT, source_member="penta.status", target_member="penta.od", operation="readiness_assess", evidence_refs=["test:od"], payload={"candidate_target": "penta.mail"}, risk_class="D0")
    readiness = od["details"]["result"]
    assert readiness["ready_for_bounded_dispatch"] is True and readiness["adapter_operations"] == ["production_status"] and readiness["authority_expanded"] is False


def _compliance_payload() -> dict:
    return {"obligations": [{"obligation_id": "obl.test", "title": "Test adopted obligation", "source_ref": "test:source", "owner_ref": "test:owner", "status": "active", "jurisdictions": ["US"], "scopes": ["license"], "evidence_requirements": ["ctrl.test"], "controls": [{"control_id": "ctrl.test", "requirement": "evidence exists"}], "effective_from": "2026-01-01", "source_sha256": "a" * 64}], "jurisdictions": ["US"], "scopes": ["license"], "evidence_index": {"ctrl.test": ["evidence:test"]}, "as_of": "2026-08-26"}


def test_compliance_and_license_readiness_execute_without_binding_action() -> None:
    compliance = invoke_member(ROOT, source_member="penta.status", target_member="penta.compliance", operation="evaluate", evidence_refs=["test:compliance"], payload=_compliance_payload(), risk_class="D0")["details"]["result"]
    assert compliance["disposition"] == "PASS_EVIDENCE_SATISFIED" and verify_receipt(compliance)
    asset = {"asset_id": "asset.test", "version": "1.0.0", "content_sha256": "b" * 64, "title": "Test Asset", "owner_ref": "owner:test", "status": "active", "rights_control_refs": ["chlom:rights:test"], "allowed_rights": ["display"], "prohibited_rights": [], "territories": ["US"], "media": ["digital"]}
    request = {"request_id": "req.test", "asset_id": "asset.test", "asset_version": "1.0.0", "asset_sha256": "b" * 64, "licensee_ref": "licensee:test", "use_case": "test", "lane": "self_serve", "risk_class": "D1", "valid_from": "2026-08-26", "valid_until": "2027-08-26", "template_ref": "template:test", "acceptance_ref": "accept:test", "idempotency_key": "idem:test", "requested_rights": ["display"], "territories": ["US"], "media": ["digital"], "authority_trace": {"chlom_ref": "chlom:test", "accountable_owner": "owner:test"}, "compliance_receipt": compliance, "commercial_terms_ref": "terms:test", "provider_effect": False}
    readiness = invoke_member(ROOT, source_member="penta.status", target_member="penta.license", operation="readiness", evidence_refs=["test:license"], payload={"asset": asset, "request": request}, risk_class="D0")["details"]["result"]
    assert readiness["binding_action_performed"] is False and readiness["adapter_boundary"] == "readiness_only_no_license_grant_issued" and verify_receipt(readiness["decision"])


def test_scribe_and_marketer_real_isolated_cycles_execute() -> None:
    scribe = invoke_member(ROOT, source_member="penta.status", target_member="penta.scribe", operation="reconcile_preview", evidence_refs=["test:scribe"], payload={"scan_text": "PentaScribe is registered."}, risk_class="D0")["details"]["result"]
    assert scribe["summary"]["system"] == "PentaScribe" and scribe["state_persisted"] is False and scribe["provider_write"] is False
    marketer = invoke_member(ROOT, source_member="penta.status", target_member="penta.marketer", operation="cycle_preview", evidence_refs=["test:marketer"], payload={}, risk_class="D0")["details"]["result"]
    assert marketer["summary"]["status"] in {"ARTIFACT_DISPATCHED", "PARTIAL_HOLD"} and marketer["state_persisted"] is False and marketer["provider_write"] is False


def test_promoted_pentamail_status_is_bound_to_live_evidence() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.mail", operation="production_status", evidence_refs=["test:mail-production"], risk_class="D0")
    status = result["details"]["result"]
    assert result["disposition"] == "completed" and status["state"] == "PRODUCTION_VERIFIED"
    assert status["provider_send_http_200_verified"] is True and status["founder_inbox_readback_verified"] is True
    assert status["provider_write_performed_by_this_adapter"] is False


def test_promoted_pentastatus_owner_snapshot_is_current() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.status", operation="owner_snapshot", evidence_refs=["test:status-owner"], risk_class="D0")
    snapshot = result["details"]["result"]
    assert snapshot["production_member_count"] == 21 and snapshot["production_adapter_coverage_complete"] is True
    assert snapshot["promotion_count"] == 5 and snapshot["provider_write_performed"] is False
    assert snapshot["hourly_reporting"]["provider_send_http_200_verified"] is True


def test_pentacontext_contract_probe_is_local_and_evidence_bound() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.context", operation="contract_probe", evidence_refs=["test:context-contract"], risk_class="D0")
    probe = result["details"]["result"]
    assert result["disposition"] == "completed"
    assert probe["schema"] == "ct.penta.context.contract-probe.v1" and probe["system_key"] == "penta.context" and probe["version"] == "1.1.0"
    assert probe["effective_maturity"] == "production"
    assert probe["provider_call_performed"] is False and probe["credential_material_accessed"] is False and probe["authority_expanded"] is False
    assert len(probe["production_evidence"]["v1_1_automation_receipt_sha256"]) == 64


def test_promoted_credentials_build_and_certify_operations_are_bounded() -> None:
    credentials = invoke_member(ROOT, source_member="penta.status", target_member="penta.credentials", operation="binding_census", evidence_refs=["test:credentials"], risk_class="D0")["details"]["result"]
    assert credentials["provider_count"] >= 8 and credentials["secret_values_returned"] is False and credentials["state_persisted"] is False
    assert all("fingerprints" not in row for row in credentials["providers"])
    build = invoke_member(ROOT, source_member="penta.status", target_member="penta.build", operation="provider_adapter_probe", evidence_refs=["test:build"], payload={"provider_id": "resend"}, risk_class="D0")["details"]["result"]
    assert build["build"]["artifact_exists"] is True and build["build"]["provider_write_performed"] is False and build["build"]["state_persisted"] is False
    certify = invoke_member(ROOT, source_member="penta.status", target_member="penta.certify", operation="provider_static_probe", evidence_refs=["test:certify"], payload={"provider_id": "resend"}, risk_class="D0")["details"]["result"]
    assert certify["runtime_probe"]["network_probe_performed"] is False and certify["runtime_probe"]["provider_write_performed"] is False
    assert certify["production_evidence_projection"]["current_failed"] == 0 and certify["production_evidence_projection"]["current_completed"] == 15



def test_evi_builder_and_immune_adapters_are_bounded() -> None:
    evi = invoke_member(
        ROOT,
        source_member="penta.status",
        target_member="penta.evi-builder",
        operation="evidence_bundle_preview",
        evidence_refs=["test:evi-builder-preview"],
        payload={"head_sha": "a" * 40, "created_at": "2026-08-27T00:00:00Z"},
        risk_class="D0",
    )
    preview = evi["details"]["result"]
    assert evi["disposition"] == "completed"
    assert preview["schema"] == "ct.penta.evi-builder.adapter-preview.v1"
    assert preview["bundle"]["certification_state"] == "UNVERIFIED"
    assert preview["bundle"]["production_promotion"] is False
    assert preview["independent_certification_performed"] is False
    assert preview["state_persisted"] is False and preview["provider_write_performed"] is False

    immune = invoke_member(
        ROOT,
        source_member="penta.status",
        target_member="penta.immune",
        operation="repair_plan_preview",
        evidence_refs=["test:immune-plan-preview"],
        payload={"candidate": {"id": "candidate-test", "authority_level": "D2"}},
        risk_class="D0",
    )
    plan = immune["details"]["result"]
    assert immune["disposition"] == "completed"
    assert plan["schema"] == "ct.penta.immune.adapter-preview.v1"
    assert plan["plan"]["status"] == "READY"
    assert plan["plan"]["production_promotion_authorized"] is False
    assert plan["repair_execution_performed"] is False
    assert plan["state_persisted"] is False and plan["provider_write_performed"] is False


def test_mail_send_still_requires_separate_provider_lane() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.mail", operation="send", evidence_refs=["test:no-local-mail-send"])
    assert result["disposition"] == "hold_fail_closed" and "no registered executable adapter" in result["details"]["reason"]


def test_unknown_member_fails_closed() -> None:
    _, snapshot = load_family(ROOT); expect_error(lambda: member_status(snapshot, "penta.this-does-not-exist"), "unknown or unregistered")


def run() -> None:
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests: test(); print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} executable Penta Family tests")


if __name__ == "__main__": run()
