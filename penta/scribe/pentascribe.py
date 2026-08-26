#!/usr/bin/env python3
"""PentaScribe: deterministic institutional language compiler for CrownThrive."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOWED_TERM_STATUS = {"draft", "canonical", "deprecated", "historical"}
ALLOWED_TM_STATUS = {"unverified", "claimed_public_display", "filed", "registered", "abandoned", "not_applicable"}
SCANNABLE_SUFFIXES = {".md", ".mdx", ".json", ".yml", ".yaml", ".py", ".txt", ".ts", ".tsx"}
PENTA_CANDIDATE_RE = re.compile(r"\b(Penta[A-Z][A-Za-z0-9]+|PENTA)([™®]?)(?![A-Za-z0-9_])")


def load_registry(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources(path: pathlib.Path | None) -> dict:
    if path is None:
        return {"schema_version": "1.0.0", "sources": [], "blocked_terms": []}
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def semantic_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold().replace("™", "").replace("®", ""))


def validate_registry(data: dict) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_names: dict[str, str] = {}
    if data.get("schema_version") != "1.0.0":
        errors.append("unsupported schema_version")
    for i, term in enumerate(data.get("terms", [])):
        prefix = f"terms[{i}]"
        for key in ("id", "canonical", "kind", "definition", "status", "source", "trademark"):
            if not term.get(key):
                errors.append(f"{prefix}: missing {key}")
        tid = term.get("id")
        if tid in seen_ids:
            errors.append(f"{prefix}: duplicate id {tid}")
        if tid:
            seen_ids.add(tid)
            if normalize(tid) != tid:
                errors.append(f"{prefix}: id must be normalized kebab-case")
        if term.get("status") not in ALLOWED_TERM_STATUS:
            errors.append(f"{prefix}: invalid status {term.get('status')}")
        tm = term.get("trademark") or {}
        if tm.get("status") not in ALLOWED_TM_STATUS:
            errors.append(f"{prefix}: invalid trademark.status {tm.get('status')}")
        for name in [term.get("canonical", ""), *(term.get("aliases") or [])]:
            if not name:
                continue
            key = semantic_key(name)
            owner = seen_names.get(key)
            if owner and owner != tid:
                errors.append(f"{prefix}: name/alias collision '{name}' with {owner}")
            seen_names[key] = tid
        if tm.get("status") == "registered" and (tm.get("symbol") != "®" or not tm.get("registration")):
            errors.append(f"{prefix}: registered marks require ® and a registration reference")
        if tm.get("symbol") == "®" and tm.get("status") != "registered":
            errors.append(f"{prefix}: ® prohibited unless status=registered")
    return errors


def reconcile(data: dict) -> dict:
    terms = data.get("terms", [])
    alias_map: dict[str, str] = {}
    conflicts: list[dict] = []
    for term in terms:
        for name in [term["canonical"], *(term.get("aliases") or [])]:
            key = semantic_key(name)
            prev = alias_map.get(key)
            if prev and prev != term["id"]:
                conflicts.append({"normalized": key, "left": prev, "right": term["id"]})
            alias_map[key] = term["id"]
    return {
        "registry_id": data.get("registry_id"),
        "schema_version": data.get("schema_version"),
        "term_count": len(terms),
        "canonical_count": sum(t.get("status") == "canonical" for t in terms),
        "conflicts": conflicts,
        "result": "PASS" if not conflicts and not validate_registry(data) else "FAIL",
    }


def _source_path(source: dict, root: pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(source["path"])
    return path if path.is_absolute() else root / path


def _markdown_section_names(path: pathlib.Path, section: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    active = False
    names: list[str] = []
    wanted = f"## {section}".strip()
    for line in text.splitlines():
        if line.startswith("## "):
            if active:
                break
            active = line.strip() == wanted
            continue
        if not active:
            continue
        match = re.match(r"\s*-\s+\*\*(.+?)\*\*", line)
        if not match:
            continue
        for raw in match.group(1).split("/"):
            name = raw.strip().replace("`", "")
            if name.startswith("Penta"):
                names.append(name)
    return names


def source_entries(sources_config: dict, root: pathlib.Path = REPO_ROOT) -> list[dict]:
    entries: list[dict] = []
    for source in sources_config.get("sources", []):
        source_id = source["source_id"]
        authority = source.get("authority", "federated")
        path = _source_path(source, root)
        if not path.is_file():
            raise FileNotFoundError(f"registered PentaScribe source missing: {path}")
        kind = source["type"]
        if kind == "penta_component_registry":
            payload = load_registry(path)
            for item in payload.get("components", []):
                entries.append({
                    "id": item["key"],
                    "canonical": item["name"],
                    "aliases": item.get("aliases", []),
                    "source_id": source_id,
                    "source_path": source["path"],
                    "authority": authority,
                    "kind": "component",
                })
        elif kind == "penta_system_registry":
            payload = load_registry(path)
            for item in payload.get("systems", []):
                entries.append({
                    "id": item["machine_key"],
                    "canonical": item["canonical_name"],
                    "aliases": item.get("aliases", []),
                    "source_id": source_id,
                    "source_path": source["path"],
                    "authority": authority,
                    "kind": "system",
                })
        elif kind == "penta_system_extension":
            payload = load_registry(path)
            for item in payload.get("systems", []):
                entries.append({
                    "id": item["machine_key"],
                    "canonical": item["canonical_name"],
                    "aliases": item.get("aliases", []),
                    "source_id": source_id,
                    "source_path": source["path"],
                    "authority": authority,
                    "kind": "system_extension",
                })
        elif kind == "markdown_bold_list_section":
            for name in _markdown_section_names(path, source["section"]):
                entries.append({
                    "id": f"{source_id}:{normalize(name)}",
                    "canonical": name,
                    "aliases": [],
                    "source_id": source_id,
                    "source_path": source["path"],
                    "authority": authority,
                    "kind": "primitive",
                })
        else:
            raise ValueError(f"unsupported PentaScribe source type: {kind}")
    return entries


def build_federated_vocabulary(data: dict, sources_config: dict | None = None, root: pathlib.Path = REPO_ROOT) -> dict[str, dict]:
    vocab: dict[str, dict] = {}
    for term in data.get("terms", []):
        if term.get("status") not in {"canonical", "draft"}:
            continue
        record = {
            "id": term["id"],
            "canonical": term["canonical"],
            "source_id": "pentascribe-seed",
            "source_path": term.get("source"),
            "authority": "pentascribe_canonical" if term.get("status") == "canonical" else "pentascribe_draft",
            "kind": term.get("kind"),
            "term": term,
        }
        for name in [term["canonical"], *(term.get("aliases") or [])]:
            vocab[semantic_key(name)] = record
    if sources_config:
        for entry in source_entries(sources_config, root):
            record = {
                "id": entry["id"],
                "canonical": entry["canonical"],
                "source_id": entry["source_id"],
                "source_path": entry["source_path"],
                "authority": entry["authority"],
                "kind": entry["kind"],
                "term": None,
            }
            for name in [entry["canonical"], *(entry.get("aliases") or [])]:
                vocab.setdefault(semantic_key(name), record)
    return vocab


def blocked_vocabulary(sources_config: dict | None) -> dict[str, dict]:
    if not sources_config:
        return {}
    return {semantic_key(item["name"]): item for item in sources_config.get("blocked_terms", [])}


def federated_index_document(data: dict, sources_config: dict, root: pathlib.Path = REPO_ROOT) -> dict:
    vocab = build_federated_vocabulary(data, sources_config, root)
    unique: dict[tuple[str, str], dict] = {}
    for record in vocab.values():
        key = (record["id"], record["canonical"])
        unique[key] = {k: v for k, v in record.items() if k != "term"}
    return {
        "schema_version": "1.0.0",
        "index_id": "crownthrive.pentascribe.federated-vocabulary",
        "resolved_identity_count": len(unique),
        "lookup_form_count": len(vocab),
        "blocked_term_count": len(blocked_vocabulary(sources_config)),
        "identities": sorted(unique.values(), key=lambda x: (x["canonical"].casefold(), x["id"])),
        "authority_note": "Federated identity recognition preserves source authority; it does not create legal/trademark/provider authority.",
    }


def scan_files(roots: list[pathlib.Path]):
    seen: set[pathlib.Path] = set()
    for root in roots:
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = root.rglob("*")
        else:
            continue
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in SCANNABLE_SUFFIXES:
                continue
            if any(part in {".git", "node_modules", ".venv", "venv"} for part in path.parts):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield path


def discover_candidates(data: dict, roots: list[pathlib.Path], sources_config: dict | None = None, root: pathlib.Path = REPO_ROOT) -> dict:
    federated = build_federated_vocabulary(data, sources_config, root)
    seed_keys = {semantic_key(name): term["id"] for term in data.get("terms", []) for name in [term.get("canonical", ""), *(term.get("aliases") or [])] if name}
    blocked = blocked_vocabulary(sources_config)
    observed = defaultdict(lambda: {"count": 0, "sources": set(), "symbols": set()})
    files_scanned = 0
    for path in scan_files(roots):
        files_scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in PENTA_CANDIDATE_RE.finditer(text):
            name, symbol = match.group(1), match.group(2)
            item = observed[name]
            item["count"] += 1
            if len(item["sources"]) < 8:
                item["sources"].add(path.as_posix())
            if symbol:
                item["symbols"].add(symbol)

    candidates: list[dict] = []
    mark_observations: list[dict] = []
    known_observations: list[dict] = []
    federated_observations: list[dict] = []
    rejected_observations: list[dict] = []
    for name in sorted(observed, key=str.casefold):
        item = observed[name]
        key = semantic_key(name)
        record = {
            "observed": name,
            "count": item["count"],
            "sources": sorted(item["sources"]),
            "symbols": sorted(item["symbols"]),
        }
        owner = seed_keys.get(key)
        resolved = federated.get(key)
        if owner:
            record["term_id"] = owner
            known_observations.append(record)
        elif resolved:
            record.update({
                "term_id": resolved["id"],
                "canonical": resolved["canonical"],
                "authority": resolved["authority"],
                "authority_source": resolved["source_path"],
            })
            federated_observations.append(record)
        elif key in blocked:
            record["status"] = "rejected_existing_name"
            record["reason"] = blocked[key]["reason"]
            rejected_observations.append(record)
        else:
            record["proposed_id"] = normalize(name)
            record["status"] = "candidate_only"
            candidates.append(record)
        if item["symbols"]:
            mark_observations.append({
                "observed": name,
                "symbols": sorted(item["symbols"]),
                "term_id": owner or (resolved or {}).get("id"),
                "note": "Observed symbol use is evidence for review only; it does not establish filing or registration.",
            })
    return {
        "schema_version": "1.1.0",
        "discovery_id": "crownthrive.pentascribe.discovery",
        "files_scanned": files_scanned,
        "candidate_count": len(candidates),
        "federated_observation_count": len(federated_observations),
        "rejected_observation_count": len(rejected_observations),
        "candidates": candidates,
        "known_observations": known_observations,
        "federated_observations": federated_observations,
        "rejected_observations": rejected_observations,
        "mark_observations": mark_observations,
        "authority_note": "Discovery never promotes an unknown term or trademark status. Federation only recognizes identities already admitted by registered canonical sources.",
    }


def render_glossary(terms):
    lines = ["# PentaScribe Canonical Glossary", "", "Generated from `penta/scribe/registry.json`. Do not hand-edit.", ""]
    for term in sorted(terms, key=lambda x: x["canonical"].casefold()):
        if term["status"] == "historical":
            continue
        aliases = ", ".join(term.get("aliases") or [])
        lines += [f"## {term['canonical']}", "", term["definition"]]
        if aliases:
            lines += ["", f"**Aliases:** {aliases}"]
        lines += ["", f"**Status:** `{term['status']}` · **Kind:** `{term['kind']}`", ""]
    return "\n".join(lines).rstrip() + "\n"


def render_dictionary(terms):
    rows = ["# PentaScribe Dictionary", "", "| Term | Kind | Definition | Status |", "| --- | --- | --- | --- |"]
    for term in sorted(terms, key=lambda x: x["canonical"].casefold()):
        rows.append(f"| {term['canonical']} | {term['kind']} | {term['definition'].replace('|','/')} | {term['status']} |")
    return "\n".join(rows) + "\n"


def render_index(terms):
    groups = defaultdict(list)
    for term in terms:
        for tag in term.get("tags") or ["untagged"]:
            groups[tag].append(term["canonical"])
    out = ["# PentaScribe Institutional Index", "", "Generated semantic/tag index.", ""]
    for tag in sorted(groups):
        out += [f"## {tag}", "", *[f"- {name}" for name in sorted(set(groups[tag]))], ""]
    return "\n".join(out).rstrip() + "\n"


def render_faq(terms):
    out = ["# PentaScribe FAQ Index", "", "Questions are governed discovery prompts; answers resolve to the canonical term definition/source.", ""]
    for term in sorted(terms, key=lambda x: x["canonical"].casefold()):
        for question in term.get("faq") or []:
            out += [f"## {question}", "", f"**{term['canonical']}:** {term['definition']}", "", f"Source: `{term['source']}`", ""]
    return "\n".join(out).rstrip() + "\n"


def render_trademarks(terms):
    out = [
        "# PentaScribe Trademark & Mark-Use Ledger",
        "",
        "This is an institutional tracking ledger, **not a legal registration database or legal opinion**. PentaScribe must never upgrade a mark to `filed` or `registered` without authoritative legal evidence.",
        "",
        "| Mark / Name | Ledger status | Display symbol | Jurisdiction | Registration reference |",
        "| --- | --- | --- | --- | --- |",
    ]
    for term in sorted(terms, key=lambda x: x["canonical"].casefold()):
        tm = term.get("trademark") or {}
        out.append(f"| {term['canonical']} | {tm.get('status','unverified')} | {tm.get('symbol') or '—'} | {tm.get('jurisdiction') or '—'} | {tm.get('registration') or '—'} |")
    return "\n".join(out) + "\n"


def render_aliases(terms):
    out = ["# PentaScribe Alias & Deprecation Index", "", "| Alias | Canonical | Term status |", "| --- | --- | --- |"]
    for term in sorted(terms, key=lambda x: x["canonical"].casefold()):
        for alias in term.get("aliases") or []:
            out.append(f"| {alias} | {term['canonical']} | {term['status']} |")
    return "\n".join(out) + "\n"


def compile_registry(data: dict, out_dir: pathlib.Path) -> list[pathlib.Path]:
    errors = validate_registry(data)
    if errors:
        raise ValueError("\n".join(errors))
    terms = data["terms"]
    out_dir.mkdir(parents=True, exist_ok=True)
    products = {
        "GLOSSARY.md": render_glossary(terms),
        "DICTIONARY.md": render_dictionary(terms),
        "INDEX.md": render_index(terms),
        "FAQ.md": render_faq(terms),
        "TRADEMARK_LEDGER.md": render_trademarks(terms),
        "ALIASES.md": render_aliases(terms),
        "reconciliation.json": json.dumps(reconcile(data), indent=2) + "\n",
    }
    paths: list[pathlib.Path] = []
    for name, content in products.items():
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "reconcile", "discover", "federate", "compile"])
    parser.add_argument("--registry", default="penta/scribe/registry.json")
    parser.add_argument("--sources", default="penta/scribe/sources.registry.json")
    parser.add_argument("--out", default="docs/generated/pentascribe")
    parser.add_argument("--scan", nargs="*", default=["README.md", "docs", "data", "penta"])
    args = parser.parse_args(argv)
    data = load_registry(pathlib.Path(args.registry))
    sources_path = pathlib.Path(args.sources) if args.sources else None
    sources = load_sources(sources_path) if sources_path and sources_path.is_file() else None
    if args.command == "validate":
        errors = validate_registry(data)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        if sources:
            source_entries(sources)
        print(f"PASS: {len(data['terms'])} seed terms; federation={'enabled' if sources else 'disabled'}")
        return 0
    if args.command == "reconcile":
        result = reconcile(data)
        print(json.dumps(result, indent=2))
        return 0 if result["result"] == "PASS" else 1
    if args.command == "federate":
        if not sources:
            print("federation sources are required", file=sys.stderr)
            return 1
        result = federated_index_document(data, sources)
        text = json.dumps(result, indent=2) + "\n"
        if args.out == "-":
            print(text, end="")
        else:
            out = pathlib.Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(out)
        return 0
    if args.command == "discover":
        result = discover_candidates(data, [pathlib.Path(item) for item in args.scan], sources)
        text = json.dumps(result, indent=2) + "\n"
        if args.out == "-":
            print(text, end="")
        else:
            out = pathlib.Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(out)
        return 0
    try:
        paths = compile_registry(data, pathlib.Path(args.out))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("compiled:", ", ".join(str(path) for path in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
