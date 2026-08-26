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
    assert result["disposition"] == "completed_read_only"
    assert result["details"]["member_count"] == snapshot["member_count"]
    assert {row["machine_key"] for row in result["details"]["members"]} == set(snapshot["members"])


def test_specified_member_has_real_status_without_fake_execution_promotion() -> None:
    _, snapshot = load_family(ROOT); result = member_status(snapshot, "penta.mail")
    assert result["details"]["maturity"] == "specified"
    assert result["details"]["execution_gate"]["eligible"] is False
    assert result["details"]["portal_route"] == "/penta/mail"


def test_execution_adapter_registry_is_static_and_fail_closed() -> None:
    registry = load_adapter_registry(ROOT)
    assert registry["fail_closed"] is True and registry["version"] == "1.2.0"
    assert len(registry["adapters"]) == 13
    assert all(adapter["provider_effect"] is False for adapter in registry["adapters"])


def test_provider_effect_builtin_adapter_is_rejected() -> None:
    broken = copy.deepcopy(load_adapter_registry(ROOT)); broken["adapters"][0]["provider_effect"] = True
    expect_error(lambda: validate_adapter_registry(broken), "does not permit provider-effect handlers")


def test_unknown_handler_is_rejected() -> None:
    broken = copy.deepcopy(load_adapter_registry(ROOT)); broken["adapters"][0]["handler"] = "shell"
    expect_error(lambda: validate_adapter_registry(broken), "unregistered builtin handler")


def test_family_execution_contract_validates_and_covers_all_production_members() -> None:
    registry, snapshot = load_family(ROOT); result = family_validate(ROOT, registry, snapshot)
    assert result["disposition"] == "pass", result
    assert result["details"]["blockers"] == []
    assert result["details"]["adapter_count"] == 13
    coverage = result["details"]["execution_adapter_coverage"]
    assert coverage["complete"] is True
    assert coverage["eligible_member_count"] == 13
    assert coverage["eligible_members_with_adapter"] == 13
    assert coverage["missing_adapter_members"] == []


def test_beata_heartbeat_is_executable_and_evidence_sealed() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.beata", operation="heartbeat", evidence_refs=["test:penta-exec:beata"], risk_class="D0")
    assert result["disposition"] == "completed", result
    assert result["details"]["result"]["machine_key"] == "penta.beata"
    assert result["details"]["envelope_sha256"] and len(result["receipt_sha256"]) == 64


def test_mesh_route_check_can_inspect_specified_target_without_invoking_it() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.mesh", operation="route_check", evidence_refs=["test:penta-exec:mesh"], payload={"candidate_target": "penta.mail"}, risk_class="D0")
    assert result["disposition"] == "completed", result
    route = result["details"]["result"]
    assert route["registered"] is True and route["maturity"] == "specified" and route["execution_eligible"] is False


def test_penta_error_normalize_redacts_context() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.error", operation="normalize", evidence_refs=["test:penta-exec:error"], payload={"message": "internal failure", "context": {"api_key": "secret-value", "safe": "ok"}}, risk_class="D0")
    assert result["disposition"] == "completed", result
    envelope = result["details"]["result"]
    assert envelope["schema"] == "ct.penta.error.v1" and envelope["context"]["api_key"] == "[REDACTED]" and envelope["context"]["safe"] == "ok"


def test_penta_logger_emit_is_redacted_and_sealed() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.logger", operation="emit", evidence_refs=["test:penta-exec:logger"], payload={"message": "adapter live", "context": {"token": "do-not-leak", "safe": 1}}, risk_class="D0")
    assert result["disposition"] == "completed", result
    emitted = result["details"]["result"]
    assert emitted["record"]["schema"] == "ct.penta.log.v1" and emitted["record"]["context"]["token"] == "[REDACTED]" and len(emitted["line_sha256"]) == 64


def test_penta_trace_creates_bounded_context() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.trace", operation="new_context", evidence_refs=["test:penta-exec:trace"], payload={"parent_span_id": "parent-1"}, risk_class="D0")
    assert result["disposition"] == "completed", result
    trace = result["details"]["result"]
    assert len(trace["trace_id"]) == 32 and len(trace["span_id"]) == 16 and trace["parent_span_id"] == "parent-1"


def test_penta_metric_builds_local_snapshot() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.metric", operation="snapshot", evidence_refs=["test:penta-exec:metric"], payload={"counters": {"penta.exec.calls": 2}, "gauges": {"penta.exec.ready": 1}, "observations": {"penta.exec.duration": [0.1, 0.3]}}, risk_class="D0")
    assert result["disposition"] == "completed", result
    metrics = result["details"]["result"]
    assert metrics["schema"] == "ct.penta.metrics.v1" and metrics["counters"]["penta.exec.calls"] == 2.0 and metrics["observations"]["penta.exec.duration"]["count"] == 2


def test_penta_heartbeat_probes_all_production_members() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.heartbeat", operation="control_plane_probe", evidence_refs=["test:penta-exec:heartbeat"], risk_class="D0")
    assert result["disposition"] == "completed", result
    probe = result["details"]["result"]
    assert probe["schema"] == "ct.penta.heartbeat.control-plane-probe.v1"
    assert probe["production_member_count"] == 13
    assert all(row["adapter_bound"] for row in probe["members"])


