#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/agent-executable-contract-convergence.v1.json"

REQUIRED = [
    "developers/manifests/agent-executable-contract-convergence.v1.json",
    "standards/executable-agent-contract-and-version-convergence.md",
    "skills/archive-reverse-verifier/SKILL.md",
    "skills/chlom-wallet-independent-review/SKILL.md",
    "skills/master-agent-control/SKILL.md",
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
    "ct.capability.archive-reverse.verify.v1",
    "ct.capability.chlom-wallet.independent-review.v2",
    "ct.capability.commercial-release.worker-plan.v1",
    "ct.capability.css.agent-contract.v1",
    "ct.capability.framework-precompile.inspect.v1",
    "ct.capability.master-agent.control-self-test.v1",
    "ct.capability.repository-child-guardian.cycle.v1",
    "ct.capability.sites-fleet.inspect.v1",
}

missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
if missing:
    raise SystemExit(f"missing executable-contract source files: {missing}")

manifest = json.loads(MANIFEST.read_text())
if manifest.get("schema_version") != "1.1.0":
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

coverage = manifest.get("global_execution_coverage", {})
for key in ("execution_eligible_agents", "privilege_bound_agents", "executable_capability_agents", "operational_presence_agents"):
    if coverage.get(key) != 92:
        raise SystemExit(f"whole-estate execution coverage mismatch for {key}")
if coverage.get("coverage_state") != "PASS_CONTROLLED_TEST":
    raise SystemExit("whole-estate execution coverage must remain controlled-test PASS")

master = manifest.get("master_suite_execution", {})
if master.get("test_subroutes") != 32 or master.get("disabled_dormant_subroutes") != 42:
    raise SystemExit("Master Suite test/dormant counts changed without manifest reconciliation")
if master.get("test_subroutes_with_control_self_test") != 32:
    raise SystemExit("all Master test subroutes must have the control self-test")
if master.get("disabled_subroutes_activated") is not False or master.get("domain_action_executed_by_control_self_test") is not False:
    raise SystemExit("Master control self-test may not activate dormant or domain execution")

archive = manifest.get("archive_reverse_canary", {})
for key in ("ciphertext_hash_verified", "plaintext_hash_verified", "member_found", "contract_digest_match", "exact_scope_short_lived_lease"):
    if archive.get(key) is not True:
        raise SystemExit(f"archive canary invariant failed: {key}")
for key in ("secret_body_returned", "key_material_returned"):
    if archive.get(key) is not False:
        raise SystemExit(f"archive canary secret boundary failed: {key}")

guardian = manifest.get("repository_guardian_canary", {})
if guardian.get("state") != "PASS_CONTROLLED_TEST" or guardian.get("missing_external_observations") != 0:
    raise SystemExit("repository guardian canary is not current controlled-test PASS")
for key in ("destructive_actions", "merge_actions", "child_self_activation_actions"):
    if guardian.get(key) != 0:
        raise SystemExit(f"repository guardian unsafe action detected: {key}")

commercial = manifest.get("commercial_release_execution", {})
if commercial.get("worker_count") != 18 or commercial.get("worker_skill_state") != "test":
    raise SystemExit("Commercial Release workers are not fully promoted to test")
if commercial.get("sealed_algorithm_contract_count") != 8:
    raise SystemExit("sealed commercial algorithm count must remain eight")
if commercial.get("sealed_algorithm_executor_state") != "NOT_MATERIALIZED":
    raise SystemExit("sealed commercial algorithms may not be projected executable")
if commercial.get("private_method_executed") is not False or commercial.get("activation_allowed") is not False:
    raise SystemExit("private commercial algorithm methods must remain unexecuted and disabled")

repair = manifest.get("stale_projection_repairs", {})
if repair.get("thrivebase_suite_canonical_name") != "ThriveBase Account Optimization Suite":
    raise SystemExit("canonical ThriveBase suite name is stale")
if repair.get("canonical_manifest_ref") != "automation/thrivebase-account-optimizer.mdx":
    raise SystemExit("canonical ThriveBase source path is stale")
if repair.get("opaque_identifiers_renamed") is not False:
    raise SystemExit("opaque compatibility identifiers may not be silently renamed")

bounds = manifest.get("hard_boundaries", {})
for key in (
    "provider_writes_enabled_by_this_control",
    "checkout_enabled_by_this_control",
    "money_movement_enabled_by_this_control",
    "rights_grants_enabled_by_this_control",
    "secret_body_return",
    "key_material_return",
    "private_algorithm_body_in_source",
    "new_scheduler_plane_created",
    "disabled_subroutes_auto_activated",
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

print("PASS: executable-agent contract convergence v1.1 is bounded and internally consistent")
