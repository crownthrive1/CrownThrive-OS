#!/usr/bin/env python3
"""Fail-closed validator for the Sermon Toolkit final-directive control plane."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "developers"
    / "manifests"
    / "sermon-toolkit-final-directive-control-plane.v1.json"
)
DEFAULT_SCHEMA = (
    ROOT
    / "developers"
    / "schemas"
    / "sermon-toolkit-final-directive-control-plane.v1.schema.json"
)

EXPECTED_EVENT_TYPES = {
    "directive.registered",
    "patch.terminal",
    "source.recovered",
    "catalog.baselined",
    "article.gate.evaluated",
    "product.gate.evaluated",
    "commerce.certified",
    "integration.state_changed",
    "release.candidate.created",
    "release.certified",
    "rollback.executed",
}

EXPECTED_STRIPE_EVENTS = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "refund.created",
    "charge.dispute.created",
}

EXPECTED_NON_NEGOTIABLES = {
    "digital_only_notice": "DIGITAL PRODUCT ONLY. NO PHYSICAL ITEM WILL BE SHIPPED.",
    "physical_fulfillment": False,
    "shipping_workflows": False,
    "source_file_resale": False,
    "template_link_resale": False,
    "model_training_rights_by_default": False,
    "empty_product_cards": False,
    "placeholder_deliverables": False,
    "duplicate_inventory_inflation": False,
    "thin_article_quota_filler": False,
    "public_version_codes": False,
    "legacy_owner_access_loss": False,
    "private_spiritual_data_ad_targeting": False,
    "unverified_integration_claims": False,
    "unverified_machine_compatibility_claims": False,
    "fabricated_vast_url": False,
    "unverified_scripture_publication": False,
}

EXPECTED_RELEASE_GATES = {
    "patch_terminal_and_reconciled": ("unverified", True),
    "editable_source_recovered": ("failed", True),
    "public_discovery_routes": ("failed", True),
    "canonical_domain_ownership": ("unverified", True),
    "product_family_edition_reconciliation": ("failed", True),
    "stripe_checkout_current": ("failed", True),
    "webhook_signature_and_replay": ("unverified", True),
    "entitlement_issuance": ("failed", True),
    "rights_id_issuance": ("failed", True),
    "protected_download": ("failed", True),
    "license_terms_effective": ("unverified", True),
    "product_files_complete": ("failed", True),
    "machine_compatibility_evidence": ("failed", True),
    "canva_app_oauth": ("unverified", False),
    "scripture_source_checksum": ("unverified", True),
    "initial_24_articles": ("failed", True),
    "durable_schedules": ("defined_not_activated", True),
    "responsive_accessibility_performance": ("unverified", True),
    "security_privacy_restore": ("unverified", True),
    "rollback_manifest": ("unverified", True),
}

EXPECTED_GITHUB_DEPENDENCY = {
    "pull_request": 158,
    "observed_state": "open",
    "observed_draft": True,
    "observed_merged": False,
    "required_before": ["ready_for_review", "shared_surface_integration", "merge"],
    "enforcement": "workflow_blocks_non_draft_promotion_until_merged",
}

EXPECTED_PUBLIC_COUNTS = {
    "kjv_visualized_sitemap_urls": 2877,
    "kjv_visualized_read_detail_urls": 1189,
    "kjv_visualized_read_index_urls": 1,
    "kjv_visualized_store_detail_urls": 1004,
    "kjv_visualized_store_index_urls": 1,
    "kjv_visualized_open_sanctuary_detail_urls": 331,
    "kjv_visualized_open_sanctuary_index_urls": 1,
}

# These digests bind order and content for the canonical identity collections.
# The JSON Schema supplies shape/additional-property controls; these digests
# prevent same-shape substitutions from silently changing the v1 contract.
EXPECTED_CONTRACT_DIGESTS = {
    "routes": "d995e82419f03fd57952692e418bb4b858a6aa67c6e8321d9f3d4342f5ac3100",
    "licenses": "a07ab123d1c8bae6c20d540ef95755189a7858306af4c4962c0ddb9cd9eea597",
    "articles": "1b1be392eb124eedee81b3edcdb04bd28c8be4c496fe82c8544df45c4083af85",
    "families": "79c3053a33ba5594ba4d04f10fb6ebba7d8f472a3f4b0c92c35f922f1386353b",
    "gates": "094e5e81448c4938f1745d8d3cbc563cd56033ffcc8f9945acae1b73b92d927e",
    "integrations": "4cf8b76b655f103feffac233b46bf404c18c41286ebe8876e7c7bcb5fb00db62",
    "siblings": "d452e53a95997a51d5246a76607913d344b4644ad6133ebd15af598357ef6846",
    "jobs": "4103f5796a22f93e059018bbae3423e69b679c6ee652624ca8679418f41f666b",
    "non_negotiables": "a1a116ef6aff6d652b5d32944295e12043fc37e33a46e3a03ba086b25005db3e",
}

SCHEMA_KEYWORDS = {
    "$schema",
    "$id",
    "title",
    "description",
    "type",
    "const",
    "enum",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "uniqueItems",
    "pattern",
    "minLength",
    "minimum",
    "maximum",
}

SECRET_KEY_PATTERN = re.compile(
    r"(?:^|_)(?:api_key|access_token|refresh_token|client_secret|private_key|"
    r"secret_key|service_role_key|webhook_secret|password|passwd|bearer_token)(?:$|_)",
    flags=re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = {
    "private-key material": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "Stripe secret": re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    "Stripe webhook secret": re.compile(r"\bwhsec_[A-Za-z0-9]{16,}\b"),
    "OpenAI key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(
        r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"
    ),
    "AWS access key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    "JWT-like token": re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{10,}\b"
    ),
    "credential-bearing database URL": re.compile(
        r"\b(?:postgres(?:ql)?|mysql)://[^\s/:@]+:[^\s@]+@",
        flags=re.IGNORECASE,
    ),
}


class ValidationError(ValueError):
    """One or more control-plane invariants failed."""


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def as_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def json_equal(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)


def contract_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def unique(values: list[Any]) -> bool:
    fingerprints = [canonical_json(value) for value in values]
    return len(fingerprints) == len(set(fingerprints))


def validate_schema_definition(schema: Any, path: str = "$schema") -> None:
    """Fail closed if the bundled schema adds unsupported assertion keywords."""
    if isinstance(schema, bool):
        return
    if not isinstance(schema, dict):
        raise ValidationError(f"{path} must be a JSON Schema object or boolean")

    unsupported = sorted(set(schema) - SCHEMA_KEYWORDS)
    if unsupported:
        raise ValidationError(
            f"{path} contains unsupported JSON Schema keyword(s): {unsupported}"
        )

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ValidationError(f"{path}.properties must be an object")
    for name, child in properties.items():
        validate_schema_definition(child, f"{path}.properties[{name!r}]")

    if "items" in schema:
        validate_schema_definition(schema["items"], f"{path}.items")

    additional = schema.get("additionalProperties", True)
    if not isinstance(additional, (bool, dict)):
        raise ValidationError(
            f"{path}.additionalProperties must be a boolean or schema"
        )
    if isinstance(additional, dict):
        validate_schema_definition(additional, f"{path}.additionalProperties")

    expected_type = schema.get("type")
    if expected_type is not None:
        allowed_types = {
            "object",
            "array",
            "string",
            "integer",
            "number",
            "boolean",
            "null",
        }
        declared = (
            set(expected_type)
            if isinstance(expected_type, list)
            else {expected_type}
        )
        if not declared or not all(isinstance(item, str) for item in declared):
            raise ValidationError(f"{path}.type must contain JSON type names")
        unknown_types = sorted(declared - allowed_types)
        if unknown_types:
            raise ValidationError(f"{path}.type contains unknown types: {unknown_types}")

    pattern = schema.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise ValidationError(f"{path}.pattern must be a string")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValidationError(f"{path}.pattern is invalid: {exc}") from exc


def matches_json_type(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return (
            isinstance(instance, (int, float))
            and not isinstance(instance, bool)
            and math.isfinite(instance)
        )
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    return False


def validate_against_schema(
    instance: Any, schema: Any, path: str = "$"
) -> list[str]:
    """Execute the Draft 2020-12 keyword subset used by the bundled schema."""
    if schema is True:
        return []
    if schema is False:
        return [f"{path}: rejected by boolean false schema"]

    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None:
        declared = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(matches_json_type(instance, item) for item in declared):
            errors.append(f"{path}: expected JSON type {declared}")
            return errors

    if "const" in schema and not json_equal(instance, schema["const"]):
        errors.append(f"{path}: value does not match schema const")
    if "enum" in schema and not any(
        json_equal(instance, candidate) for candidate in schema["enum"]
    ):
        errors.append(f"{path}: value is not in schema enum")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for name in required:
                if name not in instance:
                    errors.append(f"{path}: missing required property {name!r}")

        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        for name, child_schema in properties.items():
            if name in instance:
                errors.extend(
                    validate_against_schema(
                        instance[name], child_schema, f"{path}.{name}"
                    )
                )

        extra_names = sorted(set(instance) - set(properties))
        additional = schema.get("additionalProperties", True)
        if additional is False:
            for name in extra_names:
                errors.append(f"{path}: additional property {name!r} is prohibited")
        elif isinstance(additional, dict):
            for name in extra_names:
                errors.extend(
                    validate_against_schema(
                        instance[name], additional, f"{path}.{name}"
                    )
                )

    if isinstance(instance, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(instance) < minimum:
            errors.append(f"{path}: contains fewer than {minimum} items")
        if isinstance(maximum, int) and len(instance) > maximum:
            errors.append(f"{path}: contains more than {maximum} items")
        if schema.get("uniqueItems") is True and not unique(instance):
            errors.append(f"{path}: array items must be unique")
        if "items" in schema:
            for index, value in enumerate(instance):
                errors.extend(
                    validate_against_schema(
                        value, schema["items"], f"{path}[{index}]"
                    )
                )

    if isinstance(instance, str):
        minimum_length = schema.get("minLength")
        if isinstance(minimum_length, int) and len(instance) < minimum_length:
            errors.append(f"{path}: string is shorter than {minimum_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            errors.append(f"{path}: string does not match the schema pattern")

    if (
        isinstance(instance, (int, float))
        and not isinstance(instance, bool)
        and math.isfinite(instance)
    ):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and instance < minimum:
            errors.append(f"{path}: number is below schema minimum {minimum}")
        if isinstance(maximum, (int, float)) and instance > maximum:
            errors.append(f"{path}: number exceeds schema maximum {maximum}")

    return errors


def find_secret_like_material(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = re.sub(r"[^A-Za-z0-9]+", "_", str(key)).strip("_")
            child_path = f"{path}.{key}"
            if SECRET_KEY_PATTERN.search(normalized_key):
                errors.append(f"{child_path}: secret-like key is prohibited")
            errors.extend(find_secret_like_material(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(find_secret_like_material(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for label, pattern in SECRET_VALUE_PATTERNS.items():
            if pattern.search(value):
                errors.append(f"{path}: possible {label} is prohibited")
    return errors


def require_contract_digest(name: str, value: Any, errors: list[str]) -> None:
    require(
        contract_digest(value) == EXPECTED_CONTRACT_DIGESTS[name],
        f"{name} canonical identities drifted",
        errors,
    )


def validate_manifest(
    data: dict[str, Any], schema: dict[str, Any] | None = None
) -> list[str]:
    if schema is None:
        schema = load_json_object(DEFAULT_SCHEMA)
        validate_schema_definition(schema)

    errors = validate_against_schema(data, schema)
    errors.extend(find_secret_like_material(data))

    directive = as_object(data.get("directive"))
    authority = as_object(data.get("authority"))
    evidence = as_object(data.get("current_evidence"))
    artifacts = as_object(data.get("artifacts"))

    require(data.get("schema_version") == "1.0.0", "schema_version must be 1.0.0", errors)
    require(
        data.get("manifest_id")
        == "ct.manifest.kjv-sermon.final-directive-control-plane.v1",
        "manifest_id is not canonical",
        errors,
    )
    require(directive.get("business_model") == "digital_only", "business model must remain digital_only", errors)
    require(directive.get("production_activation_authorized") is False, "production activation must remain false", errors)
    require(directive.get("final_release_certified") is False, "final release certification must remain false", errors)
    require(
        directive.get("phase_3_state") == "blocked_pending_phase_2_99_hard_exit",
        "Phase 3 must remain blocked",
        errors,
    )
    require(authority.get("agents_may_self_approve") is False, "agents may not self-approve", errors)
    require(authority.get("public_repo_secret_values_allowed") is False, "secret values may not enter the public repo", errors)

    non_negotiables = as_object(data.get("non_negotiables"))
    require(
        non_negotiables == EXPECTED_NON_NEGOTIABLES,
        "non-negotiables must exactly match the canonical digital-only contract",
        errors,
    )
    require_contract_digest("non_negotiables", non_negotiables, errors)

    github = as_object(evidence.get("github"))
    require(
        github.get("accessible_repository") == "crownthrive1/CrownThrive-Support",
        "current accessible repository is not pinned",
        errors,
    )
    require(
        github.get("base_sha") == "4bada510f8cc8b482ae9715180aa44aec552c077",
        "current main base SHA is not pinned to the reviewed base",
        errors,
    )
    require(
        github.get("branch_origin_sha")
        == "8fcb68bf209e32ba2cd265e1b6ca730cb8da64d7",
        "branch origin SHA is not preserved",
        errors,
    )
    require(
        github.get("collision_governor_dependency") == EXPECTED_GITHUB_DEPENDENCY,
        "PR #158 dependency contract drifted",
        errors,
    )
    require(github.get("all_repositories_connected") is False, "manifest must not claim all repositories are connected", errors)

    supabase = as_object(evidence.get("supabase"))
    require(
        supabase.get("directive_specific_database_write_applied") is False,
        "directive-specific Supabase writes must remain unapplied",
        errors,
    )
    require(
        supabase.get("existing_kjv_agent_id") == "ct.agent.kjv-room-release",
        "existing KJV agent binding is missing",
        errors,
    )

    stripe_evidence = as_object(evidence.get("stripe"))
    for key, expected in {
        "active_products": 373,
        "inactive_products": 22,
        "active_prices": 372,
        "inactive_prices": 19,
        "subscriptions_total": 4,
    }.items():
        require(stripe_evidence.get(key) == expected, f"Stripe baseline {key} drifted", errors)
    require(
        stripe_evidence.get("current_kjv_checkout_fulfillment_certified") is False,
        "KJV fulfillment may not be certified",
        errors,
    )

    public_surface = as_object(evidence.get("public_surface"))
    for key, expected in EXPECTED_PUBLIC_COUNTS.items():
        require(
            public_surface.get(key) == expected,
            f"public-surface baseline {key} drifted",
            errors,
        )

    drive = as_object(artifacts.get("google_drive_master"))
    require(drive.get("state") == "created_and_verified", "Google Drive master must be created and verified", errors)
    require(bool(drive.get("document_id")), "Google Drive master document_id is required", errors)
    require(
        str(drive.get("url", "")).startswith("https://docs.google.com/document/d/"),
        "Google Drive master URL is invalid",
        errors,
    )

    federation = as_object(data.get("repository_federation"))
    require(federation.get("direct_table_writes_allowed") is False, "federation direct table writes must remain prohibited", errors)
    federation_events = as_list(federation.get("event_types"))
    require(
        len(federation_events) == len(EXPECTED_EVENT_TYPES)
        and all(isinstance(item, str) for item in federation_events)
        and set(federation_events) == EXPECTED_EVENT_TYPES,
        "repository event contract is incomplete",
        errors,
    )
    require(
        federation.get("cross_repo_propagation_state")
        == "only_canonical_parent_connected_framework_child_pending",
        "cross-repo state must remain truthful",
        errors,
    )

    topology = as_object(data.get("agent_topology"))
    orchestrator = as_object(topology.get("orchestrator"))
    require(orchestrator.get("agent_id") == "ct.agent.kjv-room-release", "orchestrator must reuse the existing KJV binding", errors)
    require(orchestrator.get("vote_eligible") is False, "KJV orchestrator may not become a new sovereign voter", errors)
    require(orchestrator.get("certify_enabled") is False, "KJV orchestrator may not self-certify", errors)
    siblings = as_list(topology.get("projected_siblings"))
    require(len(siblings) == 16, "specialist sibling topology must contain 16 identities", errors)
    require_contract_digest("siblings", siblings, errors)

    jobs = as_list(data.get("scheduled_jobs"))
    require(len(jobs) == 7, "scheduled job contract must contain seven jobs", errors)
    require_contract_digest("jobs", jobs, errors)

    scheduler = as_object(data.get("scheduler_implementation"))
    for key, expected in {
        "durable_backend_required": True,
        "client_side_timer_allowed": False,
        "static_utc_cron_for_eastern_time_allowed": False,
        "dst_aware_dispatcher_required": True,
        "supabase_cron_activation_applied": False,
        "dead_letter_queue": True,
        "dry_run_required": True,
        "staging_required": True,
    }.items():
        require(scheduler.get(key) is expected, f"scheduler invariant {key} drifted", errors)

    integrations = as_list(data.get("integration_matrix"))
    integration_projection = [
        [
            as_object(item).get("provider"),
            as_object(item).get("state"),
            as_object(item).get("activation"),
        ]
        for item in integrations
    ]
    require(len(integrations) == 23, "integration matrix must contain 23 canonical providers", errors)
    require_contract_digest("integrations", integration_projection, errors)
    for item in integrations:
        provider = as_object(item)
        require(
            provider.get("secret_values_in_docs") is False,
            f"{provider.get('provider')} permits secret values in docs",
            errors,
        )

    advertising = as_object(data.get("advertising"))
    zone = as_object(advertising.get("verified_zone"))
    require(zone.get("zone_id") == 108420, "AdLuxe display zone evidence must stay pinned to 108420", errors)
    require(zone.get("placement_type") == "display_leaderboard", "zone 108420 may only be represented as display leaderboard", errors)
    require(zone.get("vast_capable") is False, "zone 108420 may not be represented as VAST-capable", errors)
    require(zone.get("vast_url") is None, "a VAST URL may not be fabricated", errors)

    stripe = as_object(data.get("stripe_contract"))
    require(stripe.get("checkout_surface") == "Stripe Checkout Sessions", "Stripe Checkout Sessions must be the checkout surface", errors)
    require(stripe.get("payment_method_types_parameter_allowed") is False, "payment_method_types must remain omitted", errors)
    require(stripe.get("shipping_address_collection_allowed") is False, "shipping address collection is prohibited", errors)
    require(stripe.get("shipping_options_allowed") is False, "shipping options are prohibited", errors)
    stripe_events = as_list(stripe.get("required_webhook_events"))
    require(
        len(stripe_events) == len(EXPECTED_STRIPE_EVENTS)
        and all(isinstance(item, str) for item in stripe_events)
        and set(stripe_events) == EXPECTED_STRIPE_EVENTS,
        "Stripe webhook event contract is incomplete",
        errors,
    )
    require(stripe.get("live_catalog_mutation_applied") is False, "live Stripe catalog mutation must remain unapplied", errors)

    routes = as_list(data.get("public_routes"))
    licenses = as_list(data.get("license_tiers"))
    articles = [
        [as_object(item).get("category"), as_object(item).get("title")]
        for item in as_list(data.get("initial_articles"))
    ]
    families = [
        [
            as_object(item).get("ordinal"),
            as_object(item).get("family_id"),
            as_object(item).get("name"),
        ]
        for item in as_list(data.get("product_families"))
    ]
    require(len(routes) == 36, "public route contract must contain 36 routes", errors)
    require(len(licenses) == 14, "license contract must contain 14 tiers", errors)
    require(len(articles) == 24, "article contract must contain 24 category/title pairs", errors)
    require(len(families) == 30, "product family contract must contain 30 identities", errors)
    require_contract_digest("routes", routes, errors)
    require_contract_digest("licenses", licenses, errors)
    require_contract_digest("articles", articles, errors)
    require_contract_digest("families", families, errors)

    gates = [as_object(item) for item in as_list(data.get("release_gates"))]
    gate_ids = [item.get("gate_id") for item in gates]
    require(len(gates) == 20, "release gate contract must contain 20 gates", errors)
    require(unique(gate_ids), "release gate IDs must be unique", errors)
    gate_map = {
        item.get("gate_id"): (item.get("state"), item.get("blocking"))
        for item in gates
    }
    require(
        gate_map == EXPECTED_RELEASE_GATES,
        "all release gate identities, states, and blocking controls must remain exact",
        errors,
    )
    gate_projection = [
        [item.get("gate_id"), item.get("state"), item.get("blocking")]
        for item in gates
    ]
    require_contract_digest("gates", gate_projection, errors)

    activation = as_object(data.get("activation_policy"))
    require(activation.get("fail_closed") is True, "activation policy must fail closed", errors)
    for key in (
        "publish_incomplete_products",
        "publish_unreviewed_articles",
        "activate_schedules_before_dry_run",
        "activate_integration_without_real_connection_test",
        "create_duplicate_stripe_records",
        "apply_supabase_ddl_in_this_change",
        "merge_or_deploy_in_this_change",
    ):
        require(activation.get(key) is False, f"activation policy {key} must be false", errors)

    impact = as_object(data.get("documentation_impact"))
    require(impact.get("outcome") == "docs_delta_opened", "documentation impact must be docs_delta_opened", errors)
    require(impact.get("shared_surface_updates_deferred") is True, "shared-surface updates must remain deferred", errors)

    return errors


def load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must contain a JSON object")
    return value


def validate_schema_reference(
    data: dict[str, Any], manifest_path: Path, schema_path: Path
) -> list[str]:
    reference = data.get("$schema")
    if not isinstance(reference, str) or not reference:
        return ["manifest $schema must be a non-empty relative path"]
    if "://" in reference:
        return ["manifest $schema must reference the bundled relative schema"]
    resolved = (manifest_path.resolve().parent / reference).resolve()
    if resolved != schema_path.resolve():
        return ["manifest $schema does not resolve to the bundled schema"]
    return []


def run_self_test(data: dict[str, Any], schema: dict[str, Any]) -> None:
    cases: list[tuple[str, Any]] = [
        (
            "production activation",
            lambda d: d["directive"].__setitem__(
                "production_activation_authorized", True
            ),
        ),
        (
            "VAST fabrication",
            lambda d: d["advertising"]["verified_zone"].__setitem__(
                "vast_url", "https://example.invalid/vast"
            ),
        ),
        (
            "schedule activation",
            lambda d: d["scheduled_jobs"][0].__setitem__("state", "active"),
        ),
        (
            "sibling substitution",
            lambda d: d["agent_topology"]["projected_siblings"][0].__setitem__(
                "agent_id", "ct.agent.kjv.substitute"
            ),
        ),
        (
            "job substitution",
            lambda d: d["scheduled_jobs"][0].__setitem__("queue", "other_queue"),
        ),
        (
            "route substitution",
            lambda d: d["public_routes"].__setitem__(0, "/substitute"),
        ),
        (
            "license substitution",
            lambda d: d["license_tiers"].__setitem__(0, "Substitute License"),
        ),
        (
            "article substitution",
            lambda d: d["initial_articles"][0].__setitem__("title", "Substitute"),
        ),
        (
            "product family substitution",
            lambda d: d["product_families"][0].__setitem__(
                "family_id", "ct.product-family.substitute"
            ),
        ),
        (
            "duplicate release gate",
            lambda d: d["release_gates"].append(
                copy.deepcopy(d["release_gates"][0])
            ),
        ),
        (
            "release gate pass",
            lambda d: d["release_gates"][0].__setitem__("state", "passed"),
        ),
        (
            "integration production_enabled",
            lambda d: d["integration_matrix"][1].__setitem__(
                "activation", "production_enabled"
            ),
        ),
        (
            "Google Drive production activation",
            lambda d: d["integration_matrix"][0].__setitem__(
                "activation", "production"
            ),
        ),
        (
            "integration production state",
            lambda d: d["integration_matrix"][1].__setitem__(
                "state", "production"
            ),
        ),
        (
            "integration provider substitution",
            lambda d: d["integration_matrix"][0].__setitem__(
                "provider", "Substitute Provider"
            ),
        ),
        (
            "unknown api_key",
            lambda d: d["current_evidence"].__setitem__(
                "api_key", "not-a-real-test-value"
            ),
        ),
        (
            "credential-shaped value",
            lambda d: d["current_evidence"]["github"].__setitem__(
                "base_sha", "sk_live_" + ("A" * 24)
            ),
        ),
        (
            "schema additional property",
            lambda d: d.__setitem__("unexpected_field", False),
        ),
    ]

    for key, expected in EXPECTED_NON_NEGOTIABLES.items():
        replacement = not expected if isinstance(expected, bool) else "altered notice"
        cases.append(
            (
                f"non-negotiable {key}",
                lambda d, key=key, replacement=replacement: d[
                    "non_negotiables"
                ].__setitem__(key, replacement),
            )
        )

    for label, mutator in cases:
        candidate = copy.deepcopy(data)
        mutator(candidate)
        if not validate_manifest(candidate, schema):
            raise ValidationError(f"self-test did not reject {label}")

    with tempfile.TemporaryDirectory() as tmpdir:
        sample = Path(tmpdir) / "sample.json"
        sample.write_text(json.dumps(data), encoding="utf-8")
        if load_json_object(sample).get("manifest_id") != data.get("manifest_id"):
            raise ValidationError("JSON round-trip self-test failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    try:
        data = load_json_object(args.manifest)
        schema = load_json_object(args.schema)
        validate_schema_definition(schema)
        errors = validate_schema_reference(data, args.manifest, args.schema)
        errors.extend(validate_manifest(data, schema))
        if args.self_test:
            run_self_test(data, schema)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, OverflowError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        "PASS: Sermon Toolkit directive manifest matches the bundled schema and "
        "fail-closed invariants; production remains inactive."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
