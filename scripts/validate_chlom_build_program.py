#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "developers/manifests/chlom-build-cells.v1.json"
UPSTREAM = ROOT / "developers/manifests/chlom-upstream-components.v1.json"
GENERATOR = ROOT / "scripts/generate_chlom_living_status.py"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    cells = json.loads(CELLS.read_text(encoding="utf-8"))
    upstream = json.loads(UPSTREAM.read_text(encoding="utf-8"))
    if cells.get("phase") != "2.99" or cells.get("state") != "prototype_build_active_phase3_activation_blocked":
        fail("CHLOM build state must remain Phase 2.99 prototype / Phase 3 activation blocked")
    records = cells.get("cells", [])
    if len(records) != 10:
        fail(f"Expected exactly 10 CHLOM build cells, found {len(records)}")
    ids = [row.get("cell_id") for row in records]
    if len(ids) != len(set(ids)):
        fail("CHLOM cell IDs must be unique")
    if cells.get("rules", {}).get("cells_are_quorum_voters") is not False:
        fail("CHLOM subcells must not create extra sovereign votes")
    if cells.get("rules", {}).get("production_activation_before_phase3") is not False:
        fail("Phase 2.99 CHLOM packet cannot activate production")
    for excluded in cells.get("active_packet_exclusions", []):
        if any(excluded in path for row in records for path in row.get("scope", [])):
            fail(f"Cell scope collides with active governance packet path: {excluded}")

    expected_upstream = {
        "open-policy-agent/opa": "Apache-2.0",
        "openfga/openfga": "Apache-2.0",
        "cedar-policy/cedar": "Apache-2.0",
        "temporalio/temporal": "MIT",
    }
    actual = {row.get("repository"): row.get("license") for row in upstream.get("candidates", [])}
    if actual != expected_upstream:
        fail(f"Upstream candidate/license set drifted: {actual!r}")
    if any(row.get("chlom_authority") is not False for row in upstream["candidates"]):
        fail("No upstream component may become CHLOM institutional authority by manifest inference")

    required_files = [
        ROOT / "reference/chlom_runtime/model.py",
        ROOT / "reference/chlom_runtime/policy.py",
        ROOT / "reference/chlom_runtime/dail.py",
        ROOT / "reference/chlom_runtime/docs_impact.py",
        ROOT / "reference/chlom_runtime/engine.py",
        ROOT / "reference/chlom_runtime/policies/core.v0.json",
        ROOT / "reference/chlom_runtime/tests/test_runtime.py",
    ]
    for path in required_files:
        if not path.is_file():
            fail(f"Missing reference-runtime file: {path.relative_to(ROOT)}")

    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "reference.chlom_runtime.tests.test_runtime"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if tests.returncode != 0:
        sys.stderr.write(tests.stdout + tests.stderr)
        fail("CHLOM reference-runtime unit tests failed")

    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp) / "status.md"
        generated = subprocess.run([sys.executable, str(GENERATOR), "--output", str(output)], cwd=ROOT)
        if generated.returncode != 0 or not output.is_file():
            fail("CHLOM living-status generation failed")
        text = output.read_text(encoding="utf-8")
        if "CHLOM Executable Build Status" not in text or "No upstream candidate is CHLOM authority" not in text:
            fail("Generated living status is missing governance invariants")

    print("CHLOM executable build-program validation: PASS")
    print("- 10 non-voting builder cells with bounded ownership")
    print("- reference kernel/policy/DAIL/docs-impact runtime tests: PASS")
    print("- upstream candidate licenses pinned in intake manifest")
    print("- production activation remains blocked until Phase 3 hard entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
