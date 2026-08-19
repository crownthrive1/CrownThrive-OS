#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "developers/manifests/chlom-build-cells.v1.json"
UPSTREAM = ROOT / "developers/manifests/chlom-upstream-components.v1.json"


def render() -> str:
    cells = json.loads(CELLS.read_text(encoding="utf-8"))
    upstream = json.loads(UPSTREAM.read_text(encoding="utf-8"))
    lines = [
        "# CHLOM Executable Build Status",
        "",
        "> Generated from governed machine manifests. Runtime/deployment claims remain evidence-gated.",
        "",
        f"Program state: `{cells['state']}`",
        f"Current phase: `{cells['phase']}`",
        "",
        "## Build cells",
        "",
        "| Cell | Host agents | State |",
        "| --- | --- | --- |",
    ]
    for cell in cells["cells"]:
        lines.append(f"| `{cell['cell_id']}` — {cell['name']} | {', '.join(cell['host_agents'])} | `{cell['current_state']}` |")
    lines.extend(["", "## Upstream candidates", "", "| Component | Repository | License | Adoption state |", "| --- | --- | --- | --- |"])
    for item in upstream["candidates"]:
        lines.append(f"| `{item['component_id']}` | `{item['repository']}` | `{item['license']}` | `{item['adoption_state']}` |")
    lines.extend(["", "No upstream candidate is CHLOM authority. Production adoption requires the manifest adoption gate.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = render()
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
