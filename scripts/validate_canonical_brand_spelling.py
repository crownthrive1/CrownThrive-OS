#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {'.md', '.mdx', '.json', '.yml', '.yaml', '.py', '.txt'}
SKIP_DIRS = {'.git', '.venv', 'venv', 'node_modules', '.mintlify', '__pycache__'}
FORBIDDEN = 'Crown Thrive'
errors = []

for path in ROOT.rglob('*'):
    if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
        continue
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        continue
    text = path.read_text(encoding='utf-8', errors='strict')
    for lineno, line in enumerate(text.splitlines(), 1):
        if FORBIDDEN in line:
            errors.append(f'{rel}:{lineno}:{line.strip()}')

if errors:
    print('FAIL_CANONICAL_BRAND_SPELLING')
    print('Canonical brand spelling is CrownThrive with no space.')
    for error in errors:
        print(error)
    raise SystemExit(1)

print('PASS_CANONICAL_BRAND_SPELLING')
print('canonical_brand=CrownThrive')
print('forbidden_current_mutable_typo=Crown Thrive')
