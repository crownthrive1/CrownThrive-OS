#!/usr/bin/env python3
"""Deterministic, fail-closed Penta namespace discovery.

PentaCensus discovers explicit Penta symbols and machine keys in governed source
classes and compares them with the existing namespace census plus governed
extensions. It does not register, authorize, certify, or promote anything.
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
SCAN_ROOTS = (
    Path("data/penta"),
    Path("penta/registry"),
    Path("runtime"),
    Path("scripts"),
    Path(".github/workflows"),
)
TEXT_SUFFIXES = {".json", ".py", ".md", ".mdx", ".yml", ".yaml"}
MAX_SCAN_BYTES = 1_500_000
MAX_EVIDENCE_PATHS = 20

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
PENTA_MACHINE_RE = re.compile(r"(?<![a-z0-9_.-])penta\.[a-z][a-z0-9_.-]*(?![a-z0-9_.-])")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def iter_scan_files(root: Path) -> Iterable[Path]:
    for rel_root in SCAN_ROOTS:
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

    # Governed extensions are allowed to exist outside the frozen canonical OS
    # registry. Their names/keys are known discovery identities, but they do not
    # become canonical merely because PentaCensus recognizes them.
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


def build_report(root: Path = ROOT) -> dict[str, Any]:
    known_names, known_machine_keys, _ = known_namespace(root)
    symbol_paths: dict[str, set[str]] = defaultdict(set)
    machine_paths: dict[str, set[str]] = defaultdict(set)
    scanned: list[tuple[str, str]] = []

    for path in iter_scan_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned.append((rel, hashlib.sha256(raw).hexdigest()))
        for symbol in PENTA_SYMBOL_RE.findall(text):
            if normalize_name(symbol) not in known_names:
                symbol_paths[symbol].add(rel)
        for machine_key in PENTA_MACHINE_RE.findall(text):
            if machine_key not in known_machine_keys:
                machine_paths[machine_key].add(rel)

    source_digest_input = "\n".join(f"{path}\0{digest}" for path, digest in scanned).encode("utf-8")
    source_digest = hashlib.sha256(source_digest_input).hexdigest()

    unknown_symbols = [
        {
            "candidate_type": "display_symbol",
            "value": value,
            "normalized": normalize_name(value),
            "state": "CANDIDATE_DISCOVERY",
            "evidence_paths": sorted(paths)[:MAX_EVIDENCE_PATHS],
        }
        for value, paths in sorted(symbol_paths.items(), key=lambda item: item[0].casefold())
    ]
    unknown_machine_keys = [
        {
            "candidate_type": "machine_key",
            "value": value,
            "state": "CANDIDATE_DISCOVERY",
            "evidence_paths": sorted(paths)[:MAX_EVIDENCE_PATHS],
        }
        for value, paths in sorted(machine_paths.items())
    ]

    return {
        "schema_version": "1.0.0",
        "report_id": "crownthrive.penta.census.discovery.v1",
        "authority_invariant": (
            "Discovery and repeated observation never create canonical identity, maturity, execution eligibility, "
            "credentials, provider permission, certification, production status, financial/rights authority, or D3 authority."
        ),
        "source_classes": [path.as_posix() for path in SCAN_ROOTS],
        "source_digest_sha256": source_digest,
        "counts": {
            "known_namespace_identities": len(known_names),
            "known_machine_keys": len(known_machine_keys),
            "scanned_files": len(scanned),
            "unknown_display_symbols": len(unknown_symbols),
            "unknown_machine_keys": len(unknown_machine_keys),
            "total_unknown_observations": len(unknown_symbols) + len(unknown_machine_keys),
        },
        "unknown_display_symbols": unknown_symbols,
        "unknown_machine_keys": unknown_machine_keys,
        "routing": {
            "unknown_identity_state": "CANDIDATE_DISCOVERY",
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
        help="Return success even when new candidate discoveries exist; useful for advisory inspection only.",
    )
    args = parser.parse_args()

    report = build_report(args.root.resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        counts = report["counts"]
        print(
            "PentaCensus: "
            f"known={counts['known_namespace_identities']} "
            f"machine_keys={counts['known_machine_keys']} "
            f"files={counts['scanned_files']} "
            f"unknown={counts['total_unknown_observations']} "
            f"source_sha256={report['source_digest_sha256']}"
        )
        for row in report["unknown_display_symbols"]:
            print(f"UNKNOWN_SYMBOL {row['value']} :: {', '.join(row['evidence_paths'])}")
        for row in report["unknown_machine_keys"]:
            print(f"UNKNOWN_MACHINE_KEY {row['value']} :: {', '.join(row['evidence_paths'])}")

    if report["counts"]["total_unknown_observations"] and not args.allow_unknown:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
