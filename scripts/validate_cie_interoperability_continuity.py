#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers/manifests/cie-interoperability-continuity.v1.json"
SCHEMA_PATH = ROOT / "developers/schemas/cie-interoperability.v1.schema.json"
COMMERCIAL_PATH = ROOT / "developers/manifests/cie-commercialization-candidate.v1.json"
NEXT_PATH = ROOT / "developers/manifests/convergent-ecosystem-research-handoff.v1.json"
MIGRATION_PATH = ROOT / "supabase/migrations/20260822190000_cie_interoperability_continuity_candidate.sql"
DOC_PATH = ROOT / "doctrine/cultural-imprint-engine.mdx"
CHANGELOG_PATH = ROOT / "changelog/phase-2-99-cie-interoperability-continuity-2026-08-22.mdx"


def fail(message):
    raise SystemExit(f"FAIL: {message}")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


manifest = load(MANIFEST_PATH)
load(SCHEMA_PATH)
commercial = load(COMMERCIAL_PATH)
next_fw = load(NEXT_PATH)
migration = MIGRATION_PATH.read_text(encoding="utf-8")
doc = DOC_PATH.read_text(encoding="utf-8")
changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

if manifest["exact_sources"]["canonical_main_at_start"] != "c7f14b73cff09f00a8f94f15a8587289de18ff7b":
    fail("packet base main SHA mismatch")
if manifest["exact_sources"]["issues"] != [84, 98, 99, 100, 123, 130, 131, 148]:
    fail("required governance issue source set mismatch")
if manifest["child_repository"]["github_repository_id"] != 1341314455:
    fail("immutable child repository ID mismatch")
for key in ("physical_repository_required",):
    if manifest["child_repository"][key] is not True:
        fail(f"child {key} must be true")
for key in ("operationally_enabled", "runtime_integration_allowed", "can_vote"):
    if manifest["child_repository"][key] is not False:
        fail(f"child {key} must be false")
if manifest["child_repository"]["federation_state"] != "PROVISIONED_UNLINKED":
    fail("child must remain PROVISIONED_UNLINKED")
if not re.fullmatch(r"[0-9a-f]{64}", manifest["child_repository"]["contract_sha256"]):
    fail("child contract digest malformed")
if manifest["framework_agent"]["can_vote"] or manifest["framework_agent"]["can_certify"] or manifest["framework_agent"]["can_self_activate"]:
    fail("framework agent authority escaped fail-closed state")
if manifest["framework_agent"]["subagents"]["sync_agents_allowed"] is not False:
    fail("sync_agents must remain disabled")
if manifest["protected_ip"]["public_digest"] != "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2":
    fail("protected algorithm digest mismatch")
if manifest["protected_ip"]["public_repository_contains_protected_logic"] is not False:
    fail("protected implementation publication prohibited")
if manifest["chlom_integration"]["transport"] != "SERVICE_ONLY_GOVERNED_GATEWAY" or manifest["chlom_integration"]["direct_public_rpc_allowed"] is not False:
    fail("CHLOM integration must remain service-only")
if manifest["supabase_projection"]["migration_applied"] is not False or manifest["supabase_projection"]["provider_write_authorized"] is not False:
    fail("Supabase projection must remain unapplied")
if manifest["mintlify_projection"]["production_mintlify_write_performed"] is not False:
    fail("production Mintlify write must remain false")

for obj, label in ((manifest["commercialization"], "packet commercialization"), (commercial["commercial_controls"], "commercial manifest")):
    for key in ("exact_price_authorized", "checkout_enabled", "customer_entitlement_active"):
        if obj[key] is not False:
            fail(f"{label} {key} must remain false")
if commercial["commercial_controls"]["stripe_product_authorized"] or commercial["commercial_controls"]["stripe_price_authorized"]:
    fail("Stripe activation prohibited")
if next_fw["state"] != "RESEARCH_CANDIDATE" or next_fw["agent_identity_state"] != "RESERVED_NOT_BOUND":
    fail("Convergent Ecosystem may not advance beyond research")
if next_fw["can_vote"] or next_fw["operationally_enabled"] or next_fw["transport_identity_created"] or next_fw["sync_agents_used"]:
    fail("Convergent Ecosystem authority or operation activated")

for forbidden_true in (
    "can_vote = true", "operationally_enabled = true", "public_activation_allowed = true",
    "exact_price_authorized = true", "checkout_enabled = true", "customer_entitlement_active = true",
):
    if forbidden_true in migration.lower():
        fail(f"migration contains forbidden activation assignment: {forbidden_true}")
if "CANDIDATE ONLY — NOT APPLIED BY AGENT C" not in migration:
    fail("migration candidate warning missing")
if "Agentic interoperability boundary" not in doc or "service-only" not in doc.lower():
    fail("canonical doctrine interoperability boundary missing")
if "No activation occurred" not in changelog:
    fail("changelog activation disclaimer missing")

packet_files = [MANIFEST_PATH, SCHEMA_PATH, COMMERCIAL_PATH, NEXT_PATH, MIGRATION_PATH, DOC_PATH, CHANGELOG_PATH]
secret_patterns = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r'(?i)(password|client_secret|service_role_key)\s*[:=]\s*[\'"][^\'"]+'),
]
for path in packet_files:
    text = path.read_text(encoding="utf-8")
    for pattern in secret_patterns:
        if pattern.search(text):
            fail(f"possible credential material in {path}")

stage = manifest["lifecycle_state"]
if stage == "PARENT_ANCHOR_PREPARED":
    if manifest["parent_anchor"]["anchor_sha"] != "PENDING_COMMIT_SHA":
        fail("prepared anchor must use exact pending sentinel")
elif stage == "PROVISIONED_UNLINKED":
    for field in (manifest["parent_anchor"]["anchor_sha"], manifest["child_repository"]["proposal_head_sha"]):
        if not re.fullmatch(r"[0-9a-f]{40}", field):
            fail("final packet exact SHA missing")
    if not isinstance(manifest["parent_anchor"]["draft_pr"], int) or not isinstance(manifest["child_repository"]["draft_pr"], int):
        fail("final packet exact draft PR numbers missing")
else:
    fail("unsupported lifecycle state")

print(json.dumps({
    "status": "PASS",
    "lifecycle_state": stage,
    "child_state": manifest["child_repository"]["federation_state"],
    "operationally_enabled": manifest["child_repository"]["operationally_enabled"],
    "can_vote": manifest["child_repository"]["can_vote"],
    "commercial_state": commercial["state"],
    "next_framework_state": next_fw["state"],
}, sort_keys=True))
