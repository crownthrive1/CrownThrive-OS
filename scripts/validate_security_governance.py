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
SECURITY_WORKFLOW = ROOT / ".github/workflows/security-governance.yml"

SECRET_PATTERNS = {
    "github_classic_pat": re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
    "github_fine_grained_pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "openai_project_key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
    "stripe_live_secret": re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
}
ADVANCED_CODEQL_USE = re.compile(
    r"^\s*uses:\s*github/codeql-action/", re.MULTILINE
)
SCAN_SUFFIXES = {".py", ".json", ".yml", ".yaml", ".md", ".mdx", ".ts", ".js"}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    if policy.get("control_model") != "continuous_detect_triage_repair_revalidate_independent_verify":
        fail("security control model drifted")
    if policy["severity_policy"].get("critical") != "block_and_escalate":
        fail("critical security findings must block")
    if policy["severity_policy"].get("high") != "block_and_heal_or_escalate":
        fail("high security findings must block")
    if policy["self_heal"].get("d3") != "human_reserved":
        fail("D3 security healing must remain human-reserved")
    if policy["crypto_blockchain_guardrails"].get("phase_9_dependency") is not True:
        fail("advanced crypto/blockchain activation must remain Phase 9-gated")

    github_evidence = policy.get("github_security_evidence", {})
    if github_evidence.get("codeql") != "required_when_applicable":
        fail("CodeQL evidence requirement drifted")
    if github_evidence.get("codeql_execution_mode") != "github_default_setup_provider_managed":
        fail("CodeQL execution mode must remain provider-managed default setup")
    if github_evidence.get("advanced_codeql_workflow") != "prohibited_while_default_setup_enabled":
        fail("Advanced CodeQL workflow conflict guard drifted")

    workflow = SECURITY_WORKFLOW.read_text(encoding="utf-8")
    for fragment in (
        "name: Security Governance",
        "name: Validate provider-managed CodeQL compatibility",
        "CodeQL default setup is provider-managed",
        "actions/dependency-review-action@v4",
        "actions/checkout@v7",
        "actions/setup-python@v7",
        "python scripts/validate_security_governance.py",
    ):
        if fragment not in workflow:
            fail(f"security workflow missing {fragment!r}")
    if ADVANCED_CODEQL_USE.search(workflow):
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
    print("CodeQL mode: GitHub provider-managed default setup; duplicate advanced setup prohibited.")
    print("Provider CodeQL findings, dependency review, and secret scans remain independent evidence sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
