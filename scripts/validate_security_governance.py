#!/usr/bin/env python3
"""Validate deterministic CrownThrive security-governance controls.

This complements GitHub CodeQL, dependency review and provider secret scanning.
It does not claim those provider scans ran merely because this validator passes.
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

    workflow = SECURITY_WORKFLOW.read_text(encoding="utf-8")
    for fragment in (
        "name: Security Governance",
        "github/codeql-action/init@v4",
        "github/codeql-action/analyze@v4",
        "actions/dependency-review-action@v4",
        "python scripts/validate_security_governance.py",
    ):
        if fragment not in workflow:
            fail(f"security workflow missing {fragment!r}")

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
    print("Provider CodeQL/dependency/secret scans remain independent evidence sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
