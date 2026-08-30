"""Evidence-derived catalog convergence engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scripts.commercialization.catalog_core import (
    CatalogError, SourceRecord, commercial_safety_signature, contains_secret_material,
    dump_json, iter_json_files, load_json, normalize_source_record, sha256_json,
    source_rank, source_record_evidence, visibility_block, walk_records,
)
from scripts.commercialization.catalog_offers import generated_offers, validate_offer

def load_package_targets(repo_root: Path, policy: Mapping[str, Any]) -> Mapping[str, Any]:
    path = repo_root / policy["package_targets_ref"]
    targets = load_json(path)
    if not isinstance(targets, Mapping):
        raise CatalogError(f"package targets must be an object: {path}")
    return targets


def load_routing(repo_root: Path, policy: Mapping[str, Any]) -> Mapping[str, Any]:
    path = repo_root / policy["routing_policy_ref"]
    routing = load_json(path)
    if not isinstance(routing, Mapping):
        raise CatalogError(f"routing policy must be an object: {path}")
    return routing


def validate_routing(routing: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    lanes = routing.get("lanes")
    if not isinstance(lanes, Mapping):
        return ["routing_missing_lanes"]
    hot = lanes.get("hot")
    if not isinstance(hot, Mapping) or hot.get("side_effects_allowed") is not False:
        failures.append("hot_lane_must_be_read_only")
    for lane_name, lane in lanes.items():
        if not isinstance(lane, Mapping):
            failures.append(f"invalid_lane:{lane_name}")
            continue
        operations = lane.get("operations", [])
        if not isinstance(operations, list) or not operations:
            failures.append(f"lane_without_operations:{lane_name}")
    fallback = routing.get("fallback", {})
    if isinstance(fallback, Mapping) and fallback.get("automatic_money_movement_fallback") is not False:
        failures.append("automatic_money_movement_fallback_must_be_false")
    return failures


def build_catalog(
    repo_root: Path,
    output: Path,
    source_sha: str | None,
    policy_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    policy_path = policy_path or (repo_root / "commercialization/policy.v1.json")
    policy = load_json(policy_path)
    if not isinstance(policy, Mapping):
        raise CatalogError("commercialization policy must be a JSON object")

    secret_findings = contains_secret_material(policy)
    if secret_findings:
        raise CatalogError(f"secret-like material found in policy: {secret_findings}")

    collections = set(policy.get("record_collections", []))
    normalized: list[SourceRecord] = []
    parse_failures: list[dict[str, str]] = []
    for path in iter_json_files(
        repo_root,
        policy.get("source_roots", []),
        policy.get("exclude_roots", []),
    ):
        relative = path.relative_to(repo_root).as_posix()
        try:
            document = load_json(path)
        except CatalogError as exc:
            parse_failures.append({"source_path": relative, "error": str(exc)})
            continue
        if contains_secret_material(document):
            parse_failures.append({"source_path": relative, "error": "secret-like material rejected"})
            continue
        for record, object_path in walk_records(document, collections, relative):
            source = normalize_source_record(record, relative, object_path, policy)
            if source is not None:
                normalized.append(source)

    # De-duplicate exact component/version/source-object records deterministically.
    unique: dict[tuple[str, str, str, str], SourceRecord] = {}
    for item in normalized:
        key = (item.component_id, item.version, item.source_path, item.object_path)
        unique[key] = item

    eligible: list[dict[str, Any]] = []
    withheld: list[dict[str, Any]] = []
    offers: list[dict[str, Any]] = []

    grouped: dict[tuple[str, str], list[SourceRecord]] = {}
    for source in unique.values():
        grouped.setdefault((source.component_id, source.version), []).append(source)

    for _, source_group in sorted(grouped.items(), key=lambda item: item[0]):
        ordered_group = sorted(
            source_group,
            key=lambda source: (
                source_rank(source.source_path, policy),
                source.object_path,
                source.source_fingerprint,
            ),
        )
        item = ordered_group[0]
        source_records = [source_record_evidence(source, policy) for source in ordered_group]
        signatures = {commercial_safety_signature(source, policy) for source in ordered_group}
        if len(signatures) > 1:
            withheld.append(
                {
                    "component_id": item.component_id,
                    "canonical_name": item.name,
                    "component_type": item.component_type,
                    "version": item.version,
                    "source_sha": source_sha,
                    "source_record_count": len(ordered_group),
                    "source_records": source_records,
                    "withheld_reasons": ["conflicting_commercialization_source_records"],
                }
            )
            continue

        reasons: list[str] = []
        if item.certification_state is None:
            reasons.append("missing_explicit_production_certification")
        visibility_reason = visibility_block(item.record, policy["visibility"])
        if visibility_reason:
            reasons.append(visibility_reason)
        if item.version == "0.0.0+unknown":
            reasons.append("missing_component_version")

        base = {
            "component_id": item.component_id,
            "canonical_name": item.name,
            "component_type": item.component_type,
            "version": item.version,
            "source_path": item.source_path,
            "object_path": item.object_path,
            "source_fingerprint": item.source_fingerprint,
            "source_sha": source_sha,
            "certification_state": item.certification_state,
            "certification_source": item.certification_source,
            "source_record_count": len(ordered_group),
            "source_records": source_records,
        }
        if reasons:
            withheld.append({**base, "withheld_reasons": sorted(set(reasons))})
            continue

        component_offers = generated_offers(item, policy, source_sha)
        offer_failures: list[str] = []
        valid_offers: list[dict[str, Any]] = []
        for offer in component_offers:
            failures = validate_offer(offer)
            if failures:
                offer_failures.extend(f"{offer.get('offer_id')}:{failure}" for failure in failures)
            else:
                valid_offers.append(offer)
        if offer_failures:
            withheld.append({**base, "withheld_reasons": sorted(set(offer_failures))})
            continue

        eligible.append(
            {
                **base,
                "catalog_state": "ELIGIBLE",
                "install_contract": {
                    "universal": [
                        "git",
                        "github_release",
                        "oci_artifact",
                        "json_schema",
                        "openapi",
                        "mcp",
                    ],
                    "immutable_source_required": True,
                    "checksums_required": True,
                    "sbom_required": True,
                    "provenance_required": True,
                },
                "offer_ids": [offer["offer_id"] for offer in valid_offers],
            }
        )
        offers.extend(valid_offers)

    package_targets = load_package_targets(repo_root, policy)
    routing = load_routing(repo_root, policy)
    routing_failures = validate_routing(routing)
    if routing_failures:
        raise CatalogError("routing policy failed validation: " + ", ".join(routing_failures))

    catalog = {
        "schema_version": "1.0.0",
        "catalog_id": "ct.catalog.cos-commercialization.v1",
        "policy_id": policy["policy_id"],
        "component_version": policy["component_version"],
        "institutional_generation": policy["institutional_generation"],
        "os_compatibility": policy["os_compatibility"],
        "source_sha": source_sha,
        "counts": {
            "source_records": len(unique),
            "converged_component_versions": len(grouped),
            "eligible_components": len(eligible),
            "withheld_components": len(withheld),
            "offers": len(offers),
            "parse_failures": len(parse_failures),
        },
        "components": eligible,
        "withheld": withheld,
        "parse_failures": parse_failures,
    }
    install_index = {
        "schema_version": "1.0.0",
        "index_id": "ct.install-index.cos-commercialization.v1",
        "source_sha": source_sha,
        "universal_contract": package_targets["universal_contract"],
        "native_registry_adapters": package_targets["native_registry_adapters"],
        "components": [
            {
                "component_id": item["component_id"],
                "version": item["version"],
                "source_sha": source_sha,
                "source_path": item["source_path"],
                "source_fingerprint": item["source_fingerprint"],
                "install_contract": item["install_contract"],
            }
            for item in eligible
        ],
    }
    offer_index = {
        "schema_version": "1.0.0",
        "index_id": "ct.offer-index.chlom-commercialization.v1",
        "source_sha": source_sha,
        "wallet_contract_ref": policy["wallet_contract_ref"],
        "offers": sorted(offers, key=lambda x: x["offer_id"]),
    }
    readiness = {
        "schema_version": "1.0.0",
        "readiness_id": "ct.readiness.cos-commercialization.v1",
        "source_sha": source_sha,
        "catalog_fingerprint": sha256_json(catalog),
        "install_index_fingerprint": sha256_json(install_index),
        "offer_index_fingerprint": sha256_json(offer_index),
        "routing_fingerprint": sha256_json(routing),
        "publication_default": policy["publication"]["default"],
        "production_publication_authorized": False,
        "remaining_external_gates": [
            "independent verification of exact merged source",
            "PentaRelease package and provider readback",
            "registry credentials and protected environments per target",
            "approved fixed pricing before self-service paid checkout",
            "exact CHLOM/ECAC authorization before paid settlement",
            "wallet unattended value remains zero until separately certified",
        ],
    }

    dump_json(output / "catalog.json", catalog)
    dump_json(output / "install-index.json", install_index)
    dump_json(output / "offers.json", offer_index)
    dump_json(output / "mesh-routing.json", routing)
    dump_json(output / "readiness.json", readiness)

    return {
        "catalog": catalog,
        "install_index": install_index,
        "offers": offer_index,
        "routing": routing,
        "readiness": readiness,
    }


