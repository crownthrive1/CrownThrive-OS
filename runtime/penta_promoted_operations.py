"""Bounded runtime operations for evidence-promoted and evidence-backed Penta systems.

These operations make production control-plane members callable without exposing
secret material or manufacturing provider authority. Provider network probes and
provider writes are disabled here; already-executed production evidence remains
separate and explicitly referenced by source manifests and institutional records.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

REPAIR_MANIFEST = Path("developers/manifests/pentaod-pentacertify-repair.v1.json")
PROMOTIONS = Path("data/penta/production-promotions.v1.json")
PROVIDERS = Path("runtime/penta-provider-control-plane/providers.json")
PROVIDER_RUNTIME = Path("runtime/penta-provider-control-plane/penta_control_plane.py")
CONTEXT_RUNTIME = Path("runtime/penta_context.py")
CONTEXT_DOC = Path("PENTACONTEXT.md")
CONTEXT_TEST = Path("tests/test_penta_context.py")
CONTEXT_CI = Path(".github/workflows/penta-context-ci.yml")
CONTEXT_EDGE = Path("supabase/functions/penta-context/index.ts")
CONTEXT_BASE_RECEIPT = "1e47ec8fd0a190a663c0c6b1cf17490d87c798e3281022dc2d2553e2f090a01e"
CONTEXT_AUTOMATION_RECEIPT = "b05577014efc06fa2f07f7ea9c175e14b5d43f2b45b3c61cd464a2cad2579dd5"
CONTEXT_EDGE_SHA256 = "4b8902e1d639e9a80d3e9f028cac2bb26662658ff5a547af210514f76fc3d212"


class PromotedOperationError(ValueError):
    pass


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PromotedOperationError(f"expected JSON object: {path}")
    return value


def _load_fixed_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PromotedOperationError(f"cannot load runtime: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _provider_module(root: Path):
    return _load_fixed_module("penta_promoted_provider_control", root / PROVIDER_RUNTIME)


def _promotion(root: Path, machine_key: str) -> dict[str, Any]:
    manifest = _json(root / PROMOTIONS)
    for item in manifest.get("promotions") or []:
        if isinstance(item, dict) and item.get("machine_key") == machine_key:
            return item
    raise PromotedOperationError(f"missing production promotion for {machine_key}")


def _repair(root: Path) -> dict[str, Any]:
    manifest = _json(root / REPAIR_MANIFEST)
    if manifest.get("state") != "PRODUCTION_REPAIRS_APPLIED_AND_RETESTED":
        raise PromotedOperationError("production repair evidence is not in retested state")
    return manifest


def context_contract_probe(ctx: Any) -> dict[str, Any]:
    required = [CONTEXT_RUNTIME, CONTEXT_DOC, CONTEXT_TEST, CONTEXT_CI, CONTEXT_EDGE]
    missing = [path.as_posix() for path in required if not (ctx.root / path).is_file()]
    if missing:
        raise PromotedOperationError("PentaContext contract surface missing: " + ", ".join(missing))
    runtime = _load_fixed_module("penta_context_contract_probe", ctx.root / CONTEXT_RUNTIME)
    if getattr(runtime, "SYSTEM_KEY", None) != "penta.context" or getattr(runtime, "VERSION", None) != "1.1.0":
        raise PromotedOperationError("PentaContext runtime identity/version mismatch")
    member = (ctx.snapshot.get("members") or {}).get("penta.context") or {}
    if member.get("maturity") != "production":
        raise PromotedOperationError("PentaContext effective maturity is not production")
    return {
        "schema": "ct.penta.context.contract-probe.v1",
        "system_key": runtime.SYSTEM_KEY,
        "version": runtime.VERSION,
        "effective_maturity": member.get("maturity"),
        "runtime_present": True,
        "contract_tests_present": True,
        "ci_present": True,
        "edge_runtime_present": True,
        "documentation_evidence_present": True,
        "production_evidence": {
            "v1_base_receipt_sha256": CONTEXT_BASE_RECEIPT,
            "v1_1_automation_receipt_sha256": CONTEXT_AUTOMATION_RECEIPT,
            "edge_v2_artifact_sha256": CONTEXT_EDGE_SHA256,
        },
        "provider_call_performed": False,
        "credential_material_accessed": False,
        "authority_expanded": False,
    }



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

def mail_production_status(ctx: Any) -> dict[str, Any]:
    repair = _repair(ctx.root)
    hourly = repair["verified_state"]["hourly_reporting"]
    promotion = _promotion(ctx.root, "penta.mail")
    workflow = ctx.root / ".github/workflows/penta-mail-live-certification.yml"
    runtime = ctx.root / "runtime/penta_mail.py"
    verified = bool(hourly.get("provider_send_http_200_verified")) and bool(hourly.get("founder_inbox_readback_verified"))
    return {
        "schema": "ct.penta.mail.production-status.v1",
        "state": "PRODUCTION_VERIFIED" if verified and workflow.exists() and runtime.exists() else "HOLD",
        "provider_send_http_200_verified": bool(hourly.get("provider_send_http_200_verified")),
        "founder_inbox_readback_verified": bool(hourly.get("founder_inbox_readback_verified")),
        "mail_outbox_receipts": hourly.get("mail_outbox_receipts"),
        "runtime_present": runtime.exists(),
        "live_certification_workflow_present": workflow.exists(),
        "promotion_authority_ref": promotion["authority_ref"],
        "provider_write_performed_by_this_adapter": False,
    }


def status_owner_snapshot(ctx: Any) -> dict[str, Any]:
    if getattr(ctx, "target_member", None) == "penta.context":
        return context_contract_probe(ctx)
    repair = _repair(ctx.root)
    adapter_registry = _json(ctx.root / "data/penta/execution-adapters.registry.json")
    members = ctx.snapshot.get("members") or {}
    production = sorted(key for key, value in members.items() if value.get("maturity") == "production")
    adapter_members = {item.get("member") for item in adapter_registry.get("adapters") or [] if isinstance(item, dict)}
    missing = sorted(set(production) - adapter_members)
    return {
        "schema": "ct.penta.status.owner-snapshot.v1",
        "family_status": ctx.snapshot.get("family_status"),
        "member_count": ctx.snapshot.get("member_count"),
        "maturity_counts": ctx.snapshot.get("maturity_counts"),
        "production_member_count": len(production),
        "production_adapter_coverage_complete": not missing,
        "production_members_missing_adapter": missing,
        "promotion_count": ctx.snapshot.get("promotion_count", 0),
        "promoted_members": ctx.snapshot.get("promoted_members", []),
        "penta_self_evidence": repair["verified_state"]["penta_self"],
        "hourly_reporting": repair["verified_state"]["hourly_reporting"],
        "provider_write_performed": False,
    }


def credentials_binding_census(ctx: Any) -> dict[str, Any]:
    mod = _provider_module(ctx.root)
    registry = mod.Registry(ctx.root / PROVIDERS)
    with tempfile.TemporaryDirectory() as temp:
        bindings = mod.PentaCredentials(registry, Path(temp)).bind_all()
        rows = [{"provider_id": row.provider_id, "bound": row.bound, "matched_set_names": list(row.matched_set), "reason": row.reason} for row in bindings]
    return {
        "schema": "ct.penta.credentials.binding-census.v1",
        "provider_count": len(rows),
        "bound_count": sum(1 for row in rows if row["bound"]),
        "unbound_count": sum(1 for row in rows if not row["bound"]),
        "providers": rows,
        "secret_values_returned": False,
        "state_persisted": False,
    }


def build_provider_adapter(ctx: Any) -> dict[str, Any]:
    provider_id = ctx.payload.get("provider_id", "resend")
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise PromotedOperationError("provider_id must be a non-empty string")
    mod = _provider_module(ctx.root)
    registry = mod.Registry(ctx.root / PROVIDERS)
    with tempfile.TemporaryDirectory() as temp:
        state = Path(temp)
        receipt = mod.PentaBuild(registry, state).build(provider_id)
        artifact = state / receipt.artifact_path
        result = dataclasses.asdict(receipt)
        result["artifact_exists"] = artifact.exists()
        result["state_persisted"] = False
        result["provider_write_performed"] = False
    return {"schema": "ct.penta.build.adapter-probe.v1", "provider_id": provider_id, "build": result}


def certify_provider_static(ctx: Any) -> dict[str, Any]:
    provider_id = ctx.payload.get("provider_id", "resend")
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise PromotedOperationError("provider_id must be a non-empty string")
    mod = _provider_module(ctx.root)
    registry = mod.Registry(ctx.root / PROVIDERS)
    old = os.environ.get("PENTA_DISABLE_NETWORK_PROBES")
    os.environ["PENTA_DISABLE_NETWORK_PROBES"] = "1"
    try:
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            binding = mod.PentaCredentials(registry, state).bind(provider_id)
            build = mod.PentaBuild(registry, state).build(provider_id)
            cert = mod.PentaCertify(registry, state).certify(provider_id)
            result = {
                "credential_bound": binding.bound,
                "build": dataclasses.asdict(build),
                "certification": dataclasses.asdict(cert),
                "network_probe_performed": False,
                "provider_write_performed": False,
                "state_persisted": False,
            }
    finally:
        if old is None:
            os.environ.pop("PENTA_DISABLE_NETWORK_PROBES", None)
        else:
            os.environ["PENTA_DISABLE_NETWORK_PROBES"] = old
    repair = _repair(ctx.root)["verified_state"]["penta_certify"]
    return {"schema": "ct.penta.certify.static-probe.v1", "provider_id": provider_id, "runtime_probe": result, "production_evidence_projection": repair}
