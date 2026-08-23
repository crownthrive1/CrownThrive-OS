#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "data/documentation/sprint-1-scope.v1.json"

scope = json.loads(SCOPE.read_text(encoding="utf-8"))
minimum = int(scope.get("minimum_internal_continuity_links", 2))
exceptions = set(scope.get("exceptions", []))
errors = []
results = []

markdown_link = re.compile(r"\]\((/[^)]+)\)")
jsx_link = re.compile(r"\b(?:href|to)=['\"](/[^'\"]+)['\"]")

for rel in scope["pages"]:
    path = ROOT / rel
    if not path.exists():
        errors.append(f"missing_scope_page:{rel}")
        continue
    text = path.read_text(encoding="utf-8")
    links = set(markdown_link.findall(text)) | set(jsx_link.findall(text))
    links = {x.split("#", 1)[0] for x in links if x and not x.startswith("//")}
    results.append((rel, len(links), sorted(links)))
    if rel not in exceptions and len(links) < minimum:
        errors.append(f"insufficient_internal_continuity_links:{rel}:{len(links)}<{minimum}")

print(f"scope_pages={len(scope['pages'])}")
for rel, count, _ in results:
    print(f"{count:02d} {rel}")

if errors:
    print("FAIL_SPRINT_DOCUMENTATION_CONTINUITY")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_SPRINT_DOCUMENTATION_CONTINUITY")
