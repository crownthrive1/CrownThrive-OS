#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for f in "$ROOT"/bin/*.sh; do bash -n "$f"; done
python3 -m py_compile "$ROOT/bin/chlom_wallet_protocol.py"
python3 "$ROOT/bin/chlom_wallet_protocol.py" validate-policy --policy "$ROOT/config/policy.base-usdc.json" >/dev/null
python3 -m unittest discover -s "$ROOT/tests" -p 'test_*.py' -v
python3 - <<'PY' "$ROOT"
import json,pathlib,sys
root=pathlib.Path(sys.argv[1])
for path in sorted(root.rglob('*.json')):
    json.loads(path.read_text())
print('JSON_PARSE_PASS')
PY
