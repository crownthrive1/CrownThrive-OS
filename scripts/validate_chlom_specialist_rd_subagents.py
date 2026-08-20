#!/usr/bin/env python3
"""Fail-closed validation for the CHLOM specialist R&D subagent fabric."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/chlom-specialist-rd-subagents.v1.json"

EXPECTED_IDS = {
    "ct.subagent.rnd.legal-regulatory",
    "ct.subagent.rnd.ip-rights-licensing",
    "ct.subagent.rnd.finance-tax-treasury",
    "ct.subagent.rnd.blockchain-cryptographic-protocol",
    "ct.subagent.rnd.accessibility-consumer-protection",
    "ct.subagent.rnd.regional-global-localization",
}

DOC_PATHS = {
    "automation/chlom-specialist-rd-fabric.mdx",
    "chlom/specialist-rd-integration-and-paper-pipeline.mdx",
    "standards/documentation-linking-and-machine-ingestion.mdx",
}

REQUIRED_RECOMMENDATION_QUESTIONS = {
    "what",
    "why",
    "who",
    "where_integrated",
    "how_implemented",
    "current_best_method",
    "alternatives",
    "risks",
    "evidence",
    "subagents_or_specialty_knowledge",
    "approvals_required",
    "documentation_and_paper_effect",
    "machine_consumable_output",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def load_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - fail-closed diagnostic
        fail(f"manifest unreadable or invalid JSON: {exc}")


def validate_manifest(data: dict) -> None:
    if data.get("schema_version") != "1.0.0":
        fail("unexpected schema_version")
    if data.get("state") != "candidate_pending_governed_merge":
        fail("candidate state must remain explicit before merge")
    if data.get("role_class") != "specialist_rnd_non_voting":
        fail("specialists must remain non-voting")
    if data.get("sovereign_voter_change") is not False:
        fail("specialist fabric cannot change the sovereign voter pool")
    if data.get("simplebase_state") != "retired_historical_only_not_dependency":
        fail("SimpleBase must remain retired historical-only")

    specialists = data.get("specialists")
    if not isinstance(specialists, list) or len(specialists) != 6:
        fail("exactly six specialist R&D roles are required")

    ids = {row.get("id") for row in specialists}
    if ids != EXPECTED_IDS:
        fail(f"specialist ID drift: {sorted(ids)}")

    contracts = []
    for row in specialists:
        path = row.get("contract_path")
        if not isinstance(path, str):
            fail(f"missing contract path for {row.get('id')}")
        contracts.append(path)
        full = ROOT / path
        if not full.is_file():
            fail(f"missing specialist contract: {path}")
        text = full.read_text(encoding="utf-8")
        if f"id: {row['id']}" not in text:
            fail(f"contract ID mismatch: {path}")
        if "role_class: specialist_rnd_non_voting" not in text:
            fail(f"non-voting role class missing: {path}")
        if "reserved_boundaries:" not in text:
            fail(f"reserved boundaries missing: {path}")
        if "handoff_contract:" not in text:
            fail(f"handoff contract missing: {path}")

    if len(set(contracts)) != 6:
        fail("specialist contract paths must be unique")

    questions = set(data.get("recommendation_required_questions", []))
    if questions != REQUIRED_RECOMMENDATION_QUESTIONS:
        fail("recommendation packet contract drift")

    docs = data.get("documentation", {})
    if docs.get("internal_linking_required") is not True:
        fail("internal linking must remain mandatory")
    toc = docs.get("long_form_toc_rule", {})
    if toc.get("minimum_h2_sections") != 5 or toc.get("approximate_word_threshold") != 1200:
        fail("long-form TOC rule drift")

    paper = data.get("paper_pipeline", {})
    if set(paper.get("confirmed_families", [])) != {"white", "black", "gold", "blue", "red", "green"}:
        fail("confirmed paper-family drift")
    if set(paper.get("reserved_recovery_only_families", [])) != {"purple", "silver", "orange", "yellow"}:
        fail("reserved paper-family drift")
    if paper.get("family_name_creates_authority") is not False:
        fail("paper family cannot create authority")

    hard = set(data.get("hard_boundaries", []))
    required_hard = {
        "no specialist vote",
        "no self approval",
        "no unknown to pass",
        "no phase advancement from research or documentation alone",
    }
    if not required_hard.issubset(hard):
        fail("hard-boundary regression")


def validate_docs() -> None:
    for path in DOC_PATHS:
        full = ROOT / path
        if not full.is_file():
            fail(f"missing documentation page: {path}")
        text = full.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            fail(f"missing frontmatter: {path}")
        h2_count = len(re.findall(r"^##\s+", text, flags=re.MULTILINE))
        word_count = len(re.findall(r"\b[\w'-]+\b", text))
        if (h2_count >= 5 or word_count >= 1200) and "## Table of contents" not in text:
            fail(f"long page missing table of contents: {path}")
        internal_links = re.findall(r"\]\(/[^)]+\)", text)
        if len(internal_links) < 3:
            fail(f"page lacks required contextual internal links: {path}")

    standard = (ROOT / "standards/documentation-linking-and-machine-ingestion.mdx").read_text(encoding="utf-8")
    required_phrases = [
        "Internal linking is mandatory",
        "Machine-ingestion contract",
        "Solidity",
        "orphan pages",
        "screen readers",
    ]
    for phrase in required_phrases:
        if phrase.lower() not in standard.lower():
            fail(f"authoring standard missing required concept: {phrase}")


def main() -> None:
    data = load_manifest()
    validate_manifest(data)
    validate_docs()
    print("PASS: CHLOM specialist R&D fabric validated (6 roles, contracts, docs, boundaries).")


if __name__ == "__main__":
    main()
