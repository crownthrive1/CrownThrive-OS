"""Family-integration regression for Penta institutional controls."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.penta_family import load_family, member_dispatch_gate  # noqa: E402

EXPECTED = {"penta.compliance", "penta.privacy", "penta.identity", "penta.data", "penta.records", "penta.procure", "penta.vendor", "penta.contracts", "penta.quality"}


def test_controls_are_implemented_but_not_execution_eligible() -> None:
    registry, snapshot = load_family(ROOT)
    assert registry["schema_version"] == "1.2.0"
    assert registry["status"] == "production"
    for key in sorted(EXPECTED):
        assert key in snapshot["members"], key
        assert snapshot["members"][key]["maturity"] == "implemented", key
        gate = member_dispatch_gate(snapshot, key)
        assert gate["eligible"] is False, key
        assert gate["disposition"] == "hold_fail_closed", key
        assert "implemented" in gate["reason"], key


def test_new_composition_planes_resolve_exactly() -> None:
    _, snapshot = load_family(ROOT)
    for plane in ("data_identity_privacy", "procurement_vendor_contracts", "quality_compliance_assurance"):
        assert plane in snapshot["control_plane_resolution"], plane
        for item in snapshot["control_plane_resolution"][plane]:
            assert item["kind"] in {"penta_member", "external_authority"}
            if item["kind"] == "penta_member":
                assert item["resolved_to"] in snapshot["members"]


def run() -> None:
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests:
        test()
    print(f"PASS: {len(tests)} Penta institutional-controls family tests")


if __name__ == "__main__":
    run()
