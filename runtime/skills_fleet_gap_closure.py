#!/usr/bin/env python3
"""Deterministic, secret-free dry-run runtime for the CrownThrive
Convergence Gap Closure Skills Suite v2.

This runtime plans work and emits a canonical receipt. It never invokes
providers, mutates ledgers, moves money, publishes content, grants rights,
or claims deployment/production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

SUITE_ID = "ct.skill-suite.convergence-gap-closure.v2"
AUTHORITY_RANK = {"D0": 0, "D1": 1, "D2": 2}
SECRET_KEY_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|authorization|bearer|credential)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\b(?:Bearer\s+)[A-Za-z0-9._~+/=-]{12,}\b", re.IGNORECASE),
)


class ContractError(ValueError):
    """Raised when a task violates the public-safe execution contract."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield child_path, child
            yield from _walk(child, child_path)


def reject_secrets(value: Any) -> None:
    findings: List[str] = []
    for path, child in _walk(value):
        key = path.rsplit(".", 1)[-1]
        if SECRET_KEY_PATTERN.search(key):
            findings.append(f"secret-like key at {path}")
        if isinstance(child, str):
            for pattern in SECRET_VALUE_PATTERNS:
                if pattern.search(child):
                    findings.append(f"secret-like value at {path}")
                    break
    if findings:
        raise ContractError("SECRET_BEARING_INPUT_REJECTED: " + "; ".join(sorted(set(findings))))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_registry(root: Path | None = None) -> Dict[str, Any]:
    root = root or repo_root()
    path = root / "registry" / "skills-fleet-gap-closure-v2.json"
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    validate_registry(data, root=root)
    return data


def validate_registry(registry: Mapping[str, Any], root: Path | None = None) -> None:
    if registry.get("suite_id") != SUITE_ID:
        raise ContractError("REGISTRY_SUITE_ID_MISMATCH")
    skills = registry.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ContractError("REGISTRY_SKILLS_EMPTY")
    ids = [item.get("skill_id") for item in skills]
    slugs = [item.get("slug") for item in skills]
    if len(ids) != len(set(ids)):
        raise ContractError("REGISTRY_DUPLICATE_SKILL_ID")
    if len(slugs) != len(set(slugs)):
        raise ContractError("REGISTRY_DUPLICATE_SLUG")
    if any(not isinstance(item, str) or not item.startswith("ct.skill.convergence.") for item in ids):
        raise ContractError("REGISTRY_INVALID_SKILL_ID")
    if root is not None:
        missing = []
        for item in skills:
            path = root / item["skill_path"]
            if not path.is_file():
                missing.append(item["skill_path"])
        suite_path = root / "skills" / "convergence-gap-closure-v2" / "SKILL.md"
        if not suite_path.is_file():
            missing.append(str(suite_path.relative_to(root)))
        if missing:
            raise ContractError("REGISTRY_MISSING_SKILL_DOCS: " + ", ".join(missing))


def find_skill(registry: Mapping[str, Any], skill_id: str) -> Dict[str, Any]:
    defaults = dict(registry.get("skill_defaults", {}))
    for item in registry["skills"]:
        if item["skill_id"] == skill_id or item["slug"] == skill_id:
            merged = defaults
            merged.update(item)
            return merged
    raise ContractError(f"UNKNOWN_SKILL: {skill_id}")


def validate_task(task: Mapping[str, Any], registry: Mapping[str, Any]) -> Dict[str, Any]:
    required = {
        "task_id", "directive_id", "skill_id", "subject_id", "source_ref",
        "requested_authority", "mode", "observed_at", "inputs",
    }
    missing = sorted(required - set(task))
    if missing:
        raise ContractError("TASK_MISSING_FIELDS: " + ", ".join(missing))
    unknown = sorted(set(task) - (required | {"evidence_refs"}))
    if unknown:
        raise ContractError("TASK_UNKNOWN_FIELDS: " + ", ".join(unknown))
    if task["mode"] != "dry-run":
        raise ContractError("LIVE_MODE_DISABLED")
    authority = task["requested_authority"]
    if authority not in AUTHORITY_RANK:
        raise ContractError("INVALID_AUTHORITY")
    skill = find_skill(registry, str(task["skill_id"]))
    max_authority = skill["max_authority"]
    if AUTHORITY_RANK[authority] > AUTHORITY_RANK[max_authority]:
        raise ContractError("AUTHORITY_CEILING_EXCEEDED")
    if not isinstance(task["inputs"], dict):
        raise ContractError("INPUTS_MUST_BE_OBJECT")
    reject_secrets(task)
    return skill


