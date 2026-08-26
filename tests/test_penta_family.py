"""Regression tests for the Penta Family production control plane."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.penta_family import (  # noqa: E402
    PentaFamilyError,
    compose_family,
    load_family,
    member_dispatch_gate,
    validate_family_registry,
)


def expect_error(fn, contains: str) -> None:
    try:
        fn()
    except PentaFamilyError as exc:
        assert contains in str(exc), (contains, str(exc))
    else:
        raise AssertionError(f"expected PentaFamilyError containing {contains!r}")


def test_live_repository_contract() -> None:
    registry, snapshot = load_family(ROOT)
    assert registry["status"] == "production"
    assert snapshot["family_status"] == "production"
    assert snapshot["fail_closed"] is True
    assert snapshot["member_count"] >= 3

    # Mature children may pass the family eligibility gate.
    scribe = member_dispatch_gate(snapshot, "penta.scribe")
    assert scribe["eligible"] is True

    # Core members that are only specified remain fail-closed even though the
    # umbrella family itself is in production.
    control = member_dispatch_gate(snapshot, "penta.control")
    assert control["eligible"] is False
    assert control["disposition"] == "hold_fail_closed"

    # Newly implemented institutional services are not silently promoted.
    capital = member_dispatch_gate(snapshot, "penta.capital")
    assert capital["eligible"] is False
    assert "implemented" in capital["reason"]

    unknown = member_dispatch_gate(snapshot, "penta.unknown")
    assert unknown["eligible"] is False
    assert unknown["disposition"] == "hold_fail_closed"


def test_contract_cannot_disable_fail_closed() -> None:
    registry = json.loads((ROOT / "data/penta/family.registry.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(registry)
    broken["production_contract"]["fail_closed"] = False
    expect_error(lambda: validate_family_registry(broken), "fail_closed")


def test_missing_required_catalog_blocks_family_snapshot() -> None:
    registry = {
        "registry_id": "crownthrive.penta.family",
        "canonical_name": "Penta Family",
        "status": "production",
        "production_scope": "institutional_control_plane",
        "production_contract": {
            "fail_closed": True,
            "member_status_is_independent": True,
            "production_family_does_not_promote_members": True,
            "unknown_members_block_dispatch": True,
            "duplicate_machine_keys_block_dispatch": True,
            "missing_required_catalogs_block_dispatch": True,
            "execution_requires_member_eligibility": True,
            "execution_eligible_maturity": ["certified", "production"],
        },
        "catalogs": [
            {
                "catalog_id": "missing",
                "path": "data/penta/missing.registry.json",
                "required": True,
                "role": "test",
            }
        ],
    }
    with tempfile.TemporaryDirectory() as temp:
        expect_error(lambda: compose_family(Path(temp), registry), "missing required family catalogs")


def test_duplicate_machine_keys_block_composition() -> None:
    registry = {
        "registry_id": "crownthrive.penta.family",
        "canonical_name": "Penta Family",
        "status": "production",
        "production_scope": "institutional_control_plane",
        "production_contract": {
            "fail_closed": True,
            "member_status_is_independent": True,
            "production_family_does_not_promote_members": True,
            "unknown_members_block_dispatch": True,
            "duplicate_machine_keys_block_dispatch": True,
            "missing_required_catalogs_block_dispatch": True,
            "execution_requires_member_eligibility": True,
            "execution_eligible_maturity": ["certified", "production"],
        },
        "catalogs": [
            {"catalog_id": "a", "path": "data/penta/a.json", "required": True, "role": "test"},
            {"catalog_id": "b", "path": "data/penta/b.json", "required": True, "role": "test"},
        ],
    }
    catalog = {
        "systems": [
            {
                "machine_key": "penta.test",
                "canonical_name": "PentaTest",
                "maturity": "production",
            }
        ]
    }
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "data/penta").mkdir(parents=True)
        for name in ("a.json", "b.json"):
            (root / "data/penta" / name).write_text(json.dumps(catalog), encoding="utf-8")
        expect_error(lambda: compose_family(root, registry), "duplicate machine_key")


def run() -> None:
    tests = [
        test_live_repository_contract,
        test_contract_cannot_disable_fail_closed,
        test_missing_required_catalog_blocks_family_snapshot,
        test_duplicate_machine_keys_block_composition,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} Penta Family tests")


if __name__ == "__main__":
    run()
