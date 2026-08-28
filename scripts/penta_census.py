#!/usr/bin/env python3
"""Deterministic, fail-closed Penta namespace discovery.

PentaCensus distinguishes authoritative-ish structured identity declarations from
unstructured code/workflow references. Unknown declarations are hard-gated;
unknown references are an advisory semantic/topology queue. Neither class creates
canonical identity, authority, maturity, certification, or production status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CENSUS_PATH = Path("data/penta/namespace-census.v1.json")
STRUCTURED_ROOTS = (Path("data/penta"), Path("penta/registry"))
REFERENCE_ROOTS = (Path("runtime"), Path("scripts"), Path(".github/workflows"))
ALL_SCAN_ROOTS = STRUCTURED_ROOTS + REFERENCE_ROOTS
TEXT_SUFFIXES = {".json", ".py", ".md", ".mdx", ".yml", ".yaml"}
MAX_SCAN_BYTES = 1_500_000
MAX_EVIDENCE_PATHS = 20
IDENTITY_NAME_KEYS = {"canonical_name"}
IDENTITY_MACHINE_KEYS = {"machine_key", "canonical_machine_key"}

# Generated machine corpora contain repeated projections of the same namespace and
# are intentionally excluded from discovery evidence to avoid self-amplification.
EXCLUDED_FILES = {
    Path("data/penta/agent-knowledge.v1.json"),
    Path("data/penta/agent-knowledge.v1.jsonl"),
    Path("data/penta/operational-knowledge.v1.json"),
    Path("data/penta/pentagonal-reference.v1.json"),
    Path("data/penta/pentagonal-reference.v1.jsonl"),
    Path("data/penta/namespace-census.v1.json"),
}

PENTA_SYMBOL_RE = re.compile(r"(?<![A-Za-z0-9])Penta[A-Z][A-Za-z0-9]*(?![A-Za-z0-9])")
SYSTEM_MACHINE_RE = re.compile(r"^penta\.[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def iter_scan_files(root: Path, roots: Iterable[Path]) -> Iterable[Path]:
    for rel_root in roots:
        base = root / rel_root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel = path.relative_to(root)
            if rel in EXCLUDED_FILES:
                continue
            try:
                if path.stat().st_size > MAX_SCAN_BYTES:
                    continue
            except OSError:
                continue
            yield path


def known_namespace(root: Path) -> tuple[set[str], set[str], dict[str, str]]:
    census = load_json(root / CENSUS_PATH)
    known_names: set[str] = set()
    machine_keys: set[str] = set()
    display_by_norm: dict[str, str] = {}

    for row in census.get("records", []):
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if isinstance(name, str) and name.strip():
            norm = normalize_name(name)
            known_names.add(norm)
            display_by_norm[norm] = name
        machine = row.get("canonical_machine_key")
        if isinstance(machine, str) and machine.startswith("penta."):
            machine_keys.add(machine)

    # Governed extensions are known namespace identities even when they remain
    # outside the frozen canonical OS registry. Recognition is not promotion.
    for path in sorted((root / "data/penta").glob("systems*.json")):
        try:
            data = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        systems = data.get("systems")
        if not isinstance(systems, list):
            continue
        for row in systems:
            if not isinstance(row, dict):
                continue
            name = row.get("canonical_name")
            if isinstance(name, str) and normalize_name(name).startswith("penta"):
                norm = normalize_name(name)
                known_names.add(norm)
                display_by_norm.setdefault(norm, name)
            machine = row.get("machine_key")
            if isinstance(machine, str) and machine.startswith("penta."):
                machine_keys.add(machine)

    return known_names, machine_keys, display_by_norm


def walk_identity_declarations(value: Any) -> Iterable[tuple[str, str]]:
    """Yield (kind, value) only from explicit identity-bearing JSON fields."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key in IDENTITY_NAME_KEYS and isinstance(child, str):
                if normalize_name(child).startswith("penta"):
                    yield "display_name", child.strip()
            elif key in IDENTITY_MACHINE_KEYS and isinstance(child, str):
                if SYSTEM_MACHINE_RE.fullmatch(child.strip()):
                    yield "machine_key", child.strip()
            yield from walk_identity_declarations(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_identity_declarations(child)


def build_report(root: Path = ROOT) -> dict[str, Any]:
    known_names, known_machine_keys, _ = known_namespace(root)
    declaration_name_paths: dict[str, set[str]] = defaultdict(set)
    declaration_machine_paths: dict[str, set[str]] = defaultdict(set)
    advisory_symbol_paths: dict[str, set[str]] = defaultdict(set)
    scanned: dict[str, str] = {}

    # Structured registry/data declarations are the hard-gated discovery plane.
    for path in iter_scan_files(root, STRUCTURED_ROOTS):
        rel = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        scanned[rel] = hashlib.sha256(raw).hexdigest()
        if path.suffix.lower() != ".json":
            continue
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        for kind, declared in walk_identity_declarations(value):
            if kind == "display_name":
                if normalize_name(declared) not in known_names:
                    declaration_name_paths[declared].add(rel)
            elif declared not in known_machine_keys:
                declaration_machine_paths[declared].add(rel)

    # Runtime/script/workflow symbols are useful discovery evidence but may be
    # classes, clients, errors, helpers, fixtures, or compatibility names. They
    # therefore enter an advisory queue instead of becoming identity declarations.
    for path in iter_scan_files(root, REFERENCE_ROOTS):
        rel = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned[rel] = hashlib.sha256(raw).hexdigest()
        for symbol in PENTA_SYMBOL_RE.findall(text):
            if normalize_name(symbol) not in known_names:
                advisory_symbol_paths[symbol].add(rel)

    source_digest_input = "\n".join(
        f"{path}\0{digest}" for path, digest in sorted(scanned.items())
    ).encode("utf-8")
    source_digest = hashlib.sha256(source_digest_input).hexdigest()

    unknown_declared_names = [
        {
            "candidate_type": "declared_display_identity",
            "value": value,
            "normalized": normalize_name(value),
            "state": "CANDIDATE_DISCOVERY",
            "evidence_paths": sorted(paths)[:MAX_EVIDENCE_PATHS],
        }
        for value, paths in sorted(declaration_name_paths.items(), key=lambda item: item[0].casefold())
    ]
    unknown_declared_machine_keys = [
        {
            "candidate_type": "declared_machine_identity",
            "value": value,
            "state": "CANDIDATE_DISCOVERY",
            "evidence_paths": sorted(paths)[:MAX_EVIDENCE_PATHS],
        }
        for value, paths in sorted(declaration_machine_paths.items())
    ]
    advisory_references = [
        {
            "candidate_type": "unstructured_symbol_reference",
            "value": value,
            "normalized": normalize_name(value),
            "state": "SEMANTIC_REVIEW_PENDING",
            "evidence_paths": sorted(paths)[:MAX_EVIDENCE_PATHS],
        }
        for value, paths in sorted(advisory_symbol_paths.items(), key=lambda item: item[0].casefold())
    ]
    strict_unknown = len(unknown_declared_names) + len(unknown_declared_machine_keys)

    return {
        "schema_version": "1.1.0",
        "report_id": "crownthrive.penta.census.discovery.v1",
        "authority_invariant": (
            "Discovery and repeated observation never create canonical identity, maturity, execution eligibility, "
            "credentials, provider permission, certification, production status, financial/rights authority, or D3 authority."
        ),
        "source_classes": {
            "hard_gated_identity_declarations": [path.as_posix() for path in STRUCTURED_ROOTS],
            "advisory_unstructured_references": [path.as_posix() for path in REFERENCE_ROOTS],
        },
        "source_digest_sha256": source_digest,
        "counts": {
            "known_namespace_identities": len(known_names),
            "known_machine_keys": len(known_machine_keys),
            "scanned_files": len(scanned),
            "unknown_declared_display_identities": len(unknown_declared_names),
            "unknown_declared_machine_identities": len(unknown_declared_machine_keys),
            "strict_unknown_declarations": strict_unknown,
            "advisory_unstructured_symbol_references": len(advisory_references),
        },
        "unknown_declared_display_identities": unknown_declared_names,
        "unknown_declared_machine_identities": unknown_declared_machine_keys,
        "advisory_unstructured_symbol_references": advisory_references,
        "routing": {
            "unknown_identity_state": "CANDIDATE_DISCOVERY",
            "advisory_reference_state": "SEMANTIC_REVIEW_PENDING",
            "handoff": ["PentaScribe", "PentaPology", "PentaDocs", "PentaAssure"],
            "automatic_canonical_registration": False,
            "automatic_execution_enablement": False,
            "automatic_maturity_promotion": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Census governed Penta namespace references.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="Print the complete JSON report.")
    parser.add_argument(
        "--allow-unknown",
        action="store_true",
        help="Return success even when strict unknown identity declarations exist; advisory inspection only.",
    )
    args = parser.parse_args()

    report = build_report(args.root.resolve())
    counts = report["counts"]
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "PentaCensus: "
            f"known={counts['known_namespace_identities']} "
            f"machine_keys={counts['known_machine_keys']} "
            f"files={counts['scanned_files']} "
            f"strict_unknown={counts['strict_unknown_declarations']} "
            f"advisory_refs={counts['advisory_unstructured_symbol_references']} "
            f"source_sha256={report['source_digest_sha256']}"
        )
        for row in report["unknown_declared_display_identities"]:
            print(f"UNKNOWN_DECLARED_NAME {row['value']} :: {', '.join(row['evidence_paths'])}")
        for row in report["unknown_declared_machine_identities"]:
            print(f"UNKNOWN_DECLARED_MACHINE {row['value']} :: {', '.join(row['evidence_paths'])}")
        for row in report["advisory_unstructured_symbol_references"]:
            print(f"ADVISORY_REFERENCE {row['value']} :: {', '.join(row['evidence_paths'])}")

    if counts["strict_unknown_declarations"] and not args.allow_unknown:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
