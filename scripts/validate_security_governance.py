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
CREDENTIAL_POLICY = ROOT / "developers/manifests/credential-vault-ingestion-policy.v1.json"
REQUEST_BUDGET_POLICY = ROOT / "developers/manifests/api-request-budget-policy.v1.json"
ACTIONS_POLICY = ROOT / "developers/manifests/github-actions-runtime-policy.v1.json"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security-governance.yml"

SECRET_PATTERNS = {
    "github_classic_pat": re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
    "github_fine_grained_pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "openai_project_key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
    "stripe_live_secret": re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
}
SCAN_SUFFIXES = {".py", ".json", ".yml", ".yaml", ".md", ".mdx", ".ts", ".js"}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    credential_policy = json.loads(CREDENTIAL_POLICY.read_text(encoding="utf-8"))
    request_budget_policy = json.loads(REQUEST_BUDGET_POLICY.read_text(encoding="utf-8"))
    actions_policy = json.loads(ACTIONS_POLICY.read_text(encoding="utf-8"))
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
    if policy["crypto_blockchain_guardrails"].get("phase_9_dependency") is not True:
        fail("advanced crypto/blockchain activation must remain Phase 9-gated")

    vault_policy = credential_policy.get("policy", {})
    if credential_policy.get("status") != "active_fail_closed":
        fail("credential Vault-ingestion policy must remain active_fail_closed")
    if vault_policy.get("founder_or_user_supplied_secret") != "vault_ingest_before_runtime_use":
        fail("supplied secrets must enter Vault before runtime use")
    if vault_policy.get("default_secret_store") != "supabase_vault":
        fail("default secret store must remain Supabase Vault")
    for key in (
        "raw_secret_repository",
        "raw_secret_documentation",
        "raw_secret_examples",
        "raw_secret_logs_ci_email_screenshots",
        "raw_secret_retransmission_in_chat",
    ):
        if vault_policy.get(key) != "prohibited" and not (
            key == "raw_secret_retransmission_in_chat" and vault_policy.get(key) == "prohibited_after_ingestion"
        ):
            fail(f"credential handling control drifted: {key}")
    if vault_policy.get("runtime_consumption") != "server_side_vault_reference_only":
        fail("runtime credentials must remain server-side Vault references only")
    if vault_policy.get("vault_unavailable_behavior") != "fail_closed_and_request_connector_or_secure_binding":
        fail("missing Vault capability must fail closed")

    unlimited = set(request_budget_policy.get("unlimited_api_families", []))
    required_unlimited = {
        "crownthrive_io",
        "thrivetools_seo",
        "thrivepush",
        "crownpulse",
        "crownlytics",
        "thrivetools",
        "thrivetools_opt",
    }
    if not required_unlimited.issubset(unlimited):
        fail("founder-confirmed unlimited API family policy drifted")
    budget_enforcement = request_budget_policy.get("enforcement", {})
    if budget_enforcement.get("monthly_hard_ceiling") is not False:
        fail("founder-confirmed unlimited API families must not gain a monthly hard ceiling")
    if budget_enforcement.get("fail_closed_on_monthly_count") is not False:
        fail("request counters for unlimited API families must remain telemetry, not fail-closed monthly quota gates")
    if budget_enforcement.get("writes") != "remain_independently_governed_and_fail_closed":
        fail("unlimited read-call policy must never open provider writes")

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
    print("Credential policy: supplied secrets must enter Supabase Vault before runtime use; repository/docs/log/email exposure prohibited.")
    print("Request-budget policy: founder-confirmed unlimited CrownThrive API families use request ledgers for telemetry, not monthly fail-closed ceilings.")
    print("No literal GitHub/OpenAI/Stripe high-risk token patterns detected.")
    print("GitHub Actions: Node 24 fail-closed runtime policy; full-SHA action references; Dependency Review v5.")
    print("CodeQL mode: GitHub provider-managed default setup; duplicate advanced setup prohibited.")
    print("Provider CodeQL findings, dependency review, and secret scans remain independent evidence sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
