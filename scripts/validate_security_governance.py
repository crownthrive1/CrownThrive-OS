#!/usr/bin/env python3
"""Validate deterministic CrownThrive security-governance controls.

This complements GitHub provider-managed CodeQL default setup, dependency
review, and provider secret scanning. It never synthesizes a provider scan pass.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "developers/manifests/security-self-healing-policy.v1.json"
ACTIONS_POLICY = ROOT / "developers/manifests/github-actions-runtime-policy.v1.json"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security-governance.yml"
PROVIDER_TRUSTED_WORKFLOW = ROOT / ".github/workflows/penta-provider-control-plane.yml"
PROVIDER_CONTRACT_WORKFLOW = ROOT / ".github/workflows/penta-provider-contract.yml"
CPANEL_ADAPTER = (
    ROOT
    / "software-factory-v3/supabase/functions/ct-factory-cpanel-adapter/index.ts"
)
CPANEL_EXPOSURE_RESPONSE = (
    ROOT
    / "developers/manifests/cpanel-public-locator-exposure-response.v1.json"
)
PROVIDER_RELEASE_HOLDS = (
    ROOT / "developers/manifests/provider-release-security-holds.v1.json"
)

PROVIDER_PR_EVENTS = {"pull_request", "pull_request_target"}
PROVIDER_TRUST_GUARD = (
    "github.repository == 'crownthrive1/CrownThrive-Support' "
    "&& github.ref == 'refs/heads/main'"
)
SECRET_CONTEXT_RE = re.compile(r"\$\{\{\s*secrets(?:\.|\[)")
SECRET_INHERIT_RE = re.compile(r"(?m)^\s*secrets\s*:\s*inherit\s*(?:#.*)?$")
PROVIDER_ENV_ALIAS_RE = re.compile(r"(?m)^\s*env\s*:\s*\*provider-env\s*(?:#.*)?$")
GITHUB_TOKEN_CONTEXT_RE = re.compile(r"\$\{\{\s*github\.token\s*\}\}")
SECRET_LIKE_LITERAL_ASSIGNMENT_RE = re.compile(
    r"(?m)^\s*const\s+([A-Za-z0-9_]*(?:secret|token|password|api_?key)[A-Za-z0-9_]*)"
    r"\s*=\s*(['\"`])([^\n'\"`]{8,})\2\s*;",
    flags=re.IGNORECASE,
)

SECRET_PATTERNS = {
    "github_classic_pat": re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
    "github_fine_grained_pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "openai_project_key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
    "stripe_live_secret": re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
}
SCAN_SUFFIXES = {".py", ".json", ".yml", ".yaml", ".md", ".mdx", ".ts", ".js"}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def workflow_events(workflow: str) -> set[str]:
    """Return literal top-level events from the repository's governed YAML profile."""
    lines = workflow.splitlines()
    try:
        on_index = next(
            index
            for index, line in enumerate(lines)
            if re.fullmatch(r"on:\s*(?:#.*)?", line)
        )
    except StopIteration:
        return set()

    events: set[str] = set()
    for line in lines[on_index + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indentation = len(line) - len(line.lstrip(" "))
        if indentation == 0:
            break
        match = re.match(r"^  ([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(?:#.*)?$", line)
        if match:
            events.add(match.group(1))
    return events


def workflow_job_blocks(workflow: str) -> dict[str, str]:
    """Split literal two-space GitHub Actions job blocks without a YAML dependency."""
    lines = workflow.splitlines()
    try:
        jobs_index = next(index for index, line in enumerate(lines) if line == "jobs:")
    except StopIteration:
        return {}

    starts: list[tuple[int, str]] = []
    for index in range(jobs_index + 1, len(lines)):
        line = lines[index]
        if line and not line.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
        if match:
            starts.append((index, match.group(1)))

    blocks: dict[str, str] = {}
    for offset, (start, job_id) in enumerate(starts):
        end = starts[offset + 1][0] if offset + 1 < len(starts) else len(lines)
        blocks[job_id] = "\n".join(lines[start:end])
    return blocks


def provider_workflow_boundary_errors(trusted: str, contract: str) -> list[str]:
    """Validate that PR code and provider credentials occupy disjoint workflows."""
    errors: list[str] = []
    trusted_events = workflow_events(trusted)
    contract_events = workflow_events(contract)

    if not trusted_events:
        errors.append("trusted provider workflow has no parseable events")
    if trusted_events & PROVIDER_PR_EVENTS:
        errors.append("trusted provider workflow must not accept pull-request events")
    if not {"workflow_dispatch", "push", "schedule"}.issubset(trusted_events):
        errors.append("trusted provider workflow must retain manual, exact-main push, and schedule events")

    if contract_events != {"pull_request"}:
        errors.append("provider contract workflow must be pull_request-only")

    contract_credential_markers = (
        SECRET_CONTEXT_RE.search(contract),
        SECRET_INHERIT_RE.search(contract),
        PROVIDER_ENV_ALIAS_RE.search(contract),
        GITHUB_TOKEN_CONTEXT_RE.search(contract),
    )
    if any(contract_credential_markers):
        errors.append("provider contract workflow must not reference credentials or inherited secrets")
    if re.search(r"(?m)^\s*id-token\s*:\s*write\s*(?:#.*)?$", contract):
        errors.append("provider contract workflow must not mint OIDC tokens")
    if re.search(r"(?m)^\s*[A-Za-z0-9_-]+\s*:\s*write\s*(?:#.*)?$", contract):
        errors.append("provider contract workflow permissions must remain read-only")
    if not re.search(r"(?m)^\s*contents\s*:\s*read\s*(?:#.*)?$", contract):
        errors.append("provider contract workflow must retain contents: read")
    if re.search(r"(?m)^\s*environment\s*:", contract):
        errors.append("provider contract workflow must not attach a provider environment")

    checkout_count = contract.count("actions/checkout@")
    non_persistent_checkout_count = len(
        re.findall(r"(?m)^\s*persist-credentials\s*:\s*false\s*(?:#.*)?$", contract)
    )
    if checkout_count == 0 or checkout_count != non_persistent_checkout_count:
        errors.append("every provider contract checkout must disable persisted credentials")
    if "PENTA_DISABLE_NETWORK_PROBES: '1'" not in contract:
        errors.append("provider contract workflow must explicitly disable network probes")
    for fragment in (
        "python3 scripts/validate_security_governance.py",
        "python3 -m unittest -v tests.test_provider_workflow_secret_boundary",
        "python3 scripts/validate_penta_provider_control_plane.py",
    ):
        if fragment not in contract:
            errors.append(f"provider contract workflow missing {fragment!r}")

    secret_job_count = 0
    for job_id, block in workflow_job_blocks(trusted).items():
        secret_bearing = bool(
            SECRET_CONTEXT_RE.search(block)
            or SECRET_INHERIT_RE.search(block)
            or PROVIDER_ENV_ALIAS_RE.search(block)
        )
        if not secret_bearing:
            continue
        secret_job_count += 1
        if PROVIDER_TRUST_GUARD not in block:
            errors.append(f"trusted secret-bearing job {job_id!r} lacks exact-main repository guard")
        if not re.search(
            r"(?m)^\s*environment\s*:\s*penta-provider-production\s*(?:#.*)?$",
            block,
        ):
            errors.append(f"trusted secret-bearing job {job_id!r} lacks provider environment gate")
        if "ref: refs/heads/main" not in block:
            errors.append(f"trusted secret-bearing job {job_id!r} does not check out exact main")
        if "persist-credentials: false" not in block:
            errors.append(f"trusted secret-bearing job {job_id!r} persists checkout credentials")

    if secret_job_count == 0:
        errors.append("trusted provider workflow contains no governed secret-bearing job")

    live_job = workflow_job_blocks(trusted).get("provider-live-readback", "")
    if not live_job:
        errors.append("trusted provider workflow is missing provider-live-readback job")
    else:
        if re.search(r"(?m)^\s*continue-on-error\s*:", live_job):
            errors.append("provider live certification must not tolerate probe errors")
        for fragment in (
            "if cert.state not in {'CERTIFIED', 'WRITE_VERIFIED'}:",
            "if gate.get('state') == 'HOLD' or not gate.get('eligible'):",
            "raise SystemExit(78)",
            "if: always()",
            "steps.certify.outcome",
        ):
            if fragment not in live_job:
                errors.append(f"provider live certification missing fail-closed fragment {fragment!r}")
    return errors


def cpanel_adapter_boundary_errors(adapter: str) -> list[str]:
    """Return public-source and provider-error boundary violations."""
    errors: list[str] = []

    for identifier, _quote, _value in SECRET_LIKE_LITERAL_ASSIGNMENT_RE.findall(adapter):
        if not identifier.upper().endswith("_ENV"):
            errors.append(
                f"cPanel adapter hard-codes a secret-like literal in {identifier!r}"
            )

    required_fragments = (
        'const CPANEL_USERNAME_ENV = "CPANEL_UAPI_USERNAME";',
        'const CPANEL_SECRET_NAME_ENV = "CPANEL_RUNTIME_SECRET_NAME";',
        "const secretName = requiredBinding(CPANEL_SECRET_NAME_ENV);",
        "const username = requiredBinding(CPANEL_USERNAME_ENV);",
        "const token = await runtimeSecret();",
        "body: JSON.stringify({ secret_name: secretName }),",
        '(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "").trim()',
        "if (!token) return jsonResponse({ ok: false, error: \"cpanel_token_unavailable\" }, 503);",
        "const SAFE_BUILD_RUN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;",
        "const MAX_PROVIDER_RESPONSE_BYTES = 1_000_000;",
        'return jsonResponse({ ok: false, error: "internal_adapter_error" }, 500);',
    )
    for fragment in required_fragments:
        if fragment not in adapter:
            errors.append(f"cPanel adapter missing fail-closed fragment {fragment!r}")

    if re.search(
        r"(?m)^\s*(?:provider_)?(?:errors|messages)\s*:\s*writeJson\.(?:errors|messages)",
        adapter,
    ):
        errors.append("cPanel adapter must not return raw provider errors or messages")
    if re.search(r"\bconsole\.(?:debug|error|info|log|warn)\s*\(", adapter):
        errors.append("cPanel adapter must not log credential-bearing provider traffic")
    if re.search(r"catch\s*\([^)]*\)\s*\{[^}]*internal_adapter_error", adapter, re.DOTALL):
        errors.append("cPanel adapter terminal error boundary must not capture throwable details")

    return errors


def cpanel_exposure_response_errors(record: dict[str, object]) -> list[str]:
    """Validate that the public incident record remains value-free and release-blocking."""
    errors: list[str] = []
    incident = record.get("incident", {})
    binding = record.get("hardened_runtime_binding", {})
    release = record.get("release_predicate", {})
    closure = record.get("closure_evidence", [])
    checklist = record.get("remediation_checklist", [])
    provider = record.get("authenticated_provider_readback", {})

    if record.get("state") != "HOLD_EXTERNAL_ROTATION_AND_LOG_REVIEW":
        errors.append("cPanel exposure response must retain external rotation/log-review HOLD")
    if not isinstance(incident, dict) or incident.get("raw_value_or_fingerprint_publication") != "prohibited":
        errors.append("cPanel response must prohibit publishing the locator or its fingerprint")
    if not isinstance(binding, dict) or binding.get("secret_locator_environment_variable") != "CPANEL_RUNTIME_SECRET_NAME":
        errors.append("cPanel response must bind the replacement locator through CPANEL_RUNTIME_SECRET_NAME")
    if not isinstance(binding, dict) or binding.get("literal_locator_in_public_source") is not False:
        errors.append("cPanel response must record zero literal locator in candidate source")
    if not isinstance(release, dict) or release.get("current_state") != "HOLD":
        errors.append("cPanel major-release predicate must remain HOLD")
    if not isinstance(release, dict) or release.get("major_release_blocked") is not True:
        errors.append("cPanel response must block the major release pending external closure")
    if not isinstance(release, dict) or release.get("history_rewrite_or_provider_mutation_performed_by_this_change") is not False:
        errors.append("cPanel source response must not claim history rewrite or provider mutation")
    if not isinstance(closure, list) or len(closure) < 7:
        errors.append("cPanel response closure evidence is incomplete")
    if not isinstance(checklist, list) or len(checklist) < 10:
        errors.append("cPanel response remediation/log-review checklist is incomplete")
    if not isinstance(provider, dict) or provider.get("evidence_mode") != "read_only":
        errors.append("cPanel provider evidence must remain read-only")
    if not isinstance(provider, dict) or provider.get("vault_locator_name_matches") != 1:
        errors.append("cPanel response must retain the one-match Vault observation")
    if not isinstance(provider, dict) or provider.get("vault_match_method") != "restricted_fingerprint_comparison_value_and_fingerprint_not_recorded":
        errors.append("cPanel response must keep Vault comparison evidence public-safe")
    if not isinstance(provider, dict) or provider.get("vault_record_created_at") != "2026-08-22T03:53:31.769008Z":
        errors.append("cPanel response must retain the observed Vault creation time")
    if not isinstance(provider, dict) or provider.get("vault_record_updated_at") != provider.get("vault_record_created_at"):
        errors.append("cPanel response must retain the observed absence of locator rotation")
    if not isinstance(provider, dict) or provider.get("rotation_observed_since_creation") is not False:
        errors.append("cPanel response must not claim locator rotation occurred")
    if not isinstance(provider, dict) or provider.get("get_runtime_secret_definition_has_insert_or_audit_logging") is not False:
        errors.append("cPanel response must retain the RPC audit-logging gap")
    if not isinstance(provider, dict) or provider.get("deployed_edge_function_version") != "3":
        errors.append("cPanel response must retain the observed deployed function version")
    if not isinstance(provider, dict) or provider.get("deployed_runtime_byte_relation") != "byte_identical_to_latest_observed_public_main":
        errors.append("cPanel response must retain the deployed/public-main byte relation")
    if not isinstance(provider, dict) or provider.get("hardened_environment_bound_candidate_deployed") is not False:
        errors.append("cPanel response must not claim the hardened candidate is deployed")
    if not isinstance(provider, dict) or provider.get("returned_edge_log_window_hours") != 24:
        errors.append("cPanel response must retain the bounded 24-hour log observation")
    if not isinstance(provider, dict) or provider.get("returned_log_sources") != ["edge", "postgres"]:
        errors.append("cPanel response must retain the observed log-source boundary")
    if not isinstance(provider, dict) or provider.get("returned_function_reference_count") != 0:
        errors.append("cPanel response must retain the zero-reference provider observation")
    if not isinstance(provider, dict) or provider.get("zero_reference_interpretation") != "bounded_observation_only_cannot_prove_no_secret_reads":
        errors.append("cPanel response must not overclaim the quiet provider log window")
    if not isinstance(release, dict) or release.get("target_release") != "v4":
        errors.append("cPanel response must bind closure to the v4 release predicate")
    if not isinstance(release, dict) or release.get("v4_release_blocked") is not True:
        errors.append("cPanel response must block v4 pending provider closure")

    forbidden_keys = {"locator_value", "locator_fingerprint", "secret_value", "token_value"}
    pending: list[object] = [record]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in forbidden_keys:
                    errors.append(f"cPanel public response contains forbidden sensitive key {key!r}")
                pending.append(child)
        elif isinstance(value, list):
            pending.extend(value)
    return errors


def provider_release_hold_errors(record: dict[str, object]) -> list[str]:
    """Validate independent provider-migration and Deno supply-chain HOLDs."""
    errors: list[str] = []
    migration = record.get("supabase_migration_lineage", {})
    deno = record.get("deno_dependency_boundary", {})
    advisory = record.get("supabase_advisory_snapshot", {})
    release = record.get("release_predicate", {})

    if record.get("state") != "HOLD_NO_DB_PUSH_AND_UNPINNED_DENO_DEPENDENCIES":
        errors.append("provider security boundary must retain the combined HOLD")
    if not isinstance(migration, dict) or migration.get("state") != "HOLD_NO_DB_PUSH":
        errors.append("provider migration lineage must retain HOLD_NO_DB_PUSH")
    if not isinstance(migration, dict) or migration.get("provider_applied_versions_differ_from_local_source_filename_versions") is not True:
        errors.append("provider migration version mismatch must remain explicit")
    if not isinstance(migration, dict) or migration.get("local_to_provider_one_to_one_lineage_proven") is not False:
        errors.append("provider migration lineage must not be claimed proven")
    prohibited = migration.get("prohibited_effects", []) if isinstance(migration, dict) else []
    if "supabase_db_push" not in prohibited or "provider_state_mutation" not in prohibited:
        errors.append("provider migration HOLD must prohibit db push and provider mutation")
    migration_closure = migration.get("required_closure_evidence", []) if isinstance(migration, dict) else []
    if not isinstance(migration_closure, list) or len(migration_closure) < 6:
        errors.append("provider migration closure evidence is incomplete")

    if not isinstance(deno, dict) or deno.get("state") != "HOLD_NO_LOCK_AND_NONEXACT_IMPORTS":
        errors.append("Deno dependency boundary must retain its supply-chain HOLD")
    if not isinstance(deno, dict) or deno.get("deno_lock_present") is not False:
        errors.append("Deno dependency record must not claim a lockfile exists")
    for key in (
        "unversioned_jsr_imports_present",
        "major_only_npm_imports_present",
        "major_only_esm_sh_imports_present",
    ):
        if not isinstance(deno, dict) or deno.get(key) is not True:
            errors.append(f"Deno dependency record must retain {key}")
    deno_closure = deno.get("required_closure_evidence", []) if isinstance(deno, dict) else []
    if not isinstance(deno_closure, list) or len(deno_closure) < 5:
        errors.append("Deno dependency closure evidence is incomplete")

    if (ROOT / "deno.lock").exists():
        errors.append("Deno dependency HOLD is stale because a root lockfile now exists")
    deno_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in ROOT.rglob("*.ts")
        if ".git" not in path.parts
    )
    for fragment in (
        "jsr:@supabase/functions-js/edge-runtime.d.ts",
        "npm:@supabase/supabase-js@2",
        "https://esm.sh/@supabase/supabase-js@2",
    ):
        if fragment not in deno_sources:
            errors.append(f"Deno dependency HOLD evidence drifted for {fragment!r}")

    security_advisory = advisory.get("security", {}) if isinstance(advisory, dict) else {}
    performance_advisory = advisory.get("performance", {}) if isinstance(advisory, dict) else {}
    if not isinstance(advisory, dict) or advisory.get("state") != "HOLD_INHERITED_PERFORMANCE_AND_REVIEW":
        errors.append("Supabase advisory snapshot must retain inherited review HOLD")
    if not isinstance(security_advisory, dict) or security_advisory.get("total") != 188:
        errors.append("Supabase security advisory count drifted")
    if not isinstance(security_advisory, dict) or security_advisory.get("category") != "rls_enabled_no_policy":
        errors.append("Supabase security advisory classification drifted")
    if not isinstance(security_advisory, dict) or security_advisory.get("interpretation") != "fail_closed_no_policy_not_by_itself_public_exposure":
        errors.append("Supabase security advisory interpretation must remain bounded")
    expected_performance = {
        "total": 877,
        "unindexed_foreign_keys": 409,
        "tables_without_primary_key": 3,
        "unused_indexes": 464,
        "auth_absolute_connection_setting": 1,
    }
    if not isinstance(performance_advisory, dict) or any(
        performance_advisory.get(key) != value
        for key, value in expected_performance.items()
    ):
        errors.append("Supabase performance advisory snapshot drifted")
    if not isinstance(advisory, dict) or advisory.get("provider_changes_performed") is not False:
        errors.append("Supabase advisory snapshot must not claim provider changes")
    advisory_closure = advisory.get("required_closure_evidence", []) if isinstance(advisory, dict) else []
    if not isinstance(advisory_closure, list) or len(advisory_closure) < 5:
        errors.append("Supabase advisory closure evidence is incomplete")

    if not isinstance(release, dict) or release.get("current_state") != "HOLD":
        errors.append("provider security release predicate must remain HOLD")
    if not isinstance(release, dict) or release.get("major_release_blocked") is not True:
        errors.append("provider security boundary must block the major release")
    if not isinstance(release, dict) or release.get("database_push_allowed") is not False:
        errors.append("provider security boundary must prohibit database push")
    if not isinstance(release, dict) or release.get("provider_mutation_performed_by_this_change") is not False:
        errors.append("provider security record must not claim provider mutation")
    return errors


