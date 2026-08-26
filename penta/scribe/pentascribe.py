#!/usr/bin/env python3
"""PentaScribe: deterministic institutional language compiler for CrownThrive."""
from __future__ import annotations
import argparse, json, pathlib, re, sys
from collections import defaultdict

ALLOWED_TERM_STATUS = {"draft", "canonical", "deprecated", "historical"}
ALLOWED_TM_STATUS = {"unverified", "claimed_public_display", "filed", "registered", "abandoned", "not_applicable"}
SCANNABLE_SUFFIXES = {".md", ".mdx", ".json", ".yml", ".yaml", ".py", ".txt"}
# The negative lookahead is intentional: ™/® are non-word characters, so a trailing
# \b after an optional symbol drops the symbol from the match. Keep the boundary
# before the Penta token and require a non-word/end after the optional mark instead.
PENTA_CANDIDATE_RE = re.compile(r"\b(Penta[A-Z][A-Za-z0-9]+|PENTA)([™®]?)(?![A-Za-z0-9_])")

def load_registry(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

def semantic_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold().replace("™", "").replace("®", ""))

def validate_registry(data: dict) -> list[str]:
    errors = []
    seen_ids, seen_names = set(), {}
    if data.get("schema_version") != "1.0.0": errors.append("unsupported schema_version")
    for i, term in enumerate(data.get("terms", [])):
        prefix = f"terms[{i}]"
        for key in ("id", "canonical", "kind", "definition", "status", "source", "trademark"):
            if not term.get(key): errors.append(f"{prefix}: missing {key}")
        tid = term.get("id")
        if tid in seen_ids: errors.append(f"{prefix}: duplicate id {tid}")
        seen_ids.add(tid)
        if tid and normalize(tid) != tid: errors.append(f"{prefix}: id must be normalized kebab-case")
        if term.get("status") not in ALLOWED_TERM_STATUS: errors.append(f"{prefix}: invalid status {term.get('status')}")
        tm = term.get("trademark") or {}
        if tm.get("status") not in ALLOWED_TM_STATUS: errors.append(f"{prefix}: invalid trademark.status {tm.get('status')}")
        for name in [term.get("canonical", ""), *(term.get("aliases") or [])]:
            if not name: continue
            key = name.casefold().replace("™", "").replace("®", "").strip()
            owner = seen_names.get(key)
            if owner and owner != tid: errors.append(f"{prefix}: name/alias collision '{name}' with {owner}")
            seen_names[key] = tid
        if tm.get("status") == "registered" and (tm.get("symbol") != "®" or not tm.get("registration")):
            errors.append(f"{prefix}: registered marks require ® and a registration reference")
        if tm.get("symbol") == "®" and tm.get("status") != "registered":
            errors.append(f"{prefix}: ® prohibited unless status=registered")
    return errors

def reconcile(data: dict) -> dict:
    terms, alias_map, conflicts = data.get("terms", []), {}, []
    for term in terms:
        for name in [term["canonical"], *(term.get("aliases") or [])]:
            key = name.casefold().replace("™", "").replace("®", "").strip()
            prev = alias_map.get(key)
            if prev and prev != term["id"]: conflicts.append({"normalized": key, "left": prev, "right": term["id"]})
            alias_map[key] = term["id"]
    return {"registry_id": data.get("registry_id"), "schema_version": data.get("schema_version"), "term_count": len(terms), "canonical_count": sum(t.get("status") == "canonical" for t in terms), "conflicts": conflicts, "result": "PASS" if not conflicts and not validate_registry(data) else "FAIL"}

def known_semantic_keys(data: dict) -> dict[str, str]:
    known = {}
    for term in data.get("terms", []):
        for name in [term.get("canonical", ""), *(term.get("aliases") or [])]:
            if name: known[semantic_key(name)] = term["id"]
    return known

def scan_files(roots: list[pathlib.Path]):
    seen = set()
    for root in roots:
        if root.is_file(): candidates = [root]
        elif root.is_dir(): candidates = root.rglob("*")
        else: continue
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in SCANNABLE_SUFFIXES: continue
            if any(part in {".git", "node_modules", ".venv", "venv"} for part in path.parts): continue
            resolved = path.resolve()
            if resolved in seen: continue
            seen.add(resolved); yield path

def discover_candidates(data: dict, roots: list[pathlib.Path]) -> dict:
    known = known_semantic_keys(data)
    observed = defaultdict(lambda: {"count": 0, "sources": set(), "symbols": set()})
    files_scanned = 0
    for path in scan_files(roots):
        files_scanned += 1
        try: text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError): continue
        for match in PENTA_CANDIDATE_RE.finditer(text):
            name, symbol = match.group(1), match.group(2)
            item = observed[name]
            item["count"] += 1
            if len(item["sources"]) < 8: item["sources"].add(path.as_posix())
            if symbol: item["symbols"].add(symbol)
    candidates, mark_observations, known_observations = [], [], []
    for name in sorted(observed, key=str.casefold):
        item = observed[name]
        record = {"observed": name, "count": item["count"], "sources": sorted(item["sources"]), "symbols": sorted(item["symbols"])}
        owner = known.get(semantic_key(name))
        if owner:
            record["term_id"] = owner; known_observations.append(record)
        else:
            record["proposed_id"] = normalize(name); record["status"] = "candidate_only"; candidates.append(record)
        if item["symbols"]:
            mark_observations.append({"observed": name, "symbols": sorted(item["symbols"]), "term_id": owner, "note": "Observed symbol use is evidence for review only; it does not establish filing or registration."})
    return {"schema_version": "1.0.0", "discovery_id": "crownthrive.pentascribe.discovery", "files_scanned": files_scanned, "candidate_count": len(candidates), "candidates": candidates, "known_observations": known_observations, "mark_observations": mark_observations, "authority_note": "Discovery never promotes a term or trademark status. Governance must admit candidates into the canonical registry."}

