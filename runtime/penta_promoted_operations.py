"""Bounded local operations for evidence-promoted Penta control-plane systems.

These adapters inspect evidence or build disposable local projections. They do
not perform provider writes, return secret values, persist state, certify their
own promotion, or change any provider's readiness/certification state.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Mapping

from runtime.penta_promotions import load_promotion_manifest


REPAIR_MANIFEST = Path("developers/manifests/pentaod-pentacertify-repair.v1.json")
PROVIDERS = Path("runtime/penta-provider-control-plane/providers.json")
PROVIDER_RUNTIME = Path("runtime/penta-provider-control-plane/penta_control_plane.py")


class PromotedOperationError(ValueError):
    """Raised when a promoted operation cannot remain within its local boundary."""


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromotedOperationError(f"cannot load governed JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PromotedOperationError(f"expected JSON object: {path}")
    return value


def _exact_payload(ctx: Any, allowed: set[str]) -> Mapping[str, Any]:
    payload = ctx.payload
    if not isinstance(payload, Mapping) or set(payload) - allowed:
        raise PromotedOperationError(
            f"operation payload permits only these fields: {sorted(allowed)}"
        )
    return payload


def _provider_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("provider_id", "resend")
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value):
        raise PromotedOperationError("provider_id must be a bounded registry identifier")
    return value


def _provider_module(root: Path):
    path = root / PROVIDER_RUNTIME
    spec = importlib.util.spec_from_file_location("penta_promoted_provider_control", path)
    if spec is None or spec.loader is None:
        raise PromotedOperationError(f"cannot load fixed provider runtime: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _promotion(root: Path, machine_key: str) -> dict[str, Any]:
    manifest = load_promotion_manifest(root, required=True)
    assert manifest is not None
    for item in manifest["promotions"]:
        if item["machine_key"] == machine_key:
            return item
    raise PromotedOperationError(f"missing evidence-bound promotion for {machine_key}")


def _repair(root: Path) -> dict[str, Any]:
    manifest = _json(root / REPAIR_MANIFEST)
    if manifest.get("state") != "PRODUCTION_REPAIRS_APPLIED_AND_RETESTED":
        raise PromotedOperationError("production repair evidence is not in retested state")
    if not isinstance(manifest.get("verified_state"), dict):
        raise PromotedOperationError("production repair evidence has no verified_state")
    return manifest


def mail_production_status(ctx: Any) -> dict[str, Any]:
    _exact_payload(ctx, set())
    repair = _repair(ctx.root)
    hourly = repair["verified_state"]["hourly_reporting"]
    promotion = _promotion(ctx.root, "penta.mail")
    workflow = ctx.root / ".github/workflows/penta-mail-live-certification.yml"
    runtime = ctx.root / "runtime/penta_mail.py"
    evidence_bound = (
        bool(hourly.get("provider_send_http_200_verified"))
        and bool(hourly.get("founder_inbox_readback_verified"))
        and workflow.is_file()
        and runtime.is_file()
    )
    return {
        "schema": "ct.penta.mail.production-status.v1",
        "system_maturity_evidence_state": "PASS" if evidence_bound else "HOLD",
        "current_provider_state": "NOT_EVALUATED_BY_LOCAL_ADAPTER",
        "provider_send_http_200_evidence_present": bool(hourly.get("provider_send_http_200_verified")),
        "founder_inbox_readback_evidence_present": bool(hourly.get("founder_inbox_readback_verified")),
        "mail_outbox_receipts": hourly.get("mail_outbox_receipts"),
        "runtime_present": runtime.is_file(),
        "live_certification_workflow_present": workflow.is_file(),
        "promotion_authority_ref": promotion["authority_ref"],
        "provider_state_disposition": promotion["provider_state_disposition"],
        "provider_write_performed": False,
        "provider_state_changed": False,
        "production_promotion_authorized": False,
    }


def status_owner_snapshot(ctx: Any) -> dict[str, Any]:
    _exact_payload(ctx, set())
    repair = _repair(ctx.root)
    _promotion(ctx.root, "penta.status")
    adapter_registry = _json(ctx.root / "data/penta/execution-adapters.registry.json")
    members = ctx.snapshot.get("members") or {}
    production = sorted(
        key for key, value in members.items() if value.get("maturity") == "production"
    )
    adapter_members = {
        item.get("member")
        for item in adapter_registry.get("adapters") or []
        if isinstance(item, dict)
    }
    missing = sorted(set(production) - adapter_members)
    verified = repair["verified_state"]
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
        "penta_self_evidence": verified["penta_self"],
        "hourly_reporting_evidence": verified["hourly_reporting"],
        "provider_evidence_queue": verified["provider_evidence_queue"],
        "provider_states_changed": False,
        "provider_write_performed": False,
        "production_promotion_authorized": False,
    }


def credentials_binding_census(ctx: Any) -> dict[str, Any]:
    _exact_payload(ctx, set())
    _promotion(ctx.root, "penta.credentials")
    module = _provider_module(ctx.root)
    registry = module.Registry(ctx.root / PROVIDERS)
    with tempfile.TemporaryDirectory() as temp:
        bindings = module.PentaCredentials(registry, Path(temp)).bind_all()
        rows = [
            {
                "provider_id": row.provider_id,
                "bound": row.bound,
                "matched_environment_names": list(row.matched_set),
                "reason": row.reason,
            }
            for row in bindings
        ]
    return {
        "schema": "ct.penta.credentials.binding-census.v1",
        "provider_count": len(rows),
        "bound_count": sum(1 for row in rows if row["bound"]),
        "unbound_count": sum(1 for row in rows if not row["bound"]),
        "providers": rows,
        "secret_values_returned": False,
        "state_persisted": False,
        "provider_states_changed": False,
        "provider_write_performed": False,
        "production_promotion_authorized": False,
    }


def build_provider_adapter(ctx: Any) -> dict[str, Any]:
    payload = _exact_payload(ctx, {"provider_id"})
    _promotion(ctx.root, "penta.build")
    provider_id = _provider_id(payload)
    module = _provider_module(ctx.root)
    registry = module.Registry(ctx.root / PROVIDERS)
    with tempfile.TemporaryDirectory() as temp:
        state = Path(temp)
        receipt = module.PentaBuild(registry, state).build(provider_id)
        artifact = state / receipt.artifact_path
        result = dataclasses.asdict(receipt)
        result["artifact_exists_in_disposable_state"] = artifact.is_file()
    return {
        "schema": "ct.penta.build.adapter-probe.v1",
        "provider_id": provider_id,
        "build": result,
        "state_persisted": False,
        "provider_states_changed": False,
        "provider_write_performed": False,
        "production_promotion_authorized": False,
    }


def certify_provider_static(ctx: Any) -> dict[str, Any]:
    payload = _exact_payload(ctx, {"provider_id"})
    promotion = _promotion(ctx.root, "penta.certify")
    provider_id = _provider_id(payload)
    module = _provider_module(ctx.root)
    registry = module.Registry(ctx.root / PROVIDERS)
    previous = os.environ.get("PENTA_DISABLE_NETWORK_PROBES")
    os.environ["PENTA_DISABLE_NETWORK_PROBES"] = "1"
    try:
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            binding = module.PentaCredentials(registry, state).bind(provider_id)
            build = module.PentaBuild(registry, state).build(provider_id)
            certification = module.PentaCertify(registry, state).certify(provider_id)
            result = {
                "credential_bound": binding.bound,
                "build": dataclasses.asdict(build),
                "certification": dataclasses.asdict(certification),
            }
    finally:
        if previous is None:
            os.environ.pop("PENTA_DISABLE_NETWORK_PROBES", None)
        else:
            os.environ["PENTA_DISABLE_NETWORK_PROBES"] = previous
    repair = _repair(ctx.root)["verified_state"]["penta_certify"]
    return {
        "schema": "ct.penta.certify.static-probe.v1",
        "provider_id": provider_id,
        "runtime_probe": result,
        "historical_system_evidence": repair,
        "promotion_authority_ref": promotion["authority_ref"],
        "network_probe_performed": False,
        "state_persisted": False,
        "provider_states_changed": False,
        "provider_write_performed": False,
        "self_certification_performed": False,
        "production_promotion_authorized": False,
    }
