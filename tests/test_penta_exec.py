"""Regression tests for the executable Penta Family member control plane."""
from __future__ import annotations
import copy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.penta_exec import PentaExecutionError, family_list, family_validate, invoke_member, load_adapter_registry, member_status, validate_adapter_registry  # noqa: E402
from runtime.penta_family import load_family  # noqa: E402


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
    assert registry["fail_closed"] is True and registry["version"] == "1.1.0"
    assert len(registry["adapters"]) == 7
    assert all(adapter["provider_effect"] is False for adapter in registry["adapters"])


def test_provider_effect_builtin_adapter_is_rejected() -> None:
    broken = copy.deepcopy(load_adapter_registry(ROOT)); broken["adapters"][0]["provider_effect"] = True
    expect_error(lambda: validate_adapter_registry(broken), "does not permit provider-effect handlers")


def test_unknown_handler_is_rejected() -> None:
    broken = copy.deepcopy(load_adapter_registry(ROOT)); broken["adapters"][0]["handler"] = "shell"
    expect_error(lambda: validate_adapter_registry(broken), "unregistered builtin handler")


def test_family_execution_contract_validates() -> None:
    registry, snapshot = load_family(ROOT); result = family_validate(ROOT, registry, snapshot)
    assert result["disposition"] == "pass", result
    assert result["details"]["blockers"] == []
    assert result["details"]["adapter_count"] == 7


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
    assert envelope["schema"] == "ct.penta.error.v1"
    assert envelope["context"]["api_key"] == "[REDACTED]"
    assert envelope["context"]["safe"] == "ok"
    assert "internal" not in envelope


def test_penta_logger_emit_is_redacted_and_sealed() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.logger", operation="emit", evidence_refs=["test:penta-exec:logger"], payload={"message": "adapter live", "context": {"token": "do-not-leak", "safe": 1}}, risk_class="D0")
    assert result["disposition"] == "completed", result
    emitted = result["details"]["result"]
    assert emitted["record"]["schema"] == "ct.penta.log.v1"
    assert emitted["record"]["context"]["token"] == "[REDACTED]"
    assert len(emitted["line_sha256"]) == 64


def test_penta_trace_creates_bounded_context() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.trace", operation="new_context", evidence_refs=["test:penta-exec:trace"], payload={"parent_span_id": "parent-1"}, risk_class="D0")
    assert result["disposition"] == "completed", result
    trace = result["details"]["result"]
    assert len(trace["trace_id"]) == 32 and len(trace["span_id"]) == 16
    assert trace["parent_span_id"] == "parent-1"


def test_penta_metric_builds_local_snapshot() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.metric", operation="snapshot", evidence_refs=["test:penta-exec:metric"], payload={"counters": {"penta.exec.calls": 2}, "gauges": {"penta.exec.ready": 1}, "observations": {"penta.exec.duration": [0.1, 0.3]}}, risk_class="D0")
    assert result["disposition"] == "completed", result
    metrics = result["details"]["result"]
    assert metrics["schema"] == "ct.penta.metrics.v1"
    assert metrics["counters"]["penta.exec.calls"] == 2.0
    assert metrics["observations"]["penta.exec.duration"]["count"] == 2


def test_unimplemented_mail_send_fails_closed() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.mail", operation="send", evidence_refs=["test:penta-exec:no-mail-adapter"])
    assert result["disposition"] == "hold_fail_closed"
    assert "no registered executable adapter" in result["details"]["reason"]


def test_unknown_member_fails_closed() -> None:
    _, snapshot = load_family(ROOT)
    expect_error(lambda: member_status(snapshot, "penta.this-does-not-exist"), "unknown or unregistered")


def run() -> None:
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests: test(); print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} executable Penta Family tests")


if __name__ == "__main__": run()