def render_glossary(terms):
    lines = ["# PentaScribe Canonical Glossary", "", "Generated from `penta/scribe/registry.json`. Do not hand-edit.", ""]
    for t in sorted(terms, key=lambda x: x["canonical"].casefold()):
        if t["status"] == "historical": continue
        aliases = ", ".join(t.get("aliases") or [])
        lines += [f"## {t['canonical']}", "", t["definition"]]
        if aliases: lines += ["", f"**Aliases:** {aliases}"]
        lines += ["", f"**Status:** `{t['status']}` · **Kind:** `{t['kind']}`", ""]
    return "\n".join(lines).rstrip() + "\n"

def render_dictionary(terms):
    rows = ["# PentaScribe Dictionary", "", "| Term | Kind | Definition | Status |", "| --- | --- | --- | --- |"]
    for t in sorted(terms, key=lambda x: x["canonical"].casefold()): rows.append(f"| {t['canonical']} | {t['kind']} | {t['definition'].replace('|','/')} | {t['status']} |")
    return "\n".join(rows) + "\n"

def render_index(terms):
    groups = defaultdict(list)
    for t in terms:
        for tag in t.get("tags") or ["untagged"]: groups[tag].append(t["canonical"])
    out = ["# PentaScribe Institutional Index", "", "Generated semantic/tag index.", ""]
    for tag in sorted(groups): out += [f"## {tag}", "", *[f"- {name}" for name in sorted(set(groups[tag]))], ""]
    return "\n".join(out).rstrip() + "\n"

def render_faq(terms):
    out = ["# PentaScribe FAQ Index", "", "Questions are governed discovery prompts; answers resolve to the canonical term definition/source.", ""]
    for t in sorted(terms, key=lambda x: x["canonical"].casefold()):
        for q in t.get("faq") or []: out += [f"## {q}", "", f"**{t['canonical']}:** {t['definition']}", "", f"Source: `{t['source']}`", ""]
    return "\n".join(out).rstrip() + "\n"

def render_trademarks(terms):
    out = ["# PentaScribe Trademark & Mark-Use Ledger", "", "This is an institutional tracking ledger, **not a legal registration database or legal opinion**. PentaScribe must never upgrade a mark to `filed` or `registered` without authoritative legal evidence.", "", "| Mark / Name | Ledger status | Display symbol | Jurisdiction | Registration reference |", "| --- | --- | --- | --- | --- |"]
    for t in sorted(terms, key=lambda x: x["canonical"].casefold()):
        tm = t.get("trademark") or {}; out.append(f"| {t['canonical']} | {tm.get('status','unverified')} | {tm.get('symbol') or '—'} | {tm.get('jurisdiction') or '—'} | {tm.get('registration') or '—'} |")
    return "\n".join(out) + "\n"

def render_aliases(terms):
    out = ["# PentaScribe Alias & Deprecation Index", "", "| Alias | Canonical | Term status |", "| --- | --- | --- |"]
    for t in sorted(terms, key=lambda x: x["canonical"].casefold()):
        for alias in t.get("aliases") or []: out.append(f"| {alias} | {t['canonical']} | {t['status']} |")
    return "\n".join(out) + "\n"

def compile_registry(data: dict, out_dir: pathlib.Path) -> list[pathlib.Path]:
    errors = validate_registry(data)
    if errors: raise ValueError("\n".join(errors))
    terms = data["terms"]; out_dir.mkdir(parents=True, exist_ok=True)
    products = {"GLOSSARY.md": render_glossary(terms), "DICTIONARY.md": render_dictionary(terms), "INDEX.md": render_index(terms), "FAQ.md": render_faq(terms), "TRADEMARK_LEDGER.md": render_trademarks(terms), "ALIASES.md": render_aliases(terms), "reconciliation.json": json.dumps(reconcile(data), indent=2) + "\n"}
    paths = []
    for name, content in products.items():
        path = out_dir / name; path.write_text(content, encoding="utf-8"); paths.append(path)
    return paths

def main(argv=None) -> int:
    p = argparse.ArgumentParser(); p.add_argument("command", choices=["validate", "reconcile", "discover", "compile"]); p.add_argument("--registry", default="penta/scribe/registry.json"); p.add_argument("--out", default="docs/generated/pentascribe"); p.add_argument("--scan", nargs="*", default=["README.md", "docs", "data", "penta"]); args = p.parse_args(argv)
    data = load_registry(pathlib.Path(args.registry))
    if args.command == "validate":
        errors = validate_registry(data)
        if errors: print("\n".join(errors), file=sys.stderr); return 1
        print(f"PASS: {len(data['terms'])} terms"); return 0
    if args.command == "reconcile":
        result = reconcile(data); print(json.dumps(result, indent=2)); return 0 if result["result"] == "PASS" else 1
    if args.command == "discover":
        result = discover_candidates(data, [pathlib.Path(item) for item in args.scan])
        text = json.dumps(result, indent=2) + "\n"
        if args.out == "-": print(text, end="")
        else:
            out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text, encoding="utf-8"); print(out)
        return 0
    try: paths = compile_registry(data, pathlib.Path(args.out))
    except ValueError as exc: print(str(exc), file=sys.stderr); return 1
    print("compiled:", ", ".join(str(p) for p in paths)); return 0

if __name__ == "__main__": raise SystemExit(main())
