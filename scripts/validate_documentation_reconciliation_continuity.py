#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "frameworks/documentation-reconciliation-continuity/framework.manifest.v1.json"
ARTICLE = ROOT / "frameworks/documentation-reconciliation-continuity/article-rebuild-contract.v1.json"
TOOLS = ROOT / "plugins/documentation-reconciliation-continuity/tool-contracts.json"
RECEIPT = ROOT / "data/documentation/sprint-1-gap-pass-receipt.v1.json"

errors = []

def load(path):
    if not path.exists():
        errors.append(f"missing:{path.relative_to(ROOT)}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid_json:{path.relative_to(ROOT)}:{exc}")
        return {}

manifest = load(MANIFEST)
article = load(ARTICLE)
tools = load(TOOLS)
receipt = load(RECEIPT)

if manifest.get("framework_id") != "ct.framework.documentation-reconciliation-continuity":
    errors.append("framework_id_mismatch")

passes = manifest.get("sprint_contract", {})
if passes.get("pass_a") != "stale_state_reconciliation":
    errors.append("missing_pass_a")
if passes.get("pass_b") != "gap_closure_and_internal_link_continuity":
    errors.append("missing_pass_b")

phase = manifest.get("phase_impact", {})
if phase.get("named_canonical_phases") != list(range(1, 11)):
    errors.append("phase_1_10_contract_invalid")
if phase.get("reserved_horizon_slots") != list(range(11, 21)):
    errors.append("phase_11_20_horizon_invalid")

rmct = manifest.get("rmct", {})
if rmct.get("literal_token") != "RMCT" or rmct.get("definition_state") != "needs_owner_validation":
    errors.append("rmct_must_remain_unexpanded_until_authoritative")

if article.get("forensic_baseline", {}).get("legacy_title_count") != 795:
    errors.append("article_baseline_count_mismatch")

expected_dispositions = {
    "canonical_article", "merged_successor", "permanent_redirect",
    "restricted_record", "superseded_history", "unresolved_source"
}
if set(article.get("terminal_dispositions", [])) != expected_dispositions:
    errors.append("article_disposition_contract_invalid")

if tools.get("authority", {}).get("self_certification") is not False:
    errors.append("self_certification_must_be_false")

if receipt:
    if receipt.get("framework_id") != manifest.get("framework_id"):
        errors.append("receipt_framework_id_mismatch")
    if receipt.get("pass_a_state") not in {"pass", "pass_with_deltas", "hold"}:
        errors.append("receipt_pass_a_state_invalid")
    if receipt.get("pass_b_state") not in {"pass", "pass_with_deltas", "hold"}:
        errors.append("receipt_pass_b_state_invalid")
    if receipt.get("phase_3_entry") != "blocked_pending_phase_2_99_hard_exit":
        errors.append("phase_3_gate_widened")

if errors:
    print("FAIL_DOCUMENTATION_RECONCILIATION_CONTINUITY")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("PASS_DOCUMENTATION_RECONCILIATION_CONTINUITY")
print("framework=ct.framework.documentation-reconciliation-continuity")
print("article_baseline=795")
print("phase_horizon=1-20")
print("phase_11_20_state=reserved_definition_required")
