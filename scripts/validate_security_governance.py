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
    print("No literal GitHub/OpenAI/Stripe high-risk token patterns detected.")
    print("GitHub Actions: Node 24 fail-closed runtime policy; full-SHA action references; Dependency Review v5.")
    print("CodeQL mode: GitHub provider-managed default setup; duplicate advanced setup prohibited.")
    print("Provider CodeQL findings, dependency review, and secret scans remain independent evidence sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
