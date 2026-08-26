"""Regression tests for the Penta Family-of-Families topology."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.penta_families import (  # noqa: E402
    DiscoveredPenta,
    PentaFamiliesError,
    assign_primary_families,
    compose_snapshot,
    family_portal,
    load_json,
    normalize_name,
    portal_index,
    REGISTRY_PATH,
)


def family_for(snapshot: dict, name: str) -> str:
    target = normalize_name(name)
    for family in snapshot["families"]:
        for member in family["members"]:
            if member["normalized_name"] == target:
                return family["family_id"]
    raise AssertionError(f"missing discovered Penta: {name}")


def member(snapshot: dict, name: str) -> dict:
    target = normalize_name(name)
    for family in snapshot["families"]:
        for item in family["members"]:
            if item["normalized_name"] == target:
                return item
    raise AssertionError(name)


def test_live_inventory_is_complete_and_classified() -> None:
    snapshot = compose_snapshot(ROOT)
    assert snapshot["status"] == "production"
    assert snapshot["family_count"] == 15
    assert snapshot["discovered_penta_count"] >= 90
    assert snapshot["classified_penta_count"] == snapshot["discovered_penta_count"]
    assert snapshot["unclassified_penta_count"] == 0
    assert snapshot["family_assignment_promotes_members"] is False
    assert snapshot["authority_manufactured"] is False
    assert len(portal_index(snapshot)) == 15


def test_representative_primary_families() -> None:
    snapshot = compose_snapshot(ROOT)
    expected = {
        "PentaOS": "system-architecture",
        "PentaRoute": "routing-interoperability",
        "PentaGet": "transport-primitives",
        "PentaAuth": "security-trust",
        "PentaSnapshot": "resilience-continuity",
        "PentaDocs": "knowledge-semantics-data",
        "PentaGreen": "commerce-economy",
        "PentaWorkforce OS": "workforce-people",
        "PentaBrain": "observability-organic",
        "PentaRunners": "build-release",
        "PentaMedia": "media-creative",
        "PentaSignal": "intelligence-research",
        "PentaMail": "communications-service",
        "PentaBoard": "governance-legal",
        "PentaAgents": "automation-agentic",
        "PentaImmune": "security-trust",
        "PentaEVIBuilder": "security-trust",
    }
    for name, family_id in expected.items():
        assert family_for(snapshot, name) == family_id, name


def test_discovery_merges_registry_layers_without_duplicates() -> None:
    snapshot = compose_snapshot(ROOT)
    docs = member(snapshot, "PentaDocs")
    assert "machine" in docs["source_classes"]
    assert "component" in docs["source_classes"]
    assert "institutional" in docs["source_classes"]

    route = member(snapshot, "PentaRoute")
    assert "machine" in route["source_classes"]
    assert "component" in route["source_classes"]
    assert "institutional" in route["source_classes"]

    # PentaGet is intentionally a capability primitive rather than a parent
    # machine-catalog member, but it must still be institutionalized.
    get = member(snapshot, "PentaGet")
    assert "route_primitive" in get["source_classes"]
    assert get["primary_family"] == "transport-primitives"


def test_family_assignment_does_not_promote_machine_maturity() -> None:
    snapshot = compose_snapshot(ROOT)
    for family in snapshot["families"]:
        for item in family["members"]:
            assert item["evidence_state"]["family_assignment_promoted_member"] is False
            maturities = set(item["evidence_state"]["machine_maturity"])
            expected = bool(maturities & {"certified", "production"})
            assert item["evidence_state"]["execution_eligible_from_machine_maturity"] is expected


def test_unclassified_future_penta_fails_closed() -> None:
    registry = load_json(ROOT / REGISTRY_PATH)
    inventory = {
        "pentafutureunknown": DiscoveredPenta(
            normalized="pentafutureunknown",
            name="PentaFutureUnknown",
            source_classes={"institutional"},
            source_paths={"synthetic"},
        )
    }
    try:
        assign_primary_families(inventory, registry)
    except PentaFamiliesError as exc:
        assert "unclassified Penta identities" in str(exc)
    else:
        raise AssertionError("unclassified future Penta should fail closed")


def test_primary_family_collision_fails_closed() -> None:
    registry = load_json(ROOT / REGISTRY_PATH)
    registry = dict(registry)
    registry["families"] = [dict(x) for x in registry["families"]]
    registry["families"][0]["explicit_members"] = list(registry["families"][0]["explicit_members"]) + ["PentaRoute"]
    inventory = {
        "pentaroute": DiscoveredPenta(
            normalized="pentaroute",
            name="PentaRoute",
            source_classes={"machine"},
            source_paths={"synthetic"},
        )
    }
    try:
        assign_primary_families(inventory, registry)
    except PentaFamiliesError as exc:
        assert "explicit primary-family collision" in str(exc)
    else:
        raise AssertionError("duplicate primary-family ownership should fail closed")


def test_every_family_portal_tells_required_story() -> None:
    registry = load_json(ROOT / REGISTRY_PATH)
    snapshot = compose_snapshot(ROOT)
    required = set(registry["portal_contract"]["required_sections"])
    for row in portal_index(snapshot):
        payload = family_portal(snapshot, registry, row["family_id"])
        assert payload["portal_route"].startswith("/io/pentas/families/")
        assert payload["portal_state"] == "contracted"
        assert payload["frontend_deployment_claim"] is False
        assert set(payload["sections"]) == required
        assert "never creates" in payload["sections"]["authority_boundary"]


def run() -> None:
    tests = [
        test_live_inventory_is_complete_and_classified,
        test_representative_primary_families,
        test_discovery_merges_registry_layers_without_duplicates,
        test_family_assignment_does_not_promote_machine_maturity,
        test_unclassified_future_penta_fails_closed,
        test_primary_family_collision_fails_closed,
        test_every_family_portal_tells_required_story,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} Penta Families tests")


if __name__ == "__main__":
    run()
