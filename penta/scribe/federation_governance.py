#!/usr/bin/env python3
"""Governance controls for PentaScribe federated semantics.

This module audits overlapping semantic authority claims and converts true discovery
candidates into stable, review-only work items. It never promotes terminology,
trademark status, legal rights, provider capability, or publication authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIBE_PATH = ROOT / "penta/scribe/pentascribe.py"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


scribe = load_module("pentascribe_for_federation_governance", SCRIBE_PATH)


def equivalence_map(sources_config: dict | None) -> dict[str, str]:
    """Map declared identity IDs to one explicit equivalence group.

    Equivalence declarations are compatibility assertions only. They do not merge
    legal entities, marks, rights, provider identities, or ownership records.
    """
    mapping: dict[str, str] = {}
    if not sources_config:
        return mapping
    for index, item in enumerate(sources_config.get("equivalences", [])):
        eq_id = item.get("equivalence_id") or f"equivalence-{index}"
        ids = item.get("ids") or []
        if len(ids) < 2:
            raise ValueError(f"{eq_id}: equivalence requires at least two ids")
        for identity_id in ids:
            previous = mapping.get(identity_id)
            if previous and previous != eq_id:
                raise ValueError(f"identity {identity_id} belongs to multiple equivalence groups")
            mapping[identity_id] = eq_id
    return mapping


def identity_partition(identity_id: str, equivalences: dict[str, str]) -> str:
    return equivalences.get(identity_id, f"id:{identity_id}")


def semantic_claims(registry: dict, sources_config: dict | None, root: pathlib.Path = ROOT) -> list[dict]:
    claims: list[dict] = []
    for term in registry.get("terms", []):
        if term.get("status") not in {"canonical", "draft"}:
            continue
        for name in [term.get("canonical", ""), *(term.get("aliases") or [])]:
            if not name:
                continue
            claims.append({
                "semantic_key": scribe.semantic_key(name),
                "name": name,
                "identity_id": term["id"],
                "canonical": term["canonical"],
                "source_id": "pentascribe-seed",
                "source_path": term.get("source"),
                "authority": "pentascribe_canonical" if term.get("status") == "canonical" else "pentascribe_draft",
                "precedence": 0,
            })
    if not sources_config:
        return claims
    source_order = {item["source_id"]: index + 1 for index, item in enumerate(sources_config.get("sources", []))}
    for entry in scribe.source_entries(sources_config, root):
        for name in [entry["canonical"], *(entry.get("aliases") or [])]:
            if not name:
                continue
            claims.append({
                "semantic_key": scribe.semantic_key(name),
                "name": name,
                "identity_id": entry["id"],
                "canonical": entry["canonical"],
                "source_id": entry["source_id"],
                "source_path": entry["source_path"],
                "authority": entry["authority"],
                "precedence": source_order.get(entry["source_id"], 9999),
            })
    return claims


def audit_federation(registry: dict, sources_config: dict | None, root: pathlib.Path = ROOT) -> dict:
    equivalences = equivalence_map(sources_config)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for claim in semantic_claims(registry, sources_config, root):
        grouped[claim["semantic_key"]].append(claim)

    conflicts: list[dict] = []
    overlaps: list[dict] = []
    for key in sorted(grouped):
        claims = grouped[key]
        partitions = {identity_partition(claim["identity_id"], equivalences) for claim in claims}
        if len(claims) < 2:
            continue
        ordered = sorted(claims, key=lambda item: (item["precedence"], item["source_id"], item["identity_id"], item["name"]))
        winner = ordered[0]
        record = {
            "semantic_key": key,
            "winner": {k: winner[k] for k in ("identity_id", "canonical", "source_id", "source_path", "authority")},
            "claims": [
                {k: item[k] for k in ("identity_id", "canonical", "name", "source_id", "source_path", "authority", "precedence")}
                for item in ordered
            ],
            "identity_partitions": sorted(partitions),
        }
        if len(partitions) > 1:
            record["reason"] = "AMBIGUOUS_SEMANTIC_AUTHORITY"
            conflicts.append(record)
        else:
            record["reason"] = "SAME_OR_DECLARED_EQUIVALENT_IDENTITY"
            overlaps.append(record)

    return {
        "schema_version": "1.0.0",
        "audit_id": "crownthrive.pentascribe.federation-authority-audit",
        "result": "PASS" if not conflicts else "FAIL",
        "claim_count": sum(len(items) for items in grouped.values()),
        "semantic_key_count": len(grouped),
        "overlap_count": len(overlaps),
        "conflict_count": len(conflicts),
        "overlaps": overlaps,
        "conflicts": conflicts,
        "equivalence_group_count": len(set(equivalences.values())),
        "authority_note": "Precedence resolves only same or explicitly equivalent semantic identities. Ambiguous authority fails closed; no collision is silently converted into canon.",
    }


def candidate_id(observed: str) -> str:
    digest = hashlib.sha256(scribe.semantic_key(observed).encode("utf-8")).hexdigest()[:16]
    return f"pentascribe-candidate-{digest}"


def candidate_priority(count: int, symbols: list[str]) -> str:
    if symbols or count >= 25:
        return "high"
    if count >= 5:
        return "normal"
    return "low"


def build_candidate_queue(discovery: dict) -> dict:
    items: list[dict] = []
    for candidate in discovery.get("candidates", []):
        symbols = candidate.get("symbols") or []
        observed = candidate["observed"]
        items.append({
            "candidate_id": candidate_id(observed),
            "observed": observed,
            "semantic_key": scribe.semantic_key(observed),
            "proposed_id": candidate.get("proposed_id") or scribe.normalize(observed),
            "status": "REVIEW_REQUIRED",
            "priority": candidate_priority(int(candidate.get("count", 0)), symbols),
            "occurrence_count": int(candidate.get("count", 0)),
            "evidence_sources": candidate.get("sources") or [],
            "observed_symbols": symbols,
            "required_gates": ["PentaScribe semantic review", "CIE meaning/brand review"],
            "conditional_gates": ["PentaIP/CHLOM evidence review if legal, rights, licensing, ownership, or mark status is asserted"],
            "automatic_promotion": False,
            "disposition_note": "Discovery is evidence for review only. Admission, aliasing, deprecation, rejection, or historical classification requires a governed disposition.",
        })
    items.sort(key=lambda item: ({"high": 0, "normal": 1, "low": 2}[item["priority"]], -item["occurrence_count"], item["observed"].casefold()))
    return {
        "schema_version": "1.0.0",
        "queue_id": "crownthrive.pentascribe.candidate-review",
        "review_count": len(items),
        "federated_observation_count": int(discovery.get("federated_observation_count", 0)),
        "rejected_observation_count": int(discovery.get("rejected_observation_count", 0)),
        "items": items,
        "authority_note": "Candidate work items never self-promote. A queue item is not a trademark, legal, provider, publication, or governance authorization.",
    }


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit", "triage"])
    parser.add_argument("--registry", default="penta/scribe/registry.json")
    parser.add_argument("--sources", default="penta/scribe/sources.registry.json")
    parser.add_argument("--discovery")
    parser.add_argument("--out", default="-")
    args = parser.parse_args(argv)

    registry = read_json(pathlib.Path(args.registry))
    sources = read_json(pathlib.Path(args.sources)) if args.sources else None
    if args.command == "audit":
        try:
            result = audit_federation(registry, sources)
        except (ValueError, FileNotFoundError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        text = json.dumps(result, indent=2) + "\n"
        if args.out == "-":
            print(text, end="")
        else:
            write_json(pathlib.Path(args.out), result)
            print(args.out)
        return 0 if result["result"] == "PASS" else 1

    if not args.discovery:
        print("--discovery is required for triage", file=sys.stderr)
        return 1
    queue = build_candidate_queue(read_json(pathlib.Path(args.discovery)))
    text = json.dumps(queue, indent=2) + "\n"
    if args.out == "-":
        print(text, end="")
    else:
        write_json(pathlib.Path(args.out), queue)
        print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
