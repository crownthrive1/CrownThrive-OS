"""Family-integration regression for Penta institutional controls."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.penta_family import load_family, member_dispatch_gate  # noqa: E402

IMPLEMENTED = {"penta.privacy", "penta.identity", "penta.data", "penta.records", "penta.procure", "penta.vendor", "penta.contracts", "penta.quality"}
PRODUCTION_CONTROLS = {"penta.compliance", "penta.license"}


def test_controls_preserve_independent_maturity_and_scope() -> None:
    registry, snapshot = load_family(ROOT)
    assert registry["schema_version"] == "1.5.0"
    assert registry["status"] == "production"
    assert registry["interoperability_contract"]["protocol_version"] == "1.0.0"
    assert registry["interoperability_contract"]["execution_requires_chlom_and_dail_authority_refs"] is True
    assert registry["interoperability_contract"]["execution_requires_dail_event_plan"] is True
    assert registry["interoperability_contract"]["terminal_execution_requires_dail_receipt"] is True
    assert registry["interoperability_contract"]["execution_preserves_member_maturity"] is True
    for key in sorted(IMPLEMENTED):
        assert key in snapshot["members"], key
        assert snapshot["members"][key]["maturity"] == "implemented", key
        gate = member_dispatch_gate(snapshot, key)
        assert gate["eligible"] is False, key
        assert gate["disposition"] == "hold_fail_closed", key
        assert "implemented" in gate["reason"], key
    for key in sorted(PRODUCTION_CONTROLS):
        assert key in snapshot["members"], key
        assert snapshot["members"][key]["maturity"] == "production", key
        gate = member_dispatch_gate(snapshot, key)
        assert gate["eligible"] is True, key
        assert gate["disposition"] == "member_gate_passed", key


def test_new_composition_planes_resolve_exactly() -> None:
    _, snapshot = load_family(ROOT)
    for plane in (
        "data_identity_privacy",
        "procurement_vendor_contracts",
        "quality_compliance_assurance",
        "rights_licensing",
        "interoperability_fabric",
        "observability",
    ):
        assert plane in snapshot["control_plane_resolution"], plane
        for item in snapshot["control_plane_resolution"][plane]:
            assert item["kind"] in {"penta_member", "external_authority"}
            if item["kind"] == "penta_member":
                assert item["resolved_to"] in snapshot["members"]


def test_observability_members_are_family_production_members() -> None:
    _, snapshot = load_family(ROOT)
    for key in ("penta.error", "penta.logger", "penta.trace", "penta.metric"):
        assert key in snapshot["members"], key
        assert snapshot["members"][key]["maturity"] == "production", key
        gate = member_dispatch_gate(snapshot, key)
        assert gate["eligible"] is True, key
        assert gate["disposition"] == "member_gate_passed", key


def run() -> None:
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests:
        test()
    print(f"PASS: {len(tests)} Penta institutional-controls family tests")


if __name__ == "__main__":
    run()
