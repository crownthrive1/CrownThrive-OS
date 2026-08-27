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