def plan_task(task: Mapping[str, Any], registry: Mapping[str, Any]) -> Dict[str, Any]:
    skill = validate_task(task, registry)
    evidence_refs = task.get("evidence_refs", [])
    hold_reasons: List[str] = []
    if not evidence_refs:
        hold_reasons.append("NO_EVIDENCE_REFS_SUPPLIED_FOR_EFFECT_CLAIM")
    state = "HOLD" if hold_reasons else "PLANNED"
    receipt_core = {
        "suite_id": SUITE_ID,
        "task_id": task["task_id"],
        "skill_id": skill["skill_id"],
        "subject_id": task["subject_id"],
        "source_ref": task["source_ref"],
        "mode": "dry-run",
        "authority": task["requested_authority"],
        "state": state,
        "side_effects": False,
        "provider_invoked": False,
        "readback_required": bool(skill["provider_readback_required_for_effect_claims"]),
        "controls": [
            "secret-bearing inputs rejected",
            "D3 human-reserved",
            "dry-run only",
            "no provider invocation",
            "no production claim",
            "append-only preservation expected",
        ],
        "planned_outputs": list(skill["outputs"]),
        "hold_reasons": hold_reasons,
    }
    fingerprint = sha256_json(receipt_core)
    receipt = dict(receipt_core)
    receipt["canonical_fingerprint"] = fingerprint
    receipt["receipt_id"] = f"ct.receipt.skill-plan.{fingerprint[:24]}"
    return receipt


def cmd_list(registry: Mapping[str, Any]) -> int:
    rows = []
    for item in registry["skills"]:
        skill = find_skill(registry, item["skill_id"])
        rows.append({
            "skill_id": skill["skill_id"],
            "slug": skill["slug"],
            "name": skill["name"],
            "state": skill["lifecycle_state"],
            "max_authority": skill["max_authority"],
        })
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0


def cmd_inspect(registry: Mapping[str, Any], skill_ref: str) -> int:
    print(json.dumps(find_skill(registry, skill_ref), indent=2, ensure_ascii=False))
    return 0


def cmd_validate(registry: Mapping[str, Any]) -> int:
    validate_registry(registry, root=repo_root())
    print(json.dumps({
        "suite_id": SUITE_ID,
        "state": "VALID",
        "skill_count": len(registry["skills"]),
        "registry_fingerprint": sha256_json(registry),
    }, indent=2))
    return 0


def cmd_plan(registry: Mapping[str, Any], task_path: Path, output: Path | None) -> int:
    with task_path.open("r", encoding="utf-8") as handle:
        task = json.load(handle)
    receipt = plan_task(task, registry)
    rendered = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if receipt["state"] == "PLANNED" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List registered skills")
    inspect = sub.add_parser("inspect", help="Inspect one skill")
    inspect.add_argument("skill")
    sub.add_parser("validate-registry", help="Validate registry and skill paths")
    plan = sub.add_parser("plan", help="Create a secret-free dry-run receipt")
    plan.add_argument("--task", required=True, type=Path)
    plan.add_argument("--output", type=Path)
    return parser


def main(argv: List[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        registry = load_registry()
        if args.command == "list":
            return cmd_list(registry)
        if args.command == "inspect":
            return cmd_inspect(registry, args.skill)
        if args.command == "validate-registry":
            return cmd_validate(registry)
        if args.command == "plan":
            return cmd_plan(registry, args.task, args.output)
        raise ContractError("UNKNOWN_COMMAND")
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "DENIED", "reason": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