def main() -> int:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    actions_policy = json.loads(ACTIONS_POLICY.read_text(encoding="utf-8"))
    if policy.get("phase") != "3" or policy.get("historical_origin_phase") != "2.99":
        fail("security policy must remain bound to Phase 3 with explicit historical origin")
    if policy.get("control_model") != "continuous_detect_triage_repair_revalidate_independent_verify":
        fail("security control model drifted")
    if policy["severity_policy"].get("critical") != "block_and_escalate":
        fail("critical security findings must block")
    if policy["severity_policy"].get("high") != "block_and_heal_or_escalate":
        fail("high security findings must block")
    if policy["self_heal"].get("d3") != "human_reserved":
        fail("D3 security healing must remain human-reserved")
    if "rerun_github_actions_runtime_policy" not in policy["self_heal"].get("post_heal_requirements", []):
        fail("post-heal validation must rerun the GitHub Actions runtime policy")
    crypto = policy["crypto_blockchain_guardrails"]
    if crypto.get("activation_gate") != "independent_legal_financial_security_and_reserved_authority_review":
        fail("advanced crypto/blockchain activation must retain independent specialist gates")
    if crypto.get("institutional_phase_shortcut") is not False:
        fail("no institutional phase may shortcut crypto/token activation gates")

    github_evidence = policy.get("github_security_evidence", {})
    if github_evidence.get("codeql") != "required_when_applicable":
        fail("CodeQL evidence requirement drifted")
    if github_evidence.get("codeql_execution_mode") != "github_default_setup_provider_managed":
        fail("CodeQL execution mode must remain provider-managed default setup")
    if github_evidence.get("advanced_codeql_workflow") != "prohibited_while_default_setup_enabled":
        fail("Advanced CodeQL workflow conflict guard drifted")
    if github_evidence.get("dependency_review_action_line") != "v5_node24":
        fail("Dependency Review must remain on the Node 24 v5 line")
    if github_evidence.get("github_actions_runtime") != "node24_fail_closed":
        fail("GitHub Actions runtime security state drifted")

    runtime = policy.get("github_actions_runtime", {})
    if runtime.get("target_runtime") != "node24":
        fail("security policy must target Node 24")
    if runtime.get("node20_deprecation_response") != "upgrade_action_not_force_runtime":
        fail("Node 20 deprecation must be repaired by action upgrade, not runtime forcing")
    if runtime.get("runtime_escape_hatches") != "prohibited":
        fail("Node runtime escape hatches must remain prohibited")
    if runtime.get("direct_main_write") is not False:
        fail("GitHub Actions runtime self-healing must not write directly to main")

    if actions_policy.get("status") != "active_fail_closed":
        fail("GitHub Actions runtime policy must remain active_fail_closed")

    if not PROVIDER_TRUSTED_WORKFLOW.is_file() or not PROVIDER_CONTRACT_WORKFLOW.is_file():
        fail("provider trusted/contract workflow split is incomplete")
    provider_boundary_errors = provider_workflow_boundary_errors(
        PROVIDER_TRUSTED_WORKFLOW.read_text(encoding="utf-8"),
        PROVIDER_CONTRACT_WORKFLOW.read_text(encoding="utf-8"),
    )
    if provider_boundary_errors:
        fail("provider workflow secret boundary: " + "; ".join(provider_boundary_errors))

    if not CPANEL_ADAPTER.is_file():
        fail("cPanel adapter security boundary is missing")
    cpanel_boundary_errors = cpanel_adapter_boundary_errors(
        CPANEL_ADAPTER.read_text(encoding="utf-8")
    )
    if cpanel_boundary_errors:
        fail("cPanel adapter secret boundary: " + "; ".join(cpanel_boundary_errors))
    if not CPANEL_EXPOSURE_RESPONSE.is_file():
        fail("cPanel public locator exposure response record is missing")
    cpanel_response_errors = cpanel_exposure_response_errors(
        json.loads(CPANEL_EXPOSURE_RESPONSE.read_text(encoding="utf-8"))
    )
    if cpanel_response_errors:
        fail("cPanel exposure response: " + "; ".join(cpanel_response_errors))
    if not PROVIDER_RELEASE_HOLDS.is_file():
        fail("provider release security HOLD record is missing")
    provider_hold_errors = provider_release_hold_errors(
        json.loads(PROVIDER_RELEASE_HOLDS.read_text(encoding="utf-8"))
    )
    if provider_hold_errors:
        fail("provider release security HOLD: " + "; ".join(provider_hold_errors))

    workflow = SECURITY_WORKFLOW.read_text(encoding="utf-8")
    for fragment in (
        "name: Security Governance",
        "name: Validate provider-managed CodeQL compatibility",
        "CodeQL default setup is provider-managed",
        "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0",
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7",
        "python scripts/validate_github_actions_runtime_policy.py",
        "python scripts/validate_security_governance.py",
    ):
        if fragment not in workflow:
            fail(f"security workflow missing {fragment!r}")
    if re.search(r"^\s*uses:\s*github/codeql-action/", workflow, flags=re.MULTILINE):
        fail("Conflicting advanced CodeQL action detected while provider default setup is registered")

    findings = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(".git/"):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{name}:{rel}")
    if findings:
        fail("literal high-risk credential pattern(s) detected: " + ", ".join(findings))

    print("Deterministic security-governance validation passed.")
    print("Provider PR contracts are secret-free; provider credentials remain exact-main environment gated.")
    print("cPanel adapter uses deploy-time locator/username bindings and returns digest-only provider failures.")
    print("cPanel public-locator response remains HOLD pending external rotation and full-window log review.")
    print("Provider migration lineage remains HOLD_NO_DB_PUSH; no provider mutation is certified.")
    print("Deno runtime dependencies remain HOLD pending exact pins and a reviewed lock/integrity graph.")
    print("Supabase INFO advisories remain an inherited review/performance HOLD, not a code-test failure.")
    print("No literal GitHub/OpenAI/Stripe high-risk token patterns detected.")
    print("GitHub Actions: Node 24 fail-closed runtime policy; full-SHA action references; Dependency Review v5.")
    print("CodeQL mode: GitHub provider-managed default setup; duplicate advanced setup prohibited.")
    print("Provider CodeQL findings, dependency review, and secret scans remain independent evidence sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
