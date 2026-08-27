#!/usr/bin/env python3
"""Close Penta Production Promotion Wave 3 repository convergence gaps.

This utility is intentionally repository-bounded and idempotent. It reconciles
canonical Penta catalogs, binds bounded provider-effect-free adapters for the
already-produced PentaEVIBuilder and PentaImmune runtimes, updates executable
contracts/tests, refreshes repository custody counts, and preserves all human,
provider, economic, legal, security, and D3 authority gates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_INSTITUTIONAL_COMMIT = "12d52fc356e4f34b6298bf9d3c1c4af6fef53444"
RUNTIME_VERSION = "1.4.0"


class GapClosureError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GapClosureError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GapClosureError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def restore_canonical_institutional_services() -> None:
    result = subprocess.run(
        [
            "git",
            "show",
            f"{CANONICAL_INSTITUTIONAL_COMMIT}:data/penta/institutional-services.registry.json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise GapClosureError(
            "cannot restore canonical institutional-services registry from fixed source commit"
        )
    (ROOT / "data/penta/institutional-services.registry.json").write_text(
        result.stdout, encoding="utf-8"
    )


def update_family_registry() -> None:
    path = ROOT / "data/penta/family.registry.json"
    family = load_json(path)
    catalog = {
        "catalog_id": "penta.immune",
        "path": "data/penta/systems.extensions.penta-immune.json",
        "required": True,
        "role": "production_security_resilience_and_evidence_extension",
    }
    catalogs = family.get("catalogs")
    if not isinstance(catalogs, list):
        raise GapClosureError("family registry catalogs must be a list")
    matches = [
        item
        for item in catalogs
        if isinstance(item, dict) and item.get("catalog_id") == catalog["catalog_id"]
    ]
    if len(matches) > 1:
        raise GapClosureError("duplicate penta.immune parent-catalog registrations")
    if matches:
        matches[0].clear()
        matches[0].update(catalog)
    else:
        catalogs.append(catalog)
    family["updated"] = "2026-08-27"
    write_json(path, family)


def update_documentation_and_custody_state() -> int:
    disposition_path = ROOT / "developers/manifests/pentadocs-unlisted-page-dispositions.v1.json"
    disposition = load_json(disposition_path)
    dispositions = disposition.get("dispositions")
    if not isinstance(dispositions, dict):
        raise GapClosureError("PentaDocs dispositions must be an object")
    bucket = dispositions.get("operational_reference_direct_link")
    if not isinstance(bucket, list):
        raise GapClosureError("operational_reference_direct_link must be a list")
    page = "automation/penta-families.mdx"
    if page not in bucket:
        bucket.append(page)
    bucket[:] = sorted(set(str(item) for item in bucket))
    write_json(disposition_path, disposition)

    convergence_path = ROOT / "developers/manifests/supabase-production-convergence-state.v1.json"
    convergence = load_json(convergence_path)
    custody = convergence.get("migration_custody")
    if not isinstance(custody, dict):
        raise GapClosureError("migration_custody must be an object")
    local_count = len(list((ROOT / "supabase/migrations").glob("*.sql")))
    if local_count <= 0:
        raise GapClosureError("repository migration inventory is empty")
    custody["repository_migration_file_count"] = local_count
    write_json(convergence_path, convergence)

    mesh_path = ROOT / "virality-music/system-mesh.mdx"
    mesh = mesh_path.read_text(encoding="utf-8")
    mesh = mesh.replace("../SECURITY.md", "/technology/security-privacy-continuity").replace("/SECURITY.md", "/technology/security-privacy-continuity").replace("/SECURITY", "/technology/security-privacy-continuity")
    mesh_path.write_text(mesh, encoding="utf-8")
    return local_count


PROMOTED_OPERATION_BLOCK = r'''

def _reject_credential_keys(value: Any, *, path: str = "payload") -> None:
    forbidden = {"api_key", "apikey", "token", "password", "secret", "private_key", "credential", "credentials"}
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().casefold().replace("-", "_").replace(" ", "_")
            if normalized in forbidden:
                raise PromotedOperationError(f"credential-like field is not accepted by bounded adapter: {path}.{key}")
            _reject_credential_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_credential_keys(child, path=f"{path}[{index}]")


def _bounded_mapping_rows(value: Any, *, field: str, default: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = default if value is None else value
    if not isinstance(rows, list) or not rows or len(rows) > 50:
        raise PromotedOperationError(f"{field} must contain 1..50 objects")
    if not all(isinstance(row, Mapping) for row in rows):
        raise PromotedOperationError(f"{field} must contain only objects")
    normalized = [dict(row) for row in rows]
    _reject_credential_keys(normalized, path=field)
    return normalized


def evi_builder_evidence_preview(ctx: Any) -> dict[str, Any]:
    runtime_path = ctx.root / "runtime/penta_evi_builder.py"
    test_path = ctx.root / "tests/test_penta_evi_builder.py"
    if not runtime_path.is_file() or not test_path.is_file():
        raise PromotedOperationError("PentaEVIBuilder runtime/test surface is incomplete")
    member = (ctx.snapshot.get("members") or {}).get("penta.evi-builder") or {}
    if member.get("maturity") != "production":
        raise PromotedOperationError("PentaEVIBuilder effective maturity is not production")
    runtime = _load_fixed_module("penta_evi_builder_adapter_preview", runtime_path)
    payload = dict(ctx.payload or {})
    head_sha = payload.get("head_sha")
    if not isinstance(head_sha, str):
        raise PromotedOperationError("evidence_bundle_preview requires payload.head_sha")
    authority_level = payload.get("authority_level", "D2")
    if authority_level not in {"D0", "D1", "D2"}:
        raise PromotedOperationError("bounded evidence preview permits only D0, D1, or D2")
    observations = _bounded_mapping_rows(
        payload.get("observations"),
        field="observations",
        default=[{"kind": "evidence_gap", "result": "bounded_adapter_probe"}],
    )
    claims = _bounded_mapping_rows(
        payload.get("claims"),
        field="claims",
        default=[{"claim": "bundle constructed", "scope": "unverified preview only"}],
    )
    raw_receipts = payload.get("test_receipts") or [
        {
            "name": "adapter-contract",
            "status": "PASS",
            "source": ctx.evidence_refs[0],
            "details": "bounded local evidence-construction probe",
        }
    ]
    if not isinstance(raw_receipts, list) or not raw_receipts or len(raw_receipts) > 50:
        raise PromotedOperationError("test_receipts must contain 1..50 objects")
    receipts = []
    for row in raw_receipts:
        if not isinstance(row, Mapping):
            raise PromotedOperationError("test_receipts must contain only objects")
        receipts.append(
            runtime.TestReceipt(
                str(row.get("name", "")),
                str(row.get("status", "")),
                str(row.get("source", "")),
                str(row.get("details", "")),
            )
        )
    rollback = payload.get("rollback") or {"method": "git_revert", "target": head_sha}
    fallback = payload.get("fallback") or {"method": "hold", "redundancy": "known-good-main"}
    if not isinstance(rollback, Mapping) or not isinstance(fallback, Mapping):
        raise PromotedOperationError("rollback and fallback must be objects")
    _reject_credential_keys([rollback, fallback], path="recovery")
    created_at = payload.get("created_at")
    if created_at is not None and not isinstance(created_at, str):
        raise PromotedOperationError("created_at must be an ISO timestamp string when supplied")
    bundle = runtime.build_bundle(
        work_order_id=str(payload.get("work_order_id", "penta-exec-evi-preview")),
        subject=str(payload.get("subject", "bounded PentaEVIBuilder evidence preview")),
        source_ref=str(payload.get("source_ref", ctx.evidence_refs[0])),
        repo=str(payload.get("repo", "crownthrive1/CrownThrive-Support")),
        head_sha=head_sha,
        target_state=str(payload.get("target_state", "CONTROLLED_TEST")),
        authority_level=authority_level,
        observations=observations,
        claims=claims,
        evidence_refs=list(ctx.evidence_refs),
        test_receipts=receipts,
        rollback=dict(rollback),
        fallback=dict(fallback),
        created_at=created_at,
    )
    return {
        "schema": "ct.penta.evi-builder.adapter-preview.v1",
        "effective_maturity": member.get("maturity"),
        "bundle": bundle,
        "independent_certification_performed": False,
        "production_promotion_performed": False,
        "state_persisted": False,
        "provider_write_performed": False,
        "authority_expanded": False,
    }


def immune_repair_plan_preview(ctx: Any) -> dict[str, Any]:
    runtime_path = ctx.root / "runtime/penta_immune.py"
    test_path = ctx.root / "tests/test_penta_immune.py"
    if not runtime_path.is_file() or not test_path.is_file():
        raise PromotedOperationError("PentaImmune runtime/test surface is incomplete")
    member = (ctx.snapshot.get("members") or {}).get("penta.immune") or {}
    if member.get("maturity") != "production":
        raise PromotedOperationError("PentaImmune effective maturity is not production")
    runtime = _load_fixed_module("penta_immune_adapter_preview", runtime_path)
    raw = ctx.payload.get("candidate") or {}
    if not isinstance(raw, Mapping):
        raise PromotedOperationError("repair_plan_preview candidate must be an object")
    metadata = raw.get("metadata") or {"repo": "crownthrive1/CrownThrive-Support"}
    rollback = raw.get("rollback") or {"method": "git_revert", "scope": "candidate commit"}
    fallback = raw.get("fallback") or {"method": "hold", "redundancy": "known-good-main"}
    if not all(isinstance(value, Mapping) for value in (metadata, rollback, fallback)):
        raise PromotedOperationError("candidate metadata, rollback, and fallback must be objects")
    _reject_credential_keys([metadata, rollback, fallback], path="candidate")

    def score(name: str, default: int) -> int:
        value = raw.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5:
            raise PromotedOperationError(f"candidate {name} must be an integer from 0 through 5")
        return value

    candidate = runtime.WeaknessCandidate(
        id=str(raw.get("id", "penta-exec-immune-preview")),
        kind=str(raw.get("kind", "known_governance_defect")),
        source_ref=str(raw.get("source_ref", ctx.evidence_refs[0])),
        authority_level=str(raw.get("authority_level", "D2")),
        handler=str(raw.get("handler", "patch_known_code")),
        severity=score("severity", 4),
        recurrence=score("recurrence", 3),
        confidence=score("confidence", 5),
        reversibility=score("reversibility", 5),
        testability=score("testability", 5),
        blast_radius=score("blast_radius", 1),
        rollback=dict(rollback),
        fallback=dict(fallback),
        metadata=dict(metadata),
    )
    policy_raw = ctx.payload.get("policy") or {}
    if not isinstance(policy_raw, Mapping):
        raise PromotedOperationError("repair_plan_preview policy must be an object")
    policy = runtime.AutonomyPolicy(
        max_repairs_per_cycle=int(policy_raw.get("max_repairs_per_cycle", 1)),
        max_attempts_per_candidate=int(policy_raw.get("max_attempts_per_candidate", 2)),
        cooldown_seconds=int(policy_raw.get("cooldown_seconds", 3600)),
        kill_switch_state=str(policy_raw.get("kill_switch_state", "armed")),
    )
    plan = runtime.build_repair_plan(candidate, policy)
    return {
        "schema": "ct.penta.immune.adapter-preview.v1",
        "effective_maturity": member.get("maturity"),
        "plan": plan,
        "repair_execution_performed": False,
        "independent_certification_performed": False,
        "production_promotion_performed": False,
        "state_persisted": False,
        "provider_write_performed": False,
        "authority_expanded": False,
    }
'''


EXEC_TEST_BLOCK = r'''

def test_evi_builder_and_immune_adapters_are_bounded() -> None:
    evi = invoke_member(
        ROOT,
        source_member="penta.status",
        target_member="penta.evi-builder",
        operation="evidence_bundle_preview",
        evidence_refs=["test:evi-builder-preview"],
        payload={"head_sha": "a" * 40, "created_at": "2026-08-27T00:00:00Z"},
        risk_class="D0",
    )
    preview = evi["details"]["result"]
    assert evi["disposition"] == "completed"
    assert preview["schema"] == "ct.penta.evi-builder.adapter-preview.v1"
    assert preview["bundle"]["certification_state"] == "UNVERIFIED"
    assert preview["bundle"]["production_promotion"] is False
    assert preview["independent_certification_performed"] is False
    assert preview["state_persisted"] is False and preview["provider_write_performed"] is False

    immune = invoke_member(
        ROOT,
        source_member="penta.status",
        target_member="penta.immune",
        operation="repair_plan_preview",
        evidence_refs=["test:immune-plan-preview"],
        payload={"candidate": {"id": "candidate-test", "authority_level": "D2"}},
        risk_class="D0",
    )
    plan = immune["details"]["result"]
    assert immune["disposition"] == "completed"
    assert plan["schema"] == "ct.penta.immune.adapter-preview.v1"
    assert plan["plan"]["status"] == "READY"
    assert plan["plan"]["production_promotion_authorized"] is False
    assert plan["repair_execution_performed"] is False
    assert plan["state_persisted"] is False and plan["provider_write_performed"] is False

'''


def update_promoted_operations() -> None:
    path = ROOT / "runtime/penta_promoted_operations.py"
    text = path.read_text(encoding="utf-8")
    if "def evi_builder_evidence_preview" not in text:
        marker = "\ndef mail_production_status(ctx: Any) -> dict[str, Any]:\n"
        if text.count(marker) != 1:
            raise GapClosureError("cannot locate promoted-operation insertion marker")
        text = text.replace(marker, PROMOTED_OPERATION_BLOCK + marker, 1)
    path.write_text(text, encoding="utf-8")


def update_executable_runtime() -> None:
    path = ROOT / "runtime/penta_exec.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace('RUNTIME_VERSION = "1.3.0"', f'RUNTIME_VERSION = "{RUNTIME_VERSION}"')
    text = text.replace(
        'if registry.get("version") != "1.3.0" or registry.get("fail_closed") is not True: raise PentaExecutionError("adapter registry must be v1.3.0 and fail closed")',
        'if registry.get("version") != "1.4.0" or registry.get("fail_closed") is not True: raise PentaExecutionError("adapter registry must be v1.4.0 and fail closed")',
    )
    if "def _evi_builder_evidence_preview" not in text:
        marker = 'def _certify_provider_static(ctx: AdapterContext): return _promoted("certify_provider_static",ctx)\n'
        if text.count(marker) != 1:
            raise GapClosureError("cannot locate executable wrapper insertion marker")
        text = text.replace(
            marker,
            marker
            + 'def _evi_builder_evidence_preview(ctx: AdapterContext): return _promoted("evi_builder_evidence_preview",ctx)\n'
            + 'def _immune_repair_plan_preview(ctx: AdapterContext): return _promoted("immune_repair_plan_preview",ctx)\n',
            1,
        )
    if '"evi_builder_evidence_preview":_evi_builder_evidence_preview' not in text:
        marker = '    "mail_production_status":_mail_production_status,"status_owner_snapshot":_status_owner_snapshot,"credentials_binding_census":_credentials_binding_census,"build_provider_adapter":_build_provider_adapter,"certify_provider_static":_certify_provider_static,\n'
        if text.count(marker) != 1:
            raise GapClosureError("cannot locate builtin-handler insertion marker")
        text = text.replace(
            marker,
            marker
            + '    "evi_builder_evidence_preview":_evi_builder_evidence_preview,"immune_repair_plan_preview":_immune_repair_plan_preview,\n',
            1,
        )
    path.write_text(text, encoding="utf-8")


def update_adapter_registry() -> None:
    path = ROOT / "data/penta/execution-adapters.registry.json"
    registry = load_json(path)
    registry["version"] = RUNTIME_VERSION
    adapters = registry.get("adapters")
    if not isinstance(adapters, list):
        raise GapClosureError("execution adapters must be a list")
    additions = [
        {
            "adapter_id": "builtin.evi-builder.evidence-preview",
            "member": "penta.evi-builder",
            "operation": "evidence_bundle_preview",
            "handler": "evi_builder_evidence_preview",
            "requested_effect": "prepare",
            "provider_effect": False,
            "requires_execution_eligible": True,
        },
        {
            "adapter_id": "builtin.immune.repair-plan-preview",
            "member": "penta.immune",
            "operation": "repair_plan_preview",
            "handler": "immune_repair_plan_preview",
            "requested_effect": "analyze",
            "provider_effect": False,
            "requires_execution_eligible": True,
        },
    ]
    by_id = {item.get("adapter_id"): item for item in adapters if isinstance(item, dict)}
    for addition in additions:
        existing = by_id.get(addition["adapter_id"])
        if existing is None:
            adapters.append(addition)
        else:
            existing.clear()
            existing.update(addition)
    write_json(path, registry)


def update_member_runtime_contract() -> None:
    path = ROOT / "data/penta/member-runtime.contract.json"
    contract = load_json(path)
    contract["schema_version"] = RUNTIME_VERSION
    invariants = contract.get("invariants")
    if not isinstance(invariants, dict):
        raise GapClosureError("member-runtime invariants must be an object")
    invariants.update(
        {
            "evi_builder_adapter_is_unverified_preview_only": True,
            "immune_adapter_is_plan_preview_only": True,
            "autonomous_repair_execution_disabled": True,
        }
    )
    adapters = contract.get("production_member_adapters")
    if not isinstance(adapters, list):
        raise GapClosureError("production_member_adapters must be a list")
    for item in (
        "penta.evi-builder:evidence_bundle_preview",
        "penta.immune:repair_plan_preview",
    ):
        if item not in adapters:
            adapters.append(item)
    contract["provider_execution_boundary"] = (
        "PentaMail provider sends remain on the separately governed PentaMail Live Certification and hourly reporting lanes. "
        "The local executable adapter reports evidence but does not send. PentaCredentials returns no secret values. "
        "PentaBuild produces temporary deterministic artifacts. PentaCertify disables network probes in its local adapter. "
        "PentaEVIBuilder constructs an UNVERIFIED exact-head evidence preview only, and PentaImmune constructs an allowlisted repair-plan preview only; neither adapter executes a repair, self-certifies, promotes production, persists state, expands authority, or performs a provider write."
    )
    write_json(path, contract)


def update_exec_tests() -> None:
    path = ROOT / "tests/test_penta_exec.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace('registry["version"] == "1.3.0"', 'registry["version"] == "1.4.0"')
    text = text.replace('len(registry["adapters"]) == 19', 'len(registry["adapters"]) == 21')
    text = text.replace('result["details"]["adapter_count"] == 19', 'result["details"]["adapter_count"] == 21')
    text = text.replace(
        '{"eligible_member_count": 19, "eligible_members_with_adapter": 19, "missing_adapter_members": [], "complete": True}',
        '{"eligible_member_count": 21, "eligible_members_with_adapter": 21, "missing_adapter_members": [], "complete": True}',
    )
    text = text.replace('probe["production_member_count"] == 19', 'probe["production_member_count"] == 21')
    text = text.replace('snapshot["production_member_count"] == 19', 'snapshot["production_member_count"] == 21')
    if "def test_evi_builder_and_immune_adapters_are_bounded" not in text:
        marker = "\ndef test_mail_send_still_requires_separate_provider_lane() -> None:\n"
        if text.count(marker) != 1:
            raise GapClosureError("cannot locate executable-test insertion marker")
        text = text.replace(marker, EXEC_TEST_BLOCK + marker, 1)
    path.write_text(text, encoding="utf-8")


def check_state() -> dict[str, Any]:
    family = load_json(ROOT / "data/penta/family.registry.json")
    catalogs = family.get("catalogs") or []
    immune_catalogs = [
        item
        for item in catalogs
        if isinstance(item, dict) and item.get("path") == "data/penta/systems.extensions.penta-immune.json"
    ]
    if len(immune_catalogs) != 1 or immune_catalogs[0].get("required") is not True:
        raise GapClosureError("canonical PentaImmune/EVIBuilder catalog is not registered exactly once")

    institutional = load_json(ROOT / "data/penta/institutional-services.registry.json")
    institutional_keys = {
        item.get("machine_key")
        for item in institutional.get("systems") or []
        if isinstance(item, dict)
    }
    duplicates = sorted({"penta.evi-builder", "penta.immune"} & institutional_keys)
    if duplicates:
        raise GapClosureError("duplicate institutional-service identities remain: " + ", ".join(duplicates))

    adapters = load_json(ROOT / "data/penta/execution-adapters.registry.json")
    rows = adapters.get("adapters") or []
    if adapters.get("version") != RUNTIME_VERSION or len(rows) != 21:
        raise GapClosureError("execution adapter registry is not at v1.4.0 with 21 adapters")
    members = [item.get("member") for item in rows if isinstance(item, dict)]
    for key in ("penta.evi-builder", "penta.immune"):
        if members.count(key) != 1:
            raise GapClosureError(f"{key} must have exactly one bounded adapter")
    if any(item.get("provider_effect") is not False for item in rows if isinstance(item, dict)):
        raise GapClosureError("a local executable adapter attempts provider effect")

    contract = load_json(ROOT / "data/penta/member-runtime.contract.json")
    if contract.get("schema_version") != RUNTIME_VERSION:
        raise GapClosureError("member-runtime contract version drift")
    required = {
        "penta.evi-builder:evidence_bundle_preview",
        "penta.immune:repair_plan_preview",
    }
    if not required.issubset(set(contract.get("production_member_adapters") or [])):
        raise GapClosureError("member-runtime contract lacks immune/evidence adapters")

    exec_runtime = (ROOT / "runtime/penta_exec.py").read_text(encoding="utf-8")
    promoted = (ROOT / "runtime/penta_promoted_operations.py").read_text(encoding="utf-8")
    tests = (ROOT / "tests/test_penta_exec.py").read_text(encoding="utf-8")
    for token, body in (
        ("evi_builder_evidence_preview", promoted),
        ("immune_repair_plan_preview", promoted),
        ("evi_builder_evidence_preview", exec_runtime),
        ("immune_repair_plan_preview", exec_runtime),
        ("test_evi_builder_and_immune_adapters_are_bounded", tests),
    ):
        if token not in body:
            raise GapClosureError(f"missing generated runtime/test token: {token}")

    disposition = load_json(
        ROOT / "developers/manifests/pentadocs-unlisted-page-dispositions.v1.json"
    )
    bucket = (disposition.get("dispositions") or {}).get("operational_reference_direct_link") or []
    if "automation/penta-families.mdx" not in bucket:
        raise GapClosureError("Penta Families documentation disposition is missing")

    convergence = load_json(
        ROOT / "developers/manifests/supabase-production-convergence-state.v1.json"
    )
    expected_count = len(list((ROOT / "supabase/migrations").glob("*.sql")))
    recorded_count = (convergence.get("migration_custody") or {}).get(
        "repository_migration_file_count"
    )
    if recorded_count != expected_count:
        raise GapClosureError(
            f"migration custody count drift: recorded={recorded_count} actual={expected_count}"
        )
    mesh = (ROOT / "virality-music/system-mesh.mdx").read_text(encoding="utf-8")
    if any(value in mesh for value in ("../SECURITY.md", "/SECURITY.md", "/SECURITY")):
        raise GapClosureError("noncanonical security documentation link remains")
    if "/technology/security-privacy-continuity" not in mesh:
        raise GapClosureError("governed security documentation route is missing")
    return {
        "ok": True,
        "runtime_version": RUNTIME_VERSION,
        "registered_member_count_target": 78,
        "execution_eligible_member_count_target": 21,
        "adapter_count": len(rows),
        "repository_migration_file_count": expected_count,
        "provider_effect_adapters": 0,
        "authority_expanded": False,
    }


def apply() -> dict[str, Any]:
    restore_canonical_institutional_services()
    update_family_registry()
    local_count = update_documentation_and_custody_state()
    update_promoted_operations()
    update_executable_runtime()
    update_adapter_registry()
    update_member_runtime_contract()
    update_exec_tests()
    state = check_state()
    state["repository_migration_file_count"] = local_count
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else check_state()
    except GapClosureError as exc:
        print(json.dumps({"ok": False, "disposition": "hold_fail_closed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
