#!/usr/bin/env python3
"""Fail-closed validator for the Sermon Toolkit final-directive control plane."""

from __future__ import annotations

import argparse
import copy
import json
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

REQUIRED_EVENT_TYPES = {
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

REQUIRED_STRIPE_EVENTS = {
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

EXPECTED_JOBS = {
    "ct.job.kjv.daily-research-scan": "0 2 * * *",
    "ct.job.kjv.product-intelligence": "0 6 * * 1",
    "ct.job.kjv.tuesday-publishing": "0 5 * * 2",
    "ct.job.kjv.compatibility": "0 3 * * 3",
    "ct.job.kjv.product-gate": "0 6 * * 4",
    "ct.job.kjv.friday-publishing": "0 5 * * 5",
    "ct.job.kjv.refresh": "0 4 * * 0",
}

EXPECTED_ARTICLE_COUNTS = {
    "KJV Visual Bible": 4,
    "Sermon Preparation and Teaching": 4,
    "Prayer, Devotion, and Spiritual Formation": 4,
    "Family, Youth, and Sunday School": 4,
    "Church Leadership and Pastoral Care": 4,
    "Faith-Based Design, Craft, and Maker Business": 4,
}

REQUIRED_BLOCKING_GATES = {
    "editable_source_recovered",
    "public_discovery_routes",
    "stripe_checkout_current",
    "entitlement_issuance",
    "rights_id_issuance",
    "protected_download",
    "product_files_complete",
    "scripture_source_checksum",
    "initial_24_articles",
    "durable_schedules",
}

PROHIBITED_ACTIVE_WORDS = {"active", "enabled", "connected", "certified", "production"}


class ValidationError(ValueError):
    """One or more control-plane invariants failed."""


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def unique(values: list[Any]) -> bool:
    return len(values) == len(set(values))


def validate_manifest(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    directive = data.get("directive", {})
    authority = data.get("authority", {})
    evidence = data.get("current_evidence", {})
    artifacts = data.get("artifacts", {})

    require(data.get("schema_version") == "1.0.0", "schema_version must be 1.0.0", errors)
    require(
        data.get("manifest_id") == "ct.manifest.kjv-sermon.final-directive-control-plane.v1",
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

    non_negotiables = data.get("non_negotiables", {})
    require(
        non_negotiables.get("digital_only_notice")
        == "DIGITAL PRODUCT ONLY. NO PHYSICAL ITEM WILL BE SHIPPED.",
        "required digital-only notice is missing or altered",
        errors,
    )
    for key in (
        "physical_fulfillment",
        "shipping_workflows",
        "empty_product_cards",
        "placeholder_deliverables",
        "duplicate_inventory_inflation",
        "public_version_codes",
        "legacy_owner_access_loss",
        "private_spiritual_data_ad_targeting",
        "unverified_integration_claims",
        "unverified_machine_compatibility_claims",
        "fabricated_vast_url",
        "unverified_scripture_publication",
    ):
        require(non_negotiables.get(key) is False, f"non-negotiable {key} must be false", errors)

    github = evidence.get("github", {})
    require(
        github.get("accessible_repository") == "crownthrive1/CrownThrive-Support",
        "current accessible repository is not pinned",
        errors,
    )
    require(github.get("all_repositories_connected") is False, "manifest must not claim all repositories are connected", errors)

    supabase = evidence.get("supabase", {})
    require(supabase.get("directive_specific_database_write_applied") is False, "directive-specific Supabase writes must remain unapplied", errors)
    require(supabase.get("existing_kjv_agent_id") == "ct.agent.kjv-room-release", "existing KJV agent binding is missing", errors)

    stripe_evidence = evidence.get("stripe", {})
    require(stripe_evidence.get("active_products") == 373, "Stripe active product baseline drifted", errors)
    require(stripe_evidence.get("inactive_products") == 22, "Stripe inactive product baseline drifted", errors)
    require(stripe_evidence.get("active_prices") == 372, "Stripe active price baseline drifted", errors)
    require(stripe_evidence.get("inactive_prices") == 19, "Stripe inactive price baseline drifted", errors)
    require(stripe_evidence.get("subscriptions_total") == 4, "Stripe subscription baseline drifted", errors)
    require(stripe_evidence.get("current_kjv_checkout_fulfillment_certified") is False, "KJV fulfillment may not be certified", errors)

    drive = artifacts.get("google_drive_master", {})
    require(drive.get("state") == "created_and_verified", "Google Drive master must be created and verified", errors)
    require(bool(drive.get("document_id")), "Google Drive master document_id is required", errors)
    require(str(drive.get("url", "")).startswith("https://docs.google.com/document/d/"), "Google Drive master URL is invalid", errors)

    federation = data.get("repository_federation", {})
    require(federation.get("direct_table_writes_allowed") is False, "federation direct table writes must remain prohibited", errors)
    require(set(federation.get("event_types", [])) == REQUIRED_EVENT_TYPES, "repository event contract is incomplete", errors)
    require(
        federation.get("cross_repo_propagation_state")
        == "only_canonical_parent_connected_framework_child_pending",
        "cross-repo state must remain truthful",
        errors,
    )

    topology = data.get("agent_topology", {})
    orchestrator = topology.get("orchestrator", {})
    require(orchestrator.get("agent_id") == "ct.agent.kjv-room-release", "orchestrator must reuse the existing KJV binding", errors)
    require(orchestrator.get("vote_eligible") is False, "KJV orchestrator may not become a new sovereign voter", errors)
    require(orchestrator.get("certify_enabled") is False, "KJV orchestrator may not self-certify", errors)
    siblings = topology.get("projected_siblings", [])
    require(len(siblings) >= 12, "specialist sibling topology is incomplete", errors)
    sibling_ids = [item.get("agent_id") for item in siblings]
    require(unique(sibling_ids), "projected sibling IDs must be unique", errors)
    for item in siblings:
        require(item.get("state") == "planned_not_registered", f"{item.get('agent_id')} must remain planned", errors)
        require(item.get("vote_eligible") is False, f"{item.get('agent_id')} may not vote", errors)
        require(item.get("authority_ceiling") in {"D0", "D1", "D2"}, f"{item.get('agent_id')} has excessive authority", errors)

    jobs = data.get("scheduled_jobs", [])
    require(len(jobs) == len(EXPECTED_JOBS), "scheduled job count must be seven", errors)
    require(unique([job.get("job_id") for job in jobs]), "scheduled job IDs must be unique", errors)
    for job in jobs:
        job_id = job.get("job_id")
        require(job_id in EXPECTED_JOBS, f"unexpected scheduled job {job_id}", errors)
        require(job.get("local_cron") == EXPECTED_JOBS.get(job_id), f"cron drift for {job_id}", errors)
        require(job.get("timezone") == "America/New_York", f"timezone drift for {job_id}", errors)
        require(job.get("state") == "defined_not_activated", f"{job_id} must remain inactive", errors)
        require(bool(job.get("idempotency_template")), f"{job_id} needs an idempotency template", errors)
        require(job.get("max_runtime_minutes", 999) <= 10, f"{job_id} exceeds the ten-minute job envelope", errors)

    scheduler = data.get("scheduler_implementation", {})
    require(scheduler.get("durable_backend_required") is True, "durable backend is required", errors)
    require(scheduler.get("client_side_timer_allowed") is False, "client-side scheduling is prohibited", errors)
    require(scheduler.get("static_utc_cron_for_eastern_time_allowed") is False, "static UTC schedules may not impersonate Eastern time", errors)
    require(scheduler.get("dst_aware_dispatcher_required") is True, "DST-aware dispatch is required", errors)
    require(scheduler.get("supabase_cron_activation_applied") is False, "Supabase cron activation must remain unapplied", errors)
    require(scheduler.get("dead_letter_queue") is True, "dead-letter queue is required", errors)
    require(scheduler.get("dry_run_required") is True, "dry run is required", errors)
    require(scheduler.get("staging_required") is True, "staging is required", errors)

    integrations = data.get("integration_matrix", [])
    require(len(integrations) >= 20, "integration matrix is incomplete", errors)
    require(unique([item.get("provider") for item in integrations]), "integration providers must be unique", errors)
    for item in integrations:
        require(item.get("secret_values_in_docs") is False, f"{item.get('provider')} permits secret values in docs", errors)
        activation = str(item.get("activation", "")).lower()
        if item.get("provider") not in {"Google Drive"}:
            require(
                activation not in PROHIBITED_ACTIVE_WORDS,
                f"{item.get('provider')} is represented as universally active",
                errors,
            )

    advertising = data.get("advertising", {})
    zone = advertising.get("verified_zone", {})
    require(zone.get("zone_id") == 108420, "AdLuxe display zone evidence must stay pinned to 108420", errors)
    require(zone.get("placement_type") == "display_leaderboard", "zone 108420 may only be represented as display leaderboard", errors)
    require(zone.get("vast_capable") is False, "zone 108420 may not be represented as VAST-capable", errors)
    require(zone.get("vast_url") is None, "a VAST URL may not be fabricated", errors)

    stripe = data.get("stripe_contract", {})
    require(stripe.get("checkout_surface") == "Stripe Checkout Sessions", "Stripe Checkout Sessions must be the checkout surface", errors)
    require(stripe.get("payment_method_types_parameter_allowed") is False, "payment_method_types must remain omitted", errors)
    require(stripe.get("shipping_address_collection_allowed") is False, "shipping address collection is prohibited", errors)
    require(stripe.get("shipping_options_allowed") is False, "shipping options are prohibited", errors)
    require(set(stripe.get("required_webhook_events", [])) == REQUIRED_STRIPE_EVENTS, "Stripe webhook event contract is incomplete", errors)
    require(stripe.get("live_catalog_mutation_applied") is False, "live Stripe catalog mutation must remain unapplied", errors)

    routes = data.get("public_routes", [])
    require(len(routes) == 36, "public route contract must contain 36 routes", errors)
    require(unique(routes), "public routes must be unique", errors)
    for route in ("/", "/articles", "/store", "/pricing", "/licenses", "/accessibility"):
        require(route in routes, f"required public route {route} is missing", errors)

    licenses = data.get("license_tiers", [])
    require(len(licenses) == 14, "license tier contract must contain 14 tiers", errors)
    require(unique(licenses), "license tiers must be unique", errors)

    articles = data.get("initial_articles", [])
    require(len(articles) == 24, "initial article manifest must contain 24 articles", errors)
    require(unique([a.get("title") for a in articles]), "article titles must be unique", errors)
    counts: dict[str, int] = {}
    for article in articles:
        counts[article.get("category", "")] = counts.get(article.get("category", ""), 0) + 1
    require(counts == EXPECTED_ARTICLE_COUNTS, "article categories must contain four titles each", errors)

    families = data.get("product_families", [])
    require(len(families) == 30, "product family manifest must contain 30 families", errors)
    require([item.get("ordinal") for item in families] == list(range(1, 31)), "product family ordinals must be 1..30", errors)
    require(unique([item.get("family_id") for item in families]), "product family IDs must be unique", errors)
    require(unique([item.get("name") for item in families]), "product family names must be unique", errors)
    for family in families:
        require(family.get("state") == "blocked_incomplete", f"{family.get('family_id')} must remain blocked", errors)

    gates = data.get("release_gates", [])
    gate_map = {gate.get("gate_id"): gate for gate in gates}
    require(REQUIRED_BLOCKING_GATES.issubset(gate_map), "required release gates are missing", errors)
    for gate_id in REQUIRED_BLOCKING_GATES:
        require(gate_map.get(gate_id, {}).get("blocking") is True, f"{gate_id} must remain blocking", errors)
        require(gate_map.get(gate_id, {}).get("state") not in {"passed", "certified"}, f"{gate_id} cannot pass in this manifest", errors)

    activation = data.get("activation_policy", {})
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

    impact = data.get("documentation_impact", {})
    require(impact.get("outcome") == "docs_delta_opened", "documentation impact must be docs_delta_opened", errors)
    require(impact.get("shared_surface_updates_deferred") is True, "shared-surface updates must remain deferred", errors)

    return errors


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_self_test(data: dict[str, Any]) -> None:
    cases: list[tuple[str, Any]] = [
        ("production activation", lambda d: d["directive"].__setitem__("production_activation_authorized", True)),
        ("shipping", lambda d: d["non_negotiables"].__setitem__("shipping_workflows", True)),
        ("VAST fabrication", lambda d: d["advertising"]["verified_zone"].__setitem__("vast_url", "https://example.invalid/vast")),
        ("schedule activation", lambda d: d["scheduled_jobs"][0].__setitem__("state", "active")),
        ("sibling vote", lambda d: d["agent_topology"]["projected_siblings"][0].__setitem__("vote_eligible", True)),
        ("product activation", lambda d: d["product_families"][0].__setitem__("state", "active")),
    ]
    for label, mutator in cases:
        candidate = copy.deepcopy(data)
        mutator(candidate)
        if not validate_manifest(candidate):
            raise ValidationError(f"self-test did not reject {label}")

    with tempfile.TemporaryDirectory() as tmpdir:
        sample = Path(tmpdir) / "sample.json"
        sample.write_text(json.dumps(data), encoding="utf-8")
        if load_manifest(sample).get("manifest_id") != data.get("manifest_id"):
            raise ValidationError("JSON round-trip self-test failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    try:
        data = load_manifest(args.manifest)
        if args.self_test:
            run_self_test(data)
        errors = validate_manifest(data)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        "PASS: Sermon Toolkit final-directive control plane is complete, "
        "fail-closed, non-activating, and internally consistent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