def test_penta_od_reports_bounded_dispatch_readiness() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.od", operation="readiness_assess", evidence_refs=["test:penta-exec:od"], payload={"candidate_target": "penta.metric"}, risk_class="D0")
    assert result["disposition"] == "completed", result
    readiness = result["details"]["result"]
    assert readiness["schema"] == "ct.penta.od.readiness.v1"
    assert readiness["execution_eligible"] is True and readiness["adapter_operations"] == ["snapshot"] and readiness["authority_expanded"] is False


def _compliance_payload() -> dict:
    return {"obligations": [{"obligation_id": "obl.test", "title": "Test adopted obligation", "source_ref": "test:source", "owner_ref": "test:owner", "status": "active", "jurisdictions": ["US"], "scopes": ["license"], "evidence_requirements": ["ctrl.test"], "controls": [{"control_id": "ctrl.test", "requirement": "evidence exists"}], "effective_from": "2026-01-01", "source_sha256": "a" * 64}], "jurisdictions": ["US"], "scopes": ["license"], "evidence_index": {"ctrl.test": ["evidence:test"]}, "as_of": "2026-08-26"}


def test_penta_compliance_executes_deterministic_evaluation() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.compliance", operation="evaluate", evidence_refs=["test:penta-exec:compliance"], payload=_compliance_payload(), risk_class="D0")
    assert result["disposition"] == "completed", result
    evaluation = result["details"]["result"]
    assert evaluation["schema"] == "ct.penta.compliance-evaluation.v1" and evaluation["disposition"] == "PASS_EVIDENCE_SATISFIED" and verify_receipt(evaluation)


def test_penta_license_evaluates_readiness_without_issuing_grant() -> None:
    compliance = invoke_member(ROOT, source_member="penta.status", target_member="penta.compliance", operation="evaluate", evidence_refs=["test:penta-exec:compliance-license"], payload=_compliance_payload(), risk_class="D0")["details"]["result"]
    asset = {"asset_id": "asset.test", "version": "1.0.0", "content_sha256": "b" * 64, "title": "Test Asset", "owner_ref": "owner:test", "status": "active", "rights_control_refs": ["chlom:rights:test"], "allowed_rights": ["display"], "prohibited_rights": [], "territories": ["US"], "media": ["digital"]}
    request = {"request_id": "req.test", "asset_id": "asset.test", "asset_version": "1.0.0", "asset_sha256": "b" * 64, "licensee_ref": "licensee:test", "use_case": "test", "lane": "self_serve", "risk_class": "D1", "valid_from": "2026-08-26", "valid_until": "2027-08-26", "template_ref": "template:test", "acceptance_ref": "accept:test", "idempotency_key": "idem:test", "requested_rights": ["display"], "territories": ["US"], "media": ["digital"], "authority_trace": {"chlom_ref": "chlom:test", "accountable_owner": "owner:test"}, "compliance_receipt": compliance, "commercial_terms_ref": "terms:test", "provider_effect": False}
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.license", operation="readiness", evidence_refs=["test:penta-exec:license"], payload={"asset": asset, "request": request}, risk_class="D0")
    assert result["disposition"] == "completed", result
    readiness = result["details"]["result"]; decision = readiness["decision"]
    assert decision["schema"] == "ct.penta.license-decision.v1" and decision["disposition"] == "ISSUE_READY_INTERNAL" and decision["binding_action_performed"] is False and verify_receipt(decision)
    assert readiness["adapter_boundary"] == "readiness_only_no_license_grant_issued" and readiness["binding_action_performed"] is False


def test_penta_scribe_runs_real_isolated_reconciliation_cycle() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.scribe", operation="reconcile_preview", evidence_refs=["test:penta-exec:scribe"], payload={"scan_text": "PentaScribe is a registered CrownThrive system."}, risk_class="D0")
    assert result["disposition"] == "completed", result
    cycle = result["details"]["result"]
    assert cycle["summary"]["system"] == "PentaScribe" and cycle["summary"]["promotion_state"] == "NO_AUTOMATIC_PROMOTION"
    assert len(cycle["receipt"]["receipt_sha256"]) == 64 and cycle["state_persisted"] is False and cycle["provider_write"] is False


def test_penta_marketer_runs_real_isolated_bounded_cycle() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.marketer", operation="cycle_preview", evidence_refs=["test:penta-exec:marketer"], payload={}, risk_class="D0")
    assert result["disposition"] == "completed", result
    cycle = result["details"]["result"]
    assert cycle["summary"]["status"] in {"ARTIFACT_DISPATCHED", "PARTIAL_HOLD"}
    assert len(cycle["receipt"]["receipt_sha256"]) == 64 and cycle["state_persisted"] is False and cycle["provider_write"] is False


def test_unimplemented_mail_send_fails_closed() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.mail", operation="send", evidence_refs=["test:penta-exec:no-mail-adapter"])
    assert result["disposition"] == "hold_fail_closed" and "no registered executable adapter" in result["details"]["reason"]


def test_unknown_member_fails_closed() -> None:
    _, snapshot = load_family(ROOT)
    expect_error(lambda: member_status(snapshot, "penta.this-does-not-exist"), "unknown or unregistered")


def run() -> None:
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests: test(); print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} executable Penta Family tests")


if __name__ == "__main__": run()
