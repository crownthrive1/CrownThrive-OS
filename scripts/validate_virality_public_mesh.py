#!/usr/bin/env python3
"""Validate and compare Virality Music public-mesh inventory snapshots.

Validation is fail-closed for schema, public-safety, deterministic hashes, and
route policy.  Baseline comparison is observational only: it reports drift and
can fail CI when requested, but it never edits documentation, commits, opens or
merges a pull request, or changes a provider.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from sync_virality_public_mesh import (
    BLOCKED_PAGE_SUFFIXES,
    INVENTORY_ID,
    PLATFORM_ID,
    SCHEMA,
    canonical_json,
    compute_inventory_hashes,
    load_xml_estate_index,
    origin_for,
    page_policy_reason,
    sanitize_url,
    same_origin,
    value_sha256,
    write_json,
)


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "generic bearer token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    "GitHub token": re.compile(r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Stripe secret": re.compile(r"\b(?:sk_live_|sk_test_|whsec_)[A-Za-z0-9]{16,}\b"),
    "URL credential": re.compile(r"https?://[^/@\s:]+:[^/@\s]+@"),
}
FORBIDDEN_KEYS = {
    "authorization",
    "body",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "raw_html",
    "request_headers",
    "response_headers",
    "secret",
    "token",
}
ALT_STATES = {"empty", "missing", "not_applicable", "present"}
PRODUCT_SUMMARY_KEYS = {
    "brand",
    "category",
    "credits_labels",
    "description",
    "images",
    "name",
    "offers",
    "sku",
    "types",
    "url",
}
OFFER_SUMMARY_KEYS = {
    "availability",
    "high_price",
    "item_condition",
    "low_price",
    "name",
    "price",
    "price_currency",
    "price_valid_until",
    "seller",
    "types",
    "url",
}
COMMERCE_OBSERVATION_KEYS = {
    "availability",
    "credits_labels",
    "kind",
    "name",
    "observation_only",
    "observation_sha256",
    "observed_at",
    "paid_redeemable",
    "price",
    "price_currency",
    "redemption_inferred",
    "sku",
    "source_route",
    "source_type",
    "url",
}


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def is_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def sorted_unique_strings(value: Any) -> bool:
    return isinstance(value, list) and value == sorted(set(value)) and all(isinstance(item, str) for item in value)


def iter_nodes(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, dict):
        for key in sorted(value):
            yield from iter_nodes(value[key], f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_nodes(child, f"{path}[{index}]")


def validate_public_url(value: Any, root_origin: str, field: str, errors: list[str], *, same_origin_required: bool) -> None:
    if not isinstance(value, str):
        errors.append(f"{field} must be a URL string")
        return
    try:
        actual_origin = origin_for(value)
    except (ValueError, UnicodeError):
        errors.append(f"{field} is not an absolute HTTP(S) URL")
        return
    if same_origin_required and actual_origin != root_origin:
        errors.append(f"{field} escaped the source origin")
    parsed_query = "?" in value or "#" in value or "@" in value.split("//", 1)[-1].split("/", 1)[0]
    if parsed_query:
        errors.append(f"{field} retains a query, fragment, or URL credential")


def validate_structured_summary(summary: Any, field: str, errors: list[str], *, product: bool) -> None:
    if not isinstance(summary, dict):
        errors.append(f"{field} must be an object")
        return
    allowed = PRODUCT_SUMMARY_KEYS if product else OFFER_SUMMARY_KEYS
    extra = sorted(set(summary) - allowed)
    if extra:
        errors.append(f"{field} contains non-whitelisted keys: {extra}")
    if product:
        if "credits_labels" in summary and not sorted_unique_strings(summary.get("credits_labels")):
            errors.append(f"{field}.credits_labels must be sorted and unique")
        if "images" in summary and not sorted_unique_strings(summary.get("images")):
            errors.append(f"{field}.images must be sorted and unique")
        offers = summary.get("offers", [])
        if not isinstance(offers, list):
            errors.append(f"{field}.offers must be a list")
        else:
            for index, offer in enumerate(offers):
                validate_structured_summary(offer, f"{field}.offers[{index}]", errors, product=False)


def validate_commerce_observation(row: Any, field: str, root_origin: str, errors: list[str]) -> None:
    if not isinstance(row, dict):
        errors.append(f"{field} must be an object")
        return
    extra = sorted(set(row) - COMMERCE_OBSERVATION_KEYS)
    if extra:
        errors.append(f"{field} contains non-whitelisted keys: {extra}")
    require(row.get("kind") in {"offer", "product"}, f"{field}.kind is invalid", errors)
    require(row.get("source_type") in {"json_ld", "json_ld_nested", "open_graph"}, f"{field}.source_type is invalid", errors)
    validate_public_url(row.get("source_route"), root_origin, f"{field}.source_route", errors, same_origin_required=True)
    if row.get("url") is not None:
        validate_public_url(row.get("url"), root_origin, f"{field}.url", errors, same_origin_required=False)
    require(is_timestamp(row.get("observed_at")), f"{field}.observed_at must be ISO-8601", errors)
    require(row.get("observation_only") is True, f"{field} must remain observation-only", errors)
    require(row.get("paid_redeemable") == 0, f"{field} cannot claim paid redemption while SAFE_HOLD", errors)
    require(row.get("redemption_inferred") is False, f"{field} cannot infer redemption", errors)
    if "credits_labels" in row:
        require(sorted_unique_strings(row.get("credits_labels")), f"{field}.credits_labels must be sorted/unique", errors)
    semantic = {key: value for key, value in row.items() if key not in {"observation_sha256", "observed_at"}}
    require(row.get("observation_sha256") == value_sha256(semantic), f"{field}.observation_sha256 drift", errors)


def validate_inventory(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["inventory root must be an object"]

    require(data.get("schema") == SCHEMA, "inventory schema drift", errors)
    require(data.get("inventory_id") == INVENTORY_ID, "inventory stable ID drift", errors)
    require(data.get("platform_id") == PLATFORM_ID, "platform stable ID drift", errors)
    require(data.get("visibility") == "public_projection_observation", "visibility boundary drift", errors)

    authority = data.get("authority")
    require(isinstance(authority, dict), "authority must be an object", errors)
    if isinstance(authority, dict):
        require(authority.get("authority_class") == "D0_observational", "inventory must remain D0 observational", errors)
        require(authority.get("creates_rights_or_runtime_authority") is False, "inventory may not create authority", errors)
        require(authority.get("certifies_availability_or_purchase") is False, "inventory may not certify commerce", errors)

    source = data.get("source")
    if not isinstance(source, dict):
        return errors + ["source must be an object"]
    root_origin = source.get("origin")
    if not isinstance(root_origin, str):
        return errors + ["source.origin must be a string"]
    try:
        normalized_origin = origin_for(root_origin)
    except ValueError:
        return errors + ["source.origin must be an absolute HTTP(S) origin"]
    require(normalized_origin == root_origin, "source.origin is not canonical", errors)
    validate_public_url(source.get("sitemap_url"), root_origin, "source.sitemap_url", errors, same_origin_required=True)
    require(is_timestamp(source.get("source_timestamp")), "source timestamp must be timezone-aware ISO-8601", errors)
    require(source.get("retrieval_mode") in {"fixture", "network"}, "unknown retrieval mode", errors)

    robots = source.get("robots")
    require(isinstance(robots, dict), "source.robots must be an object", errors)
    if isinstance(robots, dict):
        validate_public_url(robots.get("url"), root_origin, "source.robots.url", errors, same_origin_required=True)
        if robots.get("content_sha256") is not None:
            require(is_sha256(robots.get("content_sha256")), "robots content hash is invalid", errors)

    sitemap_documents = source.get("sitemap_documents")
    require(isinstance(sitemap_documents, list), "source.sitemap_documents must be a list", errors)
    if isinstance(sitemap_documents, list):
        urls = [row.get("url") for row in sitemap_documents if isinstance(row, dict)]
        require(urls == sorted(set(urls)), "sitemap document URLs must be sorted and unique", errors)
        for index, row in enumerate(sitemap_documents):
            field = f"source.sitemap_documents[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{field} must be an object")
                continue
            validate_public_url(row.get("url"), root_origin, f"{field}.url", errors, same_origin_required=True)
            validate_public_url(row.get("final_url"), root_origin, f"{field}.final_url", errors, same_origin_required=True)
            require(is_sha256(row.get("content_sha256")), f"{field}.content_sha256 is invalid", errors)

    policy = data.get("policy")
    require(isinstance(policy, dict), "policy must be an object", errors)
    if isinstance(policy, dict):
        for key in (
            "same_origin_page_fetches_only",
            "images_or_binaries_downloaded",
            "forms_submitted",
            "checkout_or_mutation_routes_followed",
        ):
            expected = key == "same_origin_page_fetches_only"
            require(policy.get(key) is expected, f"public-safety policy drift: {key}", errors)
        require(policy.get("http_method") == "GET", "crawler method must remain GET-only", errors)
        require(policy.get("queries_and_fragments_retained") is False, "queries/fragments may not be retained", errors)
        require(
            policy.get("robots_unavailable_behavior")
            == "record_failure_then_explicit_denylist_and_public_html_only",
            "robots-unavailable boundary drift",
            errors,
        )

    routes = data.get("routes")
    if not isinstance(routes, list):
        return errors + ["routes must be a list"]
    route_urls = [row.get("url") for row in routes if isinstance(row, dict)]
    require(route_urls == sorted(set(route_urls)), "route URLs must be sorted and unique", errors)
    for index, route in enumerate(routes):
        field = f"routes[{index}]"
        if not isinstance(route, dict):
            errors.append(f"{field} must be an object")
            continue
        url = route.get("url")
        validate_public_url(url, root_origin, f"{field}.url", errors, same_origin_required=True)
        validate_public_url(route.get("final_url"), root_origin, f"{field}.final_url", errors, same_origin_required=True)
        if isinstance(url, str):
            reason = page_policy_reason(url, root_origin)
            require(reason is None, f"{field} violates page-fetch policy: {reason}", errors)
            suffix = Path(url.split("?", 1)[0]).suffix.lower()
            require(suffix not in BLOCKED_PAGE_SUFFIXES, f"{field} is a blocked binary/document route", errors)
        require(isinstance(route.get("status"), int) and 200 <= route["status"] < 300, f"{field}.status is not successful", errors)
        require(route.get("content_type") in {"application/xhtml+xml", "text/html"}, f"{field} content type is not HTML", errors)
        require(sorted_unique_strings(route.get("discovered_via")), f"{field}.discovered_via must be sorted/unique", errors)
        classification = route.get("classification")
        require(isinstance(classification, dict), f"{field}.classification must be an object", errors)
        if isinstance(classification, dict):
            require(sorted_unique_strings(classification.get("categories")), f"{field} categories must be sorted/unique", errors)
            require(bool(classification.get("categories")), f"{field} requires at least one category", errors)
            require(sorted_unique_strings(classification.get("universes")), f"{field} universes must be sorted/unique", errors)
        require(sorted_unique_strings(route.get("structured_data_types")), f"{field} structured-data types must be sorted/unique", errors)
        require(sorted_unique_strings(route.get("internal_links")), f"{field} internal links must be sorted/unique", errors)
        for link_index, link in enumerate(route.get("internal_links", [])):
            validate_public_url(link, root_origin, f"{field}.internal_links[{link_index}]", errors, same_origin_required=True)
        require(sorted_unique_strings(route.get("external_domains")), f"{field} external domains must be sorted/unique", errors)

        images = route.get("images")
        require(isinstance(images, list), f"{field}.images must be a list", errors)
        if isinstance(images, list):
            image_keys = []
            for image_index, image in enumerate(images):
                image_field = f"{field}.images[{image_index}]"
                if not isinstance(image, dict):
                    errors.append(f"{image_field} must be an object")
                    continue
                validate_public_url(image.get("url"), root_origin, f"{image_field}.url", errors, same_origin_required=False)
                require(image.get("alt_state") in ALT_STATES, f"{image_field}.alt_state is invalid", errors)
                require(isinstance(image.get("query_redacted"), bool), f"{image_field}.query_redacted must be boolean", errors)
                image_keys.append((image.get("url"), image.get("alt") or "", image.get("alt_state"), image.get("source")))
            require(image_keys == sorted(set(image_keys)), f"{field}.images must be sorted and unique", errors)

        asset_references = route.get("asset_references")
        require(isinstance(asset_references, list), f"{field}.asset_references must be a list", errors)
        if isinstance(asset_references, list):
            asset_keys = []
            for asset_index, asset in enumerate(asset_references):
                asset_field = f"{field}.asset_references[{asset_index}]"
                if not isinstance(asset, dict):
                    errors.append(f"{asset_field} must be an object")
                    continue
                validate_public_url(asset.get("url"), root_origin, f"{asset_field}.url", errors, same_origin_required=False)
                require(asset.get("observation_status") == "public_reference_observed_not_downloaded", f"{asset_field} observation status drift", errors)
                require(isinstance(asset.get("asset_type"), str), f"{asset_field}.asset_type is required", errors)
                require(isinstance(asset.get("source"), str), f"{asset_field}.source is required", errors)
                asset_keys.append((asset.get("url"), asset.get("asset_type"), asset.get("source")))
            require(asset_keys == sorted(set(asset_keys)), f"{field}.asset_references must be sorted and unique", errors)

        for item_index, summary in enumerate(route.get("products", [])):
            validate_structured_summary(summary, f"{field}.products[{item_index}]", errors, product=True)
        for item_index, summary in enumerate(route.get("offers", [])):
            validate_structured_summary(summary, f"{field}.offers[{item_index}]", errors, product=False)
        commerce_observations = route.get("commerce_observations")
        require(isinstance(commerce_observations, list), f"{field}.commerce_observations must be a list", errors)
        if isinstance(commerce_observations, list):
            observation_keys = [row.get("observation_sha256") for row in commerce_observations if isinstance(row, dict)]
            require(observation_keys == sorted(set(observation_keys)), f"{field}.commerce_observations must be hash sorted/unique", errors)
            for observation_index, observation in enumerate(commerce_observations):
                validate_commerce_observation(
                    observation,
                    f"{field}.commerce_observations[{observation_index}]",
                    root_origin,
                    errors,
                )
        hashes = route.get("hashes")
        require(isinstance(hashes, dict), f"{field}.hashes must be an object", errors)
        if isinstance(hashes, dict):
            require(is_sha256(hashes.get("content_sha256")), f"{field} content hash is invalid", errors)
            require(is_sha256(hashes.get("metadata_sha256")), f"{field} metadata hash is invalid", errors)

    assets = data.get("assets")
    require(
        isinstance(assets, dict)
        and isinstance(assets.get("images"), list)
        and isinstance(assets.get("references"), list),
        "assets.images and assets.references must be lists",
        errors,
    )
    asset_references = assets.get("references", []) if isinstance(assets, dict) else []
    asset_urls = [row.get("url") for row in asset_references if isinstance(row, dict)]
    require(asset_urls == sorted(set(asset_urls)), "asset reference URLs must be sorted and unique", errors)
    for index, asset in enumerate(asset_references):
        field = f"assets.references[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{field} must be an object")
            continue
        validate_public_url(asset.get("url"), root_origin, f"{field}.url", errors, same_origin_required=False)
        for key in ("asset_types", "source_types", "referenced_by"):
            require(sorted_unique_strings(asset.get(key)), f"{field}.{key} must be sorted and unique", errors)
        require(asset.get("first_seen_route") == (asset.get("referenced_by") or [None])[0], f"{field}.first_seen_route drift", errors)
        require(asset.get("observation_status") == "public_reference_observed_not_downloaded", f"{field} observation status drift", errors)
        expected = dict(asset)
        observed_hash = expected.pop("reference_sha256", None)
        require(observed_hash == value_sha256(expected), f"{field}.reference_sha256 drift", errors)
    images = assets.get("images", []) if isinstance(assets, dict) else []
    image_urls = [row.get("url") for row in images if isinstance(row, dict)]
    require(image_urls == sorted(set(image_urls)), "asset image URLs must be sorted and unique", errors)
    for index, image in enumerate(images):
        field = f"assets.images[{index}]"
        if not isinstance(image, dict):
            errors.append(f"{field} must be an object")
            continue
        validate_public_url(image.get("url"), root_origin, f"{field}.url", errors, same_origin_required=False)
        for key in ("alt_texts", "alt_states", "source_types", "referenced_by"):
            require(sorted_unique_strings(image.get(key)), f"{field}.{key} must be sorted and unique", errors)
        expected = dict(image)
        observed_hash = expected.pop("reference_sha256", None)
        require(observed_hash == value_sha256(expected), f"{field}.reference_sha256 drift", errors)

    for collection_name, product in (("products", True), ("offers", False)):
        collection = data.get(collection_name)
        require(isinstance(collection, list), f"{collection_name} must be a list", errors)
        if not isinstance(collection, list):
            continue
        hashes = [row.get("summary_sha256") for row in collection if isinstance(row, dict)]
        require(hashes == sorted(set(hashes)), f"{collection_name} hashes must be sorted and unique", errors)
        for index, row in enumerate(collection):
            field = f"{collection_name}[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{field} must be an object")
                continue
            validate_structured_summary(row.get("summary"), f"{field}.summary", errors, product=product)
            require(row.get("summary_sha256") == value_sha256(row.get("summary")), f"{field} summary hash drift", errors)
            require(sorted_unique_strings(row.get("referenced_by")), f"{field}.referenced_by must be sorted/unique", errors)

    commerce = data.get("commerce")
    require(isinstance(commerce, dict), "commerce must be an object", errors)
    if isinstance(commerce, dict):
        require(commerce.get("economic_state") == "SAFE_HOLD", "commerce economic state must remain SAFE_HOLD", errors)
        require(commerce.get("observation_only") is True, "commerce inventory must remain observation-only", errors)
        require(commerce.get("checkout_requests_performed") == 0, "crawler must never call checkout", errors)
        require(commerce.get("redemption_enabled") is False, "redemption cannot be enabled while SAFE_HOLD", errors)
        require(commerce.get("paid_redeemable") == 0, "paid_redeemable must be zero while SAFE_HOLD", errors)
        observations = commerce.get("observations")
        require(isinstance(observations, list), "commerce.observations must be a list", errors)
        if isinstance(observations, list):
            observation_keys = [
                (row.get("source_route"), row.get("kind"), row.get("observation_sha256"))
                for row in observations
                if isinstance(row, dict)
            ]
            require(observation_keys == sorted(observation_keys), "commerce observations must be deterministically sorted", errors)
            for index, observation in enumerate(observations):
                validate_commerce_observation(observation, f"commerce.observations[{index}]", root_origin, errors)

    related = data.get("related_domains")
    require(isinstance(related, list), "related_domains must be a list", errors)
    if isinstance(related, list):
        domains = [row.get("domain") for row in related if isinstance(row, dict)]
        require(domains == sorted(set(domains)), "related domains must be sorted and unique", errors)
        for index, row in enumerate(related):
            field = f"related_domains[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{field} must be an object")
                continue
            require(isinstance(row.get("domain"), str) and "." in row["domain"], f"{field}.domain is invalid", errors)
            require(sorted_unique_strings(row.get("relationship_types")), f"{field}.relationship_types must be sorted/unique", errors)
            require(sorted_unique_strings(row.get("referenced_by")), f"{field}.referenced_by must be sorted/unique", errors)
            expected = dict(row)
            observed_hash = expected.pop("reference_sha256", None)
            require(observed_hash == value_sha256(expected), f"{field}.reference_sha256 drift", errors)

    failures = data.get("failures")
    excluded = data.get("excluded_routes")
    require(isinstance(failures, list), "failures must be a list", errors)
    require(isinstance(excluded, list), "excluded_routes must be a list", errors)
    if isinstance(failures, list):
        failure_keys = [(row.get("url"), row.get("stage"), row.get("code")) for row in failures if isinstance(row, dict)]
        require(failure_keys == sorted(failure_keys), "failures must be deterministically sorted", errors)
    if isinstance(excluded, list):
        exclusion_keys = [(row.get("url"), row.get("reason"), row.get("discovered_from")) for row in excluded if isinstance(row, dict)]
        require(exclusion_keys == sorted(exclusion_keys), "excluded routes must be deterministically sorted", errors)
        for index, row in enumerate(excluded):
            if isinstance(row, dict):
                validate_public_url(row.get("url"), root_origin, f"excluded_routes[{index}].url", errors, same_origin_required=False)

    summary = data.get("summary")
    require(isinstance(summary, dict), "summary must be an object", errors)
    if isinstance(summary, dict):
        expected_counts = {
            "route_count": len(routes),
            "asset_reference_count": len(asset_references),
            "image_reference_count": len(images),
            "product_summary_count": len(data.get("products", [])),
            "offer_summary_count": len(data.get("offers", [])),
            "commerce_observation_count": len(data.get("commerce", {}).get("observations", [])),
            "related_domain_count": len(related or []),
            "failure_count": len(failures or []),
            "excluded_route_count": len(excluded or []),
            "category_count": len({item for route in routes for item in route.get("classification", {}).get("categories", [])}),
            "universe_count": len({item for route in routes for item in route.get("classification", {}).get("universes", [])}),
        }
        for key, expected in expected_counts.items():
            require(summary.get(key) == expected, f"summary.{key} drift: expected {expected}", errors)

    hashes = data.get("hashes")
    require(isinstance(hashes, dict), "hashes must be an object", errors)
    if isinstance(hashes, dict):
        expected_hashes = compute_inventory_hashes(data)
        require(hashes == expected_hashes, "top-level deterministic hashes drift", errors)

    for path, value in iter_nodes(data):
        if isinstance(value, dict):
            forbidden = sorted({str(key).lower() for key in value} & FORBIDDEN_KEYS)
            if forbidden:
                errors.append(f"{path} contains forbidden public-projection keys: {forbidden}")
            if data.get("commerce", {}).get("economic_state") == "SAFE_HOLD":
                for key, claim in value.items():
                    normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
                    if normalized_key in {"paidredeemable", "redeemablepaidcount"}:
                        if isinstance(claim, (int, float)) and not isinstance(claim, bool) and claim > 0:
                            errors.append(f"{path}.{key} claims paid redeemable > 0 while commerce is SAFE_HOLD")
                    if normalized_key in {
                        "paidredemptionsopen",
                        "paidtopupsopen",
                        "redemptionavailable",
                        "redemptionenabled",
                    } and claim is True:
                        errors.append(f"{path}.{key} enables paid/redemption behavior while commerce is SAFE_HOLD")

    serialized = canonical_json(data).decode("utf-8")
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(serialized):
            errors.append(f"inventory contains credential-shaped material: {label}")
    return sorted(set(errors))


def _record_map(data: Mapping[str, Any], field: str, key: str) -> dict[str, Any]:
    return {row[key]: row for row in data.get(field, []) if isinstance(row, dict) and isinstance(row.get(key), str)}


def validate_route_index(data: Any, expected_origin: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    urls: list[str] = []
    if not isinstance(data, dict):
        return ["route index root must be an object"], urls
    require(data.get("schema_version") == "1.0.0", "route-index schema version drift", errors)
    require(
        data.get("registry_id") == "ct.registry.vm.public-route-index.2026-08-26",
        "route-index stable ID drift",
        errors,
    )
    require(
        data.get("classification") == "PUBLIC_FIRST_PARTY_ROUTE_OBSERVATION",
        "route-index classification drift",
        errors,
    )
    require(data.get("status") == "OBSERVED_SNAPSHOT", "route-index status drift", errors)
    require(data.get("site_origin") == expected_origin, "route-index origin mismatch", errors)
    require(is_timestamp(data.get("observed_at")), "route-index observed_at is invalid", errors)
    require(is_sha256(data.get("source_capture_sha256")), "route-index source capture hash is invalid", errors)
    rows = data.get("routes")
    require(isinstance(rows, list), "route-index routes must be a list", errors)
    if not isinstance(rows, list):
        return sorted(set(errors)), urls
    require(data.get("route_count") == len(rows), "route-index route_count drift", errors)
    paths: list[str] = []
    for index, row in enumerate(rows):
        field = f"route_index.routes[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{field} must be an object")
            continue
        path = row.get("path")
        label = row.get("label")
        require(isinstance(path, str) and path.startswith("/"), f"{field}.path is invalid", errors)
        require(isinstance(label, str) and bool(label.strip()), f"{field}.label is invalid", errors)
        if not isinstance(path, str) or not path.startswith("/"):
            continue
        paths.append(path)
        url, _redacted = sanitize_url(path, base_url=expected_origin)
        if url is None or not same_origin(url, expected_origin):
            errors.append(f"{field}.path is not a public same-origin path")
        else:
            urls.append(url)
    require(paths == sorted(set(paths)), "route-index paths must be sorted and unique", errors)
    return sorted(set(errors)), urls


def route_index_coverage(inventory: Mapping[str, Any], expected_urls: Iterable[str]) -> dict[str, Any]:
    expected_list = list(expected_urls)
    expected_set = set(expected_list)
    observed = {row["url"] for row in inventory.get("routes", []) if isinstance(row, dict) and isinstance(row.get("url"), str)}
    observed.update(
        row["url"]
        for collection in (inventory.get("failures", []), inventory.get("excluded_routes", []))
        for row in collection
        if isinstance(row, dict) and isinstance(row.get("url"), str)
    )
    accounted_rows = sum(url in observed for url in expected_list)
    return {
        "expected_route_count": len(expected_list),
        "expected_unique_safe_url_count": len(expected_set),
        "accounted_route_count": accounted_rows,
        "unaccounted_routes": sorted(expected_set - observed),
        "coverage_complete": expected_set <= observed,
    }


def compare_inventory(current: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    current_routes = _record_map(current, "routes", "url")
    baseline_routes = _record_map(baseline, "routes", "url")
    common_routes = sorted(set(current_routes) & set(baseline_routes))
    changed_routes = [
        url
        for url in common_routes
        if current_routes[url].get("hashes", {}).get("metadata_sha256")
        != baseline_routes[url].get("hashes", {}).get("metadata_sha256")
    ]
    content_only_changes = [
        url
        for url in common_routes
        if current_routes[url].get("hashes", {}).get("content_sha256")
        != baseline_routes[url].get("hashes", {}).get("content_sha256")
        and url not in changed_routes
    ]

    def string_set(path: tuple[str, ...]) -> set[str]:
        current_node: Any = current
        baseline_node: Any = baseline
        for part in path[:-1]:
            current_node = current_node.get(part, {}) if isinstance(current_node, dict) else {}
            baseline_node = baseline_node.get(part, {}) if isinstance(baseline_node, dict) else {}
        field = path[-1]
        current_values = current_node.get(field, []) if isinstance(current_node, dict) else []
        baseline_values = baseline_node.get(field, []) if isinstance(baseline_node, dict) else []
        return set(current_values), set(baseline_values)  # type: ignore[return-value]

    current_images = {row["url"] for row in current.get("assets", {}).get("images", [])}
    baseline_images = {row["url"] for row in baseline.get("assets", {}).get("images", [])}
    current_assets = {row["url"] for row in current.get("assets", {}).get("references", [])}
    baseline_assets = {row["url"] for row in baseline.get("assets", {}).get("references", [])}
    current_products = {row["summary_sha256"] for row in current.get("products", [])}
    baseline_products = {row["summary_sha256"] for row in baseline.get("products", [])}
    current_offers = {row["summary_sha256"] for row in current.get("offers", [])}
    baseline_offers = {row["summary_sha256"] for row in baseline.get("offers", [])}
    current_domains = {row["domain"] for row in current.get("related_domains", [])}
    baseline_domains = {row["domain"] for row in baseline.get("related_domains", [])}

    changes = {
        "routes_added": sorted(set(current_routes) - set(baseline_routes)),
        "routes_removed": sorted(set(baseline_routes) - set(current_routes)),
        "routes_metadata_changed": changed_routes,
        "routes_content_only_changed": content_only_changes,
        "images_added": sorted(current_images - baseline_images),
        "images_removed": sorted(baseline_images - current_images),
        "assets_added": sorted(current_assets - baseline_assets),
        "assets_removed": sorted(baseline_assets - current_assets),
        "product_summaries_added": sorted(current_products - baseline_products),
        "product_summaries_removed": sorted(baseline_products - current_products),
        "offer_summaries_added": sorted(current_offers - baseline_offers),
        "offer_summaries_removed": sorted(baseline_offers - current_offers),
        "related_domains_added": sorted(current_domains - baseline_domains),
        "related_domains_removed": sorted(baseline_domains - current_domains),
        "failure_count_delta": current.get("summary", {}).get("failure_count", 0)
        - baseline.get("summary", {}).get("failure_count", 0),
        "excluded_route_count_delta": current.get("summary", {}).get("excluded_route_count", 0)
        - baseline.get("summary", {}).get("excluded_route_count", 0),
    }
    has_drift = current.get("hashes", {}).get("semantic_sha256") != baseline.get("hashes", {}).get("semantic_sha256")
    return {
        "schema": "ct.report.virality-public-mesh-drift.v1",
        "inventory_id": INVENTORY_ID,
        "status": "drift" if has_drift else "no_drift",
        "observed_at": current.get("source", {}).get("source_timestamp"),
        "current_semantic_sha256": current.get("hashes", {}).get("semantic_sha256"),
        "baseline_semantic_sha256": baseline.get("hashes", {}).get("semantic_sha256"),
        "changes": changes,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="Validate a generated crawl snapshot. With no arguments, validate the committed public registries offline.",
    )
    parser.add_argument("--baseline", type=Path)
    parser.add_argument(
        "--route-index",
        type=Path,
        help="Validate/account for the committed dated public route snapshot.",
    )
    parser.add_argument(
        "--xml-estate-index",
        type=Path,
        help="Validate/account for the dated recovered 2,389-route XML census.",
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--fail-on-drift", action="store_true")
    parser.add_argument("--require-baseline", action="store_true")
    return parser.parse_args(argv)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_committed_registry_contract(repo_root: Path) -> list[str]:
    """Validate the committed, public-safe Virality portal registries offline."""

    errors: list[str] = []
    registry_root = repo_root / "registry/virality-music"
    origin = "https://vm.crownthrive.com"
    paths = {
        "web": registry_root / "public-web-estate-v1.json",
        "xml": registry_root / "public-xml-estate-index-2026-08-26.json",
        "routes": registry_root / "public-route-index-2026-08-26.json",
        "universes": registry_root / "public-universe-directory-2026-08-26.json",
        "products": registry_root / "public-product-catalog-observation-2026-08-26.json",
        "masters": registry_root / "source-master-public-metadata-v1.json",
        "mesh": registry_root / "mesh-bindings-v1.json",
    }
    loaded: dict[str, Any] = {}
    for name, path in paths.items():
        try:
            loaded[name] = read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"committed registry {name} is unreadable: {exc}")
    if errors:
        return sorted(set(errors))

    route_errors, route_urls = validate_route_index(loaded["routes"], origin)
    errors.extend(route_errors)
    require(len(route_urls) == 1_825, "committed rendered route count must remain 1,825", errors)
    try:
        xml_routes, xml_assets_by_page, xml_metadata = load_xml_estate_index(paths["xml"], origin)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"committed XML-estate index is invalid: {exc}")
    else:
        xml_asset_rows = [row for rows in xml_assets_by_page.values() for row in rows]
        require(len(xml_routes) == 2_389, "committed XML route count must remain 2,389", errors)
        require(len(xml_asset_rows) == 2_010, "committed XML image-occurrence count must remain 2,010", errors)
        require(len({row["url"] for row in xml_asset_rows}) == 529, "committed unique XML image count must remain 529", errors)
        require(xml_metadata.get("parse_recovery_required") is True, "malformed-XML recovery evidence must remain explicit", errors)

    universe = loaded["universes"]
    require(
        universe.get("registry_id") == "ct.registry.vm.public-universe-directory.2026-08-26",
        "universe-directory stable ID drift",
        errors,
    )
    records = universe.get("records")
    require(isinstance(records, list), "universe-directory records must be a list", errors)
    if isinstance(records, list):
        require(len(records) == 66, "universe-directory record count must remain 66", errors)
        require(len({row.get("slug") for row in records if isinstance(row, dict)}) == 66, "universe slugs must be unique", errors)
        require(
            len({row.get("projection_record_id") for row in records if isinstance(row, dict)}) == 66,
            "universe projection IDs must be unique",
            errors,
        )
        direct = 0
        redirects = 0
        for index, row in enumerate(records):
            field = f"universe.records[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{field} must be an object")
                continue
            route = row.get("public_route", {})
            art = row.get("public_art", {})
            licensing = row.get("licensing", {})
            validate_public_url(route.get("observed_url"), origin, f"{field}.public_route.observed_url", errors, same_origin_required=True)
            validate_public_url(art.get("url"), origin, f"{field}.public_art.url", errors, same_origin_required=True)
            require(
                licensing.get("inquiry_route") == f"{origin}/chlom-licensing",
                f"{field} must use the live CHLOM inquiry route",
                errors,
            )
            require(
                licensing.get("state") == "INQUIRY_ONLY_WORK_LEVEL_CLEARANCE_REQUIRED",
                f"{field} licensing authority drift",
                errors,
            )
            require(is_sha256(row.get("source_record_sha256")), f"{field} observation hash is invalid", errors)
            direct += route.get("resolution_state") == "HTTP_200_OBSERVED"
            redirects += route.get("resolution_state") == "REDIRECT_OBSERVED"
        require(direct == 65, "universe direct-resolution count must remain 65", errors)
        require(redirects == 1, "universe redirect count must remain 1", errors)
    art_refs = universe.get("unique_public_art_references")
    require(isinstance(art_refs, list) and len(art_refs) == 42, "unique universe art count must remain 42", errors)

    products = loaded["products"]
    require(
        products.get("registry_id") == "ct.registry.vm.public-product-catalog-observation.2026-08-26",
        "product-catalog stable ID drift",
        errors,
    )
    product_authority = products.get("commerce_authority", {})
    require(product_authority.get("global_state") == "SAFE_HOLD", "product catalog must remain SAFE_HOLD", errors)
    require(product_authority.get("redeemable_paid_count") == 0, "committed product catalog cannot claim paid redemption", errors)
    require(product_authority.get("production_ready_held_count") == 353, "held product count must remain 353", errors)
    require(product_authority.get("free_count") == 2, "free product count must remain 2", errors)
    product_records = products.get("records")
    require(isinstance(product_records, list), "product records must be a list", errors)
    if isinstance(product_records, list):
        require(products.get("record_count") == len(product_records) == 355, "product record count must remain 355", errors)
        require(len({row.get("sku") for row in product_records if isinstance(row, dict)}) == 355, "product SKUs must be unique", errors)
        for index, row in enumerate(product_records):
            field = f"products.records[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{field} must be an object")
                continue
            forbidden = {
                "download_limit",
                "link_ttl",
                "embedded_amount_raw",
                "embedded_amount_semantics",
                "configured_credit_price",
                "source_record_sha256",
            } & set(row)
            require(not forbidden, f"{field} exposes protected/internal fields: {sorted(forbidden)}", errors)
            projection = {key: value for key, value in row.items() if key != "public_projection_sha256"}
            require(
                row.get("public_projection_sha256") == value_sha256(projection),
                f"{field}.public_projection_sha256 drift",
                errors,
            )
            if row.get("effective_public_state") == "AVAILABLE_FREE_OBSERVED":
                require(row.get("redemption_available") is True, f"{field} free-access state drift", errors)
            else:
                require(row.get("redemption_available") is False, f"{field} cannot enable paid redemption", errors)
            validate_public_url(row.get("public_route"), origin, f"{field}.public_route", errors, same_origin_required=True)
            images = row.get("public_image_assets")
            require(isinstance(images, list) and bool(images), f"{field}.public_image_assets must be non-empty", errors)
            if isinstance(images, list):
                for image_index, url in enumerate(images):
                    validate_public_url(url, origin, f"{field}.public_image_assets[{image_index}]", errors, same_origin_required=True)
    credit_distribution = products.get("configured_credit_value_distribution")
    require(isinstance(credit_distribution, list), "aggregate configured-credit distribution must be a list", errors)
    if isinstance(credit_distribution, list):
        require(
            sum(row.get("record_count", 0) for row in credit_distribution if isinstance(row, dict)) == 355,
            "aggregate configured-credit distribution must reconcile 355 records",
            errors,
        )
        require(
            any(row.get("credits") == 0 and row.get("record_count") == 2 for row in credit_distribution if isinstance(row, dict)),
            "aggregate configured-credit distribution must preserve two free rows",
            errors,
        )

    masters = loaded["masters"]
    require(
        masters.get("registry_id") == "ct.registry.vm.source-master-public-metadata.v1",
        "source-master registry stable ID drift",
        errors,
    )
    master_summary = masters.get("inventory_summary", {})
    require(master_summary.get("artifact_count") == 16, "source-master artifact count must remain 16", errors)
    require(master_summary.get("catalog_identity_collision_count") == 1, "source-master collision count must remain one", errors)
    require(master_summary.get("collision_disposition") == "HOLD", "Book Five collision must remain HOLD", errors)
    require("encrypted_pdf_count" not in master_summary, "source-master summary exposes PDF encryption posture", errors)
    require(
        master_summary.get("render_normalized_token_sequence_parity_pair_count") == 2,
        "source-master rendered parity-pair count must remain two",
        errors,
    )
    parity_method = masters.get("parity_method", {})
    parity_method_id = "ct.method.vm.source-parity.docx-render-pdf-pdftotext-token.v1"
    require(parity_method.get("method_id") == parity_method_id, "source-parity method ID drift", errors)
    verifier_path = parity_method.get("verifier_path")
    require(verifier_path == "scripts/verify_virality_source_parity.py", "source-parity verifier path drift", errors)
    require((repo_root / str(verifier_path)).is_file(), "source-parity verifier is missing", errors)
    expected_parity = {
        "ct.parity.vm.leonard-clarence-two-damn-fools.first-illustrated-flagship.pdf-docx": (
            40_149,
            "45c759582b237ba3191a4dd2950892adcbaee71fbd9d0d98c7d478babd41da0e",
        ),
        "ct.parity.vm.leonard-coffield-fool-who-saw-everything.first-illustrated-witness.pdf-docx": (
            45_748,
            "24752d3b5bf8bba2702732d99e678679e9ab39982ca7ee40c50fb166563e2da5",
        ),
    }
    parity_pairs = masters.get("parity_pairs")
    require(isinstance(parity_pairs, list) and len(parity_pairs) == 2, "source-parity records must contain two pairs", errors)
    if isinstance(parity_pairs, list):
        observed_parity = {
            row.get("pair_id"): (row.get("token_count"), row.get("render_normalized_token_sha256"))
            for row in parity_pairs
            if isinstance(row, dict)
        }
        require(observed_parity == expected_parity, "source-parity token/hash evidence drift", errors)
        require(
            all(row.get("state") == "RENDER_NORMALIZED_TOKEN_SEQUENCE_PARITY_VERIFIED" for row in parity_pairs),
            "source-parity state overstatement or drift",
            errors,
        )
        require(all(row.get("method_id") == parity_method_id for row in parity_pairs), "source-parity method binding drift", errors)

    master_artifacts = masters.get("artifacts")
    require(isinstance(master_artifacts, list) and len(master_artifacts) == 16, "source-master artifacts must contain 16 records", errors)
    collision_artifact_ids = {
        "ct.asset.vm.book.what-really-happened.v2-illustrated-collector.candidate-a.pdf",
        "ct.asset.vm.book.what-really-happened.v2-illustrated-collector.candidate-b.pdf",
    }
    if isinstance(master_artifacts, list):
        observed_collision_ids = set()
        for index, row in enumerate(master_artifacts):
            field = f"masters.artifacts[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{field} must be an object")
                continue
            require("encryption_state" not in row, f"{field} exposes PDF encryption posture", errors)
            if row.get("artifact_id") in collision_artifact_ids:
                observed_collision_ids.add(row.get("artifact_id"))
                forbidden_collision_fields = {"byte_size", "page_count", "image_inventory", "encryption_state"} & set(row)
                require(
                    not forbidden_collision_fields,
                    f"{field} exposes collision-differentiating metadata: {sorted(forbidden_collision_fields)}",
                    errors,
                )
                require(
                    row.get("differentiating_metadata_state") == "WITHHELD_PENDING_COLLISION_RESOLUTION",
                    f"{field} collision-withholding state drift",
                    errors,
                )
                require(
                    row.get("public_metadata_withheld_fields") == ["byte_size", "page_count", "image_inventory"],
                    f"{field} collision-withheld field declaration drift",
                    errors,
                )
        require(observed_collision_ids == collision_artifact_ids, "Book Five collision artifact set drift", errors)

    web = loaded["web"]
    universe_snapshot = web.get("universe_registry_snapshot", {})
    require(
        universe_snapshot.get("directory_registry_id") == universe.get("registry_id"),
        "public-web universe-directory reference drift",
        errors,
    )
    commerce = web.get("commerce_status", {})
    require(commerce.get("status_id") == "ct.status.vm.commerce.2026-08-26", "public-web commerce status ID drift", errors)
    require(commerce.get("paid_redeemable_count") == 0, "public-web estate cannot claim paid redemption", errors)
    require("homepage_credit_listings" not in web, "public-web estate exposes title-keyed homepage credit listings", errors)
    homepage_credit_observation = web.get("homepage_credit_listing_observation", {})
    require(
        homepage_credit_observation.get("observed_listing_count") == 4,
        "public-web homepage credit-listing aggregate count drift",
        errors,
    )
    require(
        homepage_credit_observation.get("per_item_values_state")
        == "EXCLUDED_FROM_PUBLIC_REGISTRY_TO_PREVENT_PRIVATE_PRICING_RECONSTRUCTION",
        "public-web homepage credit-listing de-keying state drift",
        errors,
    )
    require("items" not in homepage_credit_observation, "public-web homepage credit observation exposes keyed items", errors)

    mesh = loaded["mesh"]
    mesh_source_ids = {
        row.get("registry_id")
        for row in mesh.get("source_registries", [])
        if isinstance(row, dict)
    }
    expected_source_ids = {
        loaded["web"].get("registry_id"),
        loaded["xml"].get("registry_id"),
        loaded["routes"].get("registry_id"),
        loaded["universes"].get("registry_id"),
        loaded["products"].get("registry_id"),
        loaded["masters"].get("registry_id"),
    }
    require(expected_source_ids <= mesh_source_ids, "mesh source-registry references are incomplete", errors)
    require(mesh.get("state_dimensions", {}).get("commerce", {}).get("state") == "SAFE_HOLD", "mesh commerce state drift", errors)

    serialized = canonical_json(loaded).decode("utf-8")
    for forbidden_text in ("/workspace/", "project_sources/", "libfile_", "file_000000"):
        require(forbidden_text not in serialized, f"committed registries expose restricted locator: {forbidden_text}", errors)
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(serialized):
            errors.append(f"committed registries contain credential-shaped material: {label}")
    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.input is None:
        incompatible = any(
            value
            for value in (
                args.baseline,
                args.route_index,
                args.xml_estate_index,
                args.report,
                args.fail_on_drift,
                args.require_baseline,
            )
        )
        if incompatible:
            print("--input is required when live-snapshot options are supplied", file=sys.stderr)
            return 1
        committed_errors = validate_committed_registry_contract(Path(__file__).resolve().parents[1])
        if committed_errors:
            print("Virality committed public mesh validation: FAIL", file=sys.stderr)
            for error in committed_errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("Virality committed public mesh validation: PASS; 7 registries; SAFE_HOLD; Book Five HOLD; rendered parity method recorded")
        return 0
    try:
        current = read_json(args.input)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Unable to read inventory: {exc}", file=sys.stderr)
        return 1
    errors = validate_inventory(current)
    if errors:
        print("Virality public mesh validation: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    coverage: dict[str, Any] | None = None
    xml_coverage: dict[str, Any] | None = None
    if args.route_index:
        try:
            route_index = read_json(args.route_index)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Unable to read route index: {exc}", file=sys.stderr)
            return 1
        route_index_errors, expected_routes = validate_route_index(route_index, current["source"]["origin"])
        if route_index_errors:
            print("Virality public route-index validation: FAIL", file=sys.stderr)
            for error in route_index_errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        coverage = route_index_coverage(current, expected_routes)
        if not coverage["coverage_complete"]:
            print(
                f"Virality route-index coverage incomplete: {len(coverage['unaccounted_routes'])} routes unaccounted",
                file=sys.stderr,
            )
            return 1
    if args.xml_estate_index:
        try:
            xml_routes, xml_assets_by_page, xml_metadata = load_xml_estate_index(
                args.xml_estate_index,
                current["source"]["origin"],
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Unable to validate XML-estate index: {exc}", file=sys.stderr)
            return 1
        route_coverage = route_index_coverage(current, list(xml_routes))
        expected_assets = {
            row["url"]
            for rows in xml_assets_by_page.values()
            for row in rows
        }
        current_assets = {
            row["url"]
            for row in current.get("assets", {}).get("references", [])
            if isinstance(row, dict) and isinstance(row.get("url"), str)
        }
        xml_coverage = {
            "registry_id": xml_metadata["registry_id"],
            "routes": route_coverage,
            "expected_unique_image_count": len(expected_assets),
            "accounted_unique_image_count": len(expected_assets & current_assets),
            "unaccounted_images": sorted(expected_assets - current_assets),
            "coverage_complete": route_coverage["coverage_complete"] and expected_assets <= current_assets,
        }
        if not xml_coverage["coverage_complete"]:
            print("Virality XML-estate route/image coverage incomplete", file=sys.stderr)
            return 1

    report: dict[str, Any] | None = None
    if args.baseline:
        if not args.baseline.is_file():
            report = {
                "schema": "ct.report.virality-public-mesh-drift.v1",
                "inventory_id": INVENTORY_ID,
                "status": "baseline_missing",
                "observed_at": current["source"]["source_timestamp"],
                "current_semantic_sha256": current["hashes"]["semantic_sha256"],
                "baseline_semantic_sha256": None,
                "changes": None,
            }
            if args.require_baseline:
                if args.report:
                    report["report_sha256"] = value_sha256(report)
                    write_json(args.report, report)
                print(f"Required baseline is missing: {args.baseline}", file=sys.stderr)
                return 1
        else:
            try:
                baseline = read_json(args.baseline)
            except (OSError, json.JSONDecodeError) as exc:
                print(f"Unable to read baseline: {exc}", file=sys.stderr)
                return 1
            baseline_errors = validate_inventory(baseline)
            if baseline_errors:
                print("Virality public mesh baseline validation: FAIL", file=sys.stderr)
                for error in baseline_errors:
                    print(f"- {error}", file=sys.stderr)
                return 1
            report = compare_inventory(current, baseline)

    if report is None:
        report = {
            "schema": "ct.report.virality-public-mesh-drift.v1",
            "inventory_id": INVENTORY_ID,
            "status": "valid_no_baseline_requested",
            "observed_at": current["source"]["source_timestamp"],
            "current_semantic_sha256": current["hashes"]["semantic_sha256"],
            "baseline_semantic_sha256": None,
            "changes": None,
        }
    report["route_index_coverage"] = coverage
    report["xml_estate_coverage"] = xml_coverage
    report["report_sha256"] = value_sha256(report)
    if args.report:
        write_json(args.report, report)

    print(
        "Virality public mesh validation: PASS; "
        f"status={report['status']} sha256={current['hashes']['semantic_sha256']}"
    )
    if args.fail_on_drift and report["status"] == "drift":
        print("Observed public mesh differs from the governed baseline.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
