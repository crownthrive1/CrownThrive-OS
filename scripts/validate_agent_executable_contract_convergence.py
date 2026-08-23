#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/agent-executable-contract-convergence.v1.json"

REQUIRED = [
    "developers/manifests/agent-executable-contract-convergence.v1.json",
    "standards/executable-agent-contract-and-version-convergence.md",
    "skills/chlom-wallet-independent-review/SKILL.md",
    "skills/sites-fleet-orchestration/SKILL.md",
    "skills/frameworks/chlom/SKILL.md",
    "skills/frameworks/cultural-imprint-engine/SKILL.md",
    "skills/frameworks/convergent-ecosystem/SKILL.md",
    "skills/frameworks/corridor-architecture/SKILL.md",
    "skills/frameworks/hybrid-incubator/SKILL.md",
    "skills/frameworks/mm-suites/SKILL.md",
    "skills/frameworks/one-seat-multiple-industries/SKILL.md",
    "skills/frameworks/thrive-flywheel/SKILL.md",
]

EXPECTED_CAPABILITIES = {
    "ct.capability.architecture-self-awareness.execute.v1",
    "ct.capability.chlom-wallet.independent-review.v2",
    "ct.capability.commercial-release.worker-plan.v1",
    "ct.capability.css.agent-contract.v1",
    "ct.capability.framework-precompile.inspect.v1",
    "ct.capability.sites-fleet.inspect.v1",
}

missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
if missing:
    raise SystemExit(f"missing executable-contract source files: {missing}")

manifest = json.loads(MANIFEST.read_text())
if manifest.get("schema_version") != "1.0.0":
    raise SystemExit("unexpected convergence manifest schema version")
if manifest.get("state") != "CONTROLLED_TEST":
    raise SystemExit("convergence manifest must remain CONTROLLED_TEST")

caps = manifest.get("executable_capabilities", [])
ids = {c.get("id") for c in caps}
if ids != EXPECTED_CAPABILITIES:
    raise SystemExit(f"capability set mismatch: {sorted(ids)}")
for cap in caps:
    if cap.get("state") != "controlled_test" or cap.get("D3_auto") is not False or cap.get("provider_write") is not False:
        raise SystemExit(f"unsafe executable capability projection: {cap.get('id')}")

sealed = manifest.get("sealed_commercial_algorithms", {})
if sealed.get("count") != 8:
    raise SystemExit("sealed commercial algorithm count must remain eight")
if sealed.get("executor_state") != "NOT_MATERIALIZED":
    raise SystemExit("sealed commercial algorithms may not be projected executable")
if sealed.get("private_method_executed") is not False or sealed.get("activation_allowed") is not False:
    raise SystemExit("private commercial algorithm methods must remain unexecuted and disabled")

bounds = manifest.get("hard_boundaries", {})
for key in (
    "provider_writes_enabled_by_this_control",
    "checkout_enabled_by_this_control",
    "money_movement_enabled_by_this_control",
    "rights_grants_enabled_by_this_control",
    "secret_body_return",
    "private_algorithm_body_in_source",
    "new_scheduler_plane_created",
):
    if bounds.get(key) is not False:
        raise SystemExit(f"hard boundary must be false: {key}")
if bounds.get("D3_human_reserved") is not True:
    raise SystemExit("D3 must remain human-reserved")

for rel in REQUIRED[2:]:
    text = (ROOT / rel).read_text().lower()
    if "controlled-test" not in text:
        raise SystemExit(f"controlled-test boundary missing: {rel}")
    if "d3" not in text:
        raise SystemExit(f"D3 boundary missing: {rel}")

print("PASS: executable-agent contract convergence source artifacts are bounded and internally consistent")
