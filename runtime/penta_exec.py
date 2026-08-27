#!/usr/bin/env python3
"""Executable control plane for the CrownThrive Penta Family.

Every registered Penta is addressable for status and governed handoffs. Actual
member invocation requires a statically registered bounded adapter and passes
the existing family/interoperability gates. This runtime does not execute
arbitrary shell code, import user-selected handlers, accept credential material,
manufacture authority, move money, or perform provider writes.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable, Iterable, Mapping, Optional
from uuid import uuid4

try:
    from runtime.penta_family import load_family, member_dispatch_gate
    from runtime.penta_interop import build_envelope, evaluate_handoff
except ModuleNotFoundError:
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from runtime.penta_family import load_family, member_dispatch_gate
    from runtime.penta_interop import build_envelope, evaluate_handoff

RUNTIME_VERSION = "1.5.0"
ADAPTER_REGISTRY = Path("data/penta/execution-adapters.registry.json")
EXECUTION_ELIGIBLE = {"certified", "production"}
VALID_EFFECTS = {"analyze", "prepare", "route", "execute", "verify", "preserve"}


class PentaExecutionError(ValueError):
    pass


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _seal(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _receipt(kind: str, disposition: str, details: Mapping[str, Any]) -> dict[str, Any]:
    value: dict[str, Any] = {"schema": "ct.penta.execution-receipt.v1", "runtime_version": RUNTIME_VERSION, "receipt_id": f"pex-{uuid4().hex}", "kind": kind, "disposition": disposition, "created_at": _utcnow(), "details": dict(details)}
    value["receipt_sha256"] = _seal(value)
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PentaExecutionError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaExecutionError(f"JSON root must be object: {path}")
    return value


def _load_fixed_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PentaExecutionError(f"cannot load fixed runtime: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _members(snapshot: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    value = snapshot.get("members")
    if not isinstance(value, Mapping):
        raise PentaExecutionError("family snapshot has no members map")
    return value  # type: ignore[return-value]


def _member(snapshot: Mapping[str, Any], machine_key: str) -> Mapping[str, Any]:
    value = _members(snapshot).get(machine_key)
    if not isinstance(value, Mapping):
        raise PentaExecutionError(f"unknown or unregistered Penta member: {machine_key}")
    return value


def family_list(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for key, member in sorted(_members(snapshot).items()):
        gate = member_dispatch_gate(snapshot, key)
        rows.append({"machine_key": key, "canonical_name": member.get("canonical_name"), "category": member.get("category"), "maturity": member.get("maturity"), "execution_eligible": bool(gate.get("eligible")), "portal_route": member.get("portal_route")})
    return _receipt("family_list", "completed_read_only", {"member_count": len(rows), "members": rows})


def member_status(snapshot: Mapping[str, Any], machine_key: str) -> dict[str, Any]:
    member, all_members = _member(snapshot, machine_key), _members(snapshot)
    deps = [{"machine_key": dep, "registered": dep in all_members, "maturity": all_members.get(dep, {}).get("maturity") if dep in all_members else None} for dep in member.get("dependencies") or []]
    missing = sorted(item["machine_key"] for item in deps if not item["registered"])
    return _receipt("member_status", "healthy_control_plane" if not missing else "degraded_control_plane", {"machine_key": machine_key, "canonical_name": member.get("canonical_name"), "category": member.get("category"), "purpose": member.get("purpose"), "authority_boundary": member.get("authority_boundary"), "risk_ceiling": member.get("risk_ceiling"), "catalog_maturity": member.get("catalog_maturity", member.get("maturity")), "maturity": member.get("maturity"), "maturity_promotion": member.get("maturity_promotion"), "portal_route": member.get("portal_route"), "execution_gate": member_dispatch_gate(snapshot, machine_key), "dependencies": deps, "missing_dependencies": missing, "source": member.get("source")})


def validate_adapter_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("registry_id") != "crownthrive.penta.execution-adapters":
        raise PentaExecutionError("unexpected adapter registry_id")
    if registry.get("version") != "1.5.0" or registry.get("fail_closed") is not True:
        raise PentaExecutionError("adapter registry must be v1.5.0 and fail closed")
    adapters = registry.get("adapters")
    if not isinstance(adapters, list):
        raise PentaExecutionError("adapters must be a list")
    seen_ids: set[str] = set(); seen_routes: set[tuple[str, str]] = set()
    for adapter in adapters:
        if not isinstance(adapter, Mapping): raise PentaExecutionError("adapter entry must be object")
        required = {"adapter_id", "member", "operation", "handler", "requested_effect", "provider_effect", "requires_execution_eligible"}
        missing = required - set(adapter)
        if missing: raise PentaExecutionError(f"adapter missing fields: {sorted(missing)}")
        adapter_id, member, operation = adapter["adapter_id"], adapter["member"], adapter["operation"]
        if not isinstance(adapter_id, str) or not adapter_id: raise PentaExecutionError("adapter_id must be non-empty string")
        if adapter_id in seen_ids: raise PentaExecutionError(f"duplicate adapter_id: {adapter_id}")
        seen_ids.add(adapter_id)
        if not isinstance(member, str) or not member.startswith("penta."): raise PentaExecutionError("adapter member must be exact penta.* key")
        if not isinstance(operation, str) or not operation: raise PentaExecutionError("adapter operation must be non-empty string")
        route = (member, operation)
        if route in seen_routes: raise PentaExecutionError(f"duplicate member/operation adapter: {route}")
        seen_routes.add(route)
        if adapter["requested_effect"] not in VALID_EFFECTS: raise PentaExecutionError("invalid requested_effect")
        if adapter["handler"] not in BUILTIN_HANDLERS: raise PentaExecutionError(f"unregistered builtin handler: {adapter['handler']!r}")
        if not isinstance(adapter["provider_effect"], bool) or not isinstance(adapter["requires_execution_eligible"], bool): raise PentaExecutionError("adapter booleans are invalid")
        if adapter["provider_effect"]: raise PentaExecutionError("builtin adapter registry does not permit provider-effect handlers")
        if adapter["requested_effect"] == "execute" and adapter["requires_execution_eligible"] is not True: raise PentaExecutionError("execute adapters must require execution-eligible maturity")


def load_adapter_registry(root: Path) -> dict[str, Any]:
    registry = _load_json(root / ADAPTER_REGISTRY); validate_adapter_registry(registry); return registry


def _find_adapter(registry: Mapping[str, Any], member: str, operation: str) -> Optional[Mapping[str, Any]]:
    return next((adapter for adapter in registry.get("adapters") or [] if adapter.get("member") == member and adapter.get("operation") == operation), None)


def _member_adapter_operations(registry: Mapping[str, Any], machine_key: str) -> list[str]:
    return sorted(str(a["operation"]) for a in registry.get("adapters") or [] if a.get("member") == machine_key)


@dataclass(frozen=True)
class AdapterContext:
    root: Path
    registry: Mapping[str, Any]
    snapshot: Mapping[str, Any]
    source_member: str
    target_member: str
    operation: str
    payload: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    envelope: Mapping[str, Any]
    handoff_decision: Mapping[str, Any]


def _family_snapshot(ctx: AdapterContext) -> dict[str, Any]:
    return {"family_status": ctx.snapshot.get("family_status"), "production_scope": ctx.snapshot.get("production_scope"), "member_count": ctx.snapshot.get("member_count"), "maturity_counts": ctx.snapshot.get("maturity_counts"), "execution_eligible_members": ctx.snapshot.get("execution_eligible_members"), "held_members": ctx.snapshot.get("held_members")}


def _beata_heartbeat(ctx: AdapterContext) -> dict[str, Any]:
    details = member_status(ctx.snapshot, "penta.beata")["details"]
    return {"state": "alive" if not details["missing_dependencies"] else "degraded", "machine_key": "penta.beata", "maturity": details["maturity"], "missing_dependencies": details["missing_dependencies"], "observed_at": _utcnow()}


def _mesh_route_check(ctx: AdapterContext) -> dict[str, Any]:
    candidate = ctx.payload.get("candidate_target")
    if not isinstance(candidate, str) or not candidate.startswith("penta."): raise PentaExecutionError("route_check payload.candidate_target must be exact penta.* machine key")
    member, gate = _member(ctx.snapshot, candidate), member_dispatch_gate(ctx.snapshot, candidate)
    return {"candidate_target": candidate, "registered": True, "catalog_maturity": member.get("catalog_maturity", member.get("maturity")), "maturity": member.get("maturity"), "maturity_promotion": member.get("maturity_promotion"), "execution_eligible": bool(gate.get("eligible")), "portal_route": member.get("portal_route"), "dependency_count": len(member.get("dependencies") or [])}


def _error_normalize(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_observability import normalize_error
    message, code, context = ctx.payload.get("message", "bounded PentaError normalization probe"), ctx.payload.get("code", "PENTA_EXEC_ADAPTER_ERROR"), ctx.payload.get("context") or {}
    if not isinstance(message, str) or not message.strip() or not isinstance(code, str) or not code.strip(): raise PentaExecutionError("error_normalize message/code must be non-empty strings")
    if not isinstance(context, Mapping): raise PentaExecutionError("error_normalize context must be an object")
    return normalize_error(RuntimeError(message), code=code, context=context).envelope(include_internal=False)


def _logger_emit(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_observability import PentaLogger, Severity
    service, message, event, severity, context = ctx.payload.get("service", "penta-exec"), ctx.payload.get("message", "bounded executable-family log probe"), ctx.payload.get("event", "penta.exec.probe"), ctx.payload.get("severity", "info"), ctx.payload.get("context") or {}
    if not all(isinstance(v, str) and v.strip() for v in (service, message, event)) or not isinstance(context, Mapping): raise PentaExecutionError("logger_emit payload is invalid")
    lines: list[str] = []
    record = PentaLogger(service=service, penta_member="penta.logger", minimum_severity=Severity.DEBUG, sink=lines.append).emit(severity, message, event=event, context=context)
    if record is None or not lines: raise PentaExecutionError("logger_emit produced no record")
    return {"record": record, "line_sha256": sha256(lines[-1].encode("utf-8")).hexdigest()}


def _trace_new_context(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_observability import TraceContext
    parent = ctx.payload.get("parent_span_id")
    if parent is not None and (not isinstance(parent, str) or not parent.strip()): raise PentaExecutionError("trace_new_context parent_span_id must be null or non-empty")
    return TraceContext(parent_span_id=parent).as_dict()


def _metric_snapshot(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_observability import MetricRegistry
    counters, gauges, observations = ctx.payload.get("counters") or {}, ctx.payload.get("gauges") or {}, ctx.payload.get("observations") or {}
    if not all(isinstance(v, Mapping) for v in (counters, gauges, observations)): raise PentaExecutionError("metric_snapshot groups must be objects")
    if len(counters) + len(gauges) + len(observations) > 100: raise PentaExecutionError("metric_snapshot accepts at most 100 metric names")
    metrics, observation_count = MetricRegistry(), 0
    for name, value in counters.items():
        if not isinstance(value, (int, float)): raise PentaExecutionError("counter values must be numeric")
        metrics.increment(str(name), float(value))
    for name, value in gauges.items():
        if not isinstance(value, (int, float)): raise PentaExecutionError("gauge values must be numeric")
        metrics.gauge(str(name), float(value))
    for name, values in observations.items():
        if not isinstance(values, list): raise PentaExecutionError("observation values must be arrays")
        observation_count += len(values)
        if observation_count > 1000: raise PentaExecutionError("metric_snapshot accepts at most 1000 observations")
        for value in values:
            if not isinstance(value, (int, float)): raise PentaExecutionError("observation values must be numeric")
            metrics.observe(str(name), float(value))
    return metrics.snapshot()


def _heartbeat_control_plane_probe(ctx: AdapterContext) -> dict[str, Any]:
    adapter_registry = load_adapter_registry(ctx.root)
    production = sorted(key for key, member in _members(ctx.snapshot).items() if member.get("maturity") == "production")
    rows = []
    for key in production:
        status = member_status(ctx.snapshot, key)["details"]
        operations = _member_adapter_operations(adapter_registry, key)
        rows.append({"machine_key": key, "maturity": status["maturity"], "registered": True, "dependency_gaps": status["missing_dependencies"], "adapter_operations": operations, "adapter_bound": bool(operations)})
    return {"schema": "ct.penta.heartbeat.control-plane-probe.v1", "observed_at": _utcnow(), "production_member_count": len(rows), "healthy": all(row["adapter_bound"] and not row["dependency_gaps"] for row in rows), "members": rows}


def _od_readiness_assess(ctx: AdapterContext) -> dict[str, Any]:
    candidate = ctx.payload.get("candidate_target")
    if not isinstance(candidate, str) or not candidate.startswith("penta."): raise PentaExecutionError("readiness_assess requires payload.candidate_target")
    adapter_registry = load_adapter_registry(ctx.root)
    member, status, gate = _member(ctx.snapshot, candidate), member_status(ctx.snapshot, candidate)["details"], member_dispatch_gate(ctx.snapshot, candidate)
    operations = _member_adapter_operations(adapter_registry, candidate)
    ready = bool(gate.get("eligible")) and bool(operations) and not status["missing_dependencies"]
    return {"schema": "ct.penta.od.readiness.v1", "candidate_target": candidate, "maturity": member.get("maturity"), "execution_eligible": bool(gate.get("eligible")), "adapter_operations": operations, "dependency_gaps": status["missing_dependencies"], "ready_for_bounded_dispatch": ready, "authority_expanded": False, "observed_at": _utcnow()}


def _compliance_evaluate(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_compliance_license import evaluate_compliance
    obligations, jurisdictions, scopes, evidence_index, as_of = ctx.payload.get("obligations"), ctx.payload.get("jurisdictions"), ctx.payload.get("scopes"), ctx.payload.get("evidence_index"), ctx.payload.get("as_of")
    if not isinstance(obligations, list) or not isinstance(jurisdictions, list) or not isinstance(scopes, list) or not isinstance(evidence_index, Mapping): raise PentaExecutionError("compliance evaluate requires obligations/jurisdictions/scopes/evidence_index")
    try: as_of_date = date.fromisoformat(str(as_of))
    except ValueError as exc: raise PentaExecutionError("compliance as_of must be ISO date") from exc
    return evaluate_compliance(obligations, jurisdictions=jurisdictions, scopes=scopes, evidence_index=evidence_index, as_of=as_of_date)


def _license_readiness(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_compliance_license import evaluate_license_request
    asset, request = ctx.payload.get("asset"), ctx.payload.get("request")
    if not isinstance(asset, Mapping) or not isinstance(request, Mapping): raise PentaExecutionError("license readiness requires asset and request objects")
    decision = evaluate_license_request(asset, request)
    return {"decision": decision, "adapter_boundary": "readiness_only_no_license_grant_issued", "binding_action_performed": False}


def _scribe_reconcile_preview(ctx: AdapterContext) -> dict[str, Any]:
    runtime = _load_fixed_module("penta_exec_scribe_runtime", ctx.root / "penta/scribe/runtime.py")
    scan_text = ctx.payload.get("scan_text", "PentaScribe production adapter health probe.")
    if not isinstance(scan_text, str) or len(scan_text) > 100000: raise PentaExecutionError("scribe scan_text must be a string <= 100000 chars")
    authority_ref = ctx.payload.get("authority_ref") or f"penta-exec:{ctx.evidence_refs[0]}"
    if not isinstance(authority_ref, str) or not authority_ref.strip(): raise PentaExecutionError("scribe authority_ref must be non-empty")
    with tempfile.TemporaryDirectory() as tmp:
        state, source = Path(tmp) / "state", Path(tmp) / "source.md"
        source.write_text(scan_text, encoding="utf-8")
        result = runtime.cycle(ctx.root / "penta/scribe/registry.json", state, [source], authority_ref)
        return {"summary": result["summary"], "receipt": result["receipt"], "state_persisted": False, "provider_write": False}


def _marketer_cycle_preview(ctx: AdapterContext) -> dict[str, Any]:
    runtime = _load_fixed_module("penta_exec_marketer_runtime", ctx.root / "penta/marketer/runtime.py")
    campaign = ctx.payload.get("campaign")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        if campaign is None: campaign_path = ctx.root / "penta/marketer/campaign.example.json"
        else:
            if not isinstance(campaign, Mapping): raise PentaExecutionError("marketer campaign must be an object")
            campaign_path = tmp_root / "campaign.json"; campaign_path.write_text(json.dumps(dict(campaign), sort_keys=True), encoding="utf-8")
        result = runtime.cycle(campaign_path, tmp_root / "state", ctx.root / "penta/marketer/adapters.registry.json", ctx.root / "penta/scribe/registry.json", ctx.root / "penta/marketer/policy.json")
        return {"summary": result["summary"], "receipt": result["receipt"], "state_persisted": False, "provider_write": False}


def _reject_secret_fields(value: Any, path: str = "payload") -> None:
    forbidden = ("token", "secret", "password", "credential", "authorization", "api_key", "private_key")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise PentaExecutionError(f"JSON object keys must be strings: {path}")
            normalized = str(key).casefold().replace("-", "_").replace(" ", "_")
            if any(fragment in normalized for fragment in forbidden):
                raise PentaExecutionError(f"credential material is not accepted: {path}.{key}")
            _reject_secret_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_fields(child, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise PentaExecutionError(f"non-finite JSON numbers are not accepted: {path}")
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise PentaExecutionError(f"non-JSON value is not accepted: {path}")
    elif isinstance(value, str) and re.search(
        r"(?i)(?:\bbearer\s+\S{8,}|\b(?:sk-|ghp_|github_pat_|sb_secret_)[A-Za-z0-9_-]{8,})",
        value,
    ):
        raise PentaExecutionError(f"credential-like string is not accepted: {path}")


def _bounded_text(value: Any, field: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
        raise PentaExecutionError(f"{field} must be a non-empty trimmed string <= {maximum} characters")
    if any(ord(character) < 32 for character in value):
        raise PentaExecutionError(f"{field} contains control characters")
    return value


def _repo_local_ref(value: Any, field: str) -> str:
    ref = _bounded_text(value, field, maximum=256)
    prefixes = ("workflow-run:", "github-actions:", "ci:", "issue:", "test:", "evidence:", "docs:", "registry:", "automation:", "repo:", "git:")
    if not ref.startswith(prefixes) or "://" in ref or ".." in ref:
        raise PentaExecutionError(f"{field} must be a bounded repository-local reference")
    return ref


def _recovery_contracts(rollback: Any, fallback: Any, *, head_sha: str | None = None) -> tuple[dict[str, str], dict[str, str]]:
    if not isinstance(rollback, Mapping) or not isinstance(fallback, Mapping):
        raise PentaExecutionError("rollback and fallback must be objects")
    expected_rollback = {"method", "target_head_sha"} if head_sha is not None else {"method", "scope"}
    if set(rollback) != expected_rollback or rollback.get("method") != "git_revert":
        raise PentaExecutionError(f"rollback must have exact fields {sorted(expected_rollback)} and method git_revert")
    if head_sha is not None:
        target = _bounded_text(rollback.get("target_head_sha"), "rollback.target_head_sha", maximum=40)
        if target != head_sha:
            raise PentaExecutionError("rollback.target_head_sha must equal the evidence head_sha")
        normalized_rollback = {"method": "git_revert", "target_head_sha": target}
    else:
        normalized_rollback = {"method": "git_revert", "scope": _bounded_text(rollback.get("scope"), "rollback.scope", maximum=256)}
    if set(fallback) != {"method", "redundancy"} or fallback.get("method") != "hold":
        raise PentaExecutionError("fallback must have exact fields method=hold and redundancy")
    normalized_fallback = {"method": "hold", "redundancy": _bounded_text(fallback.get("redundancy"), "fallback.redundancy", maximum=256)}
    return normalized_rollback, normalized_fallback


def _evi_bundle_preview(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_evi_builder import TestReceipt, build_bundle
    required = {
        "work_order_id", "subject", "source_ref", "repo", "head_sha", "target_state",
        "authority_level", "observations", "claims", "test_receipts", "rollback",
        "fallback", "created_at",
    }
    unknown, missing = set(ctx.payload) - required, required - set(ctx.payload)
    if unknown or missing:
        raise PentaExecutionError(f"evidence preview payload fields invalid; missing={sorted(missing)} unknown={sorted(unknown)}")
    _reject_secret_fields(ctx.payload)
    if len(_canonical(ctx.payload).encode("utf-8")) > 100_000:
        raise PentaExecutionError("evidence preview payload exceeds 100000 bytes")
    observations, claims, receipt_rows = ctx.payload["observations"], ctx.payload["claims"], ctx.payload["test_receipts"]
    if not isinstance(observations, list) or not 1 <= len(observations) <= 50 or any(not isinstance(row, Mapping) or set(row) != {"kind", "result"} for row in observations):
        raise PentaExecutionError("observations must contain 1..50 exact {kind,result} objects")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 50 or any(not isinstance(row, Mapping) or set(row) != {"claim", "scope"} for row in claims):
        raise PentaExecutionError("claims must contain 1..50 exact {claim,scope} objects")
    if not isinstance(receipt_rows, list) or not 1 <= len(receipt_rows) <= 50 or any(not isinstance(row, Mapping) for row in receipt_rows):
        raise PentaExecutionError("test_receipts must contain 1..50 objects")
    risk_class = ctx.envelope.get("risk_class")
    authority_level = _bounded_text(ctx.payload["authority_level"], "authority_level", maximum=2)
    if authority_level not in {"D0", "D1", "D2"} or authority_level != risk_class:
        raise PentaExecutionError("evidence authority_level must equal the governed envelope risk_class")
    created_at = ctx.payload["created_at"]
    if not isinstance(created_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created_at):
        raise PentaExecutionError("created_at must be exact UTC YYYY-MM-DDTHH:MM:SSZ")
    try: datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc: raise PentaExecutionError("created_at is not a real UTC timestamp") from exc
    repo = _bounded_text(ctx.payload["repo"], "repo", maximum=113)
    if not re.fullmatch(r"crownthrive1/[A-Za-z0-9_.-]{1,100}", repo) or ".." in repo:
        raise PentaExecutionError("repo must be a crownthrive1 repository slug")
    head_sha = _bounded_text(ctx.payload["head_sha"], "head_sha", maximum=40)
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise PentaExecutionError("head_sha must be a lowercase 40-character Git SHA")
    target_state = _bounded_text(ctx.payload["target_state"], "target_state", maximum=32)
    if target_state not in {"CONTROLLED_TEST", "BUILD_CANDIDATE", "RELEASE_CANDIDATE", "HOLD"}:
        raise PentaExecutionError("target_state is outside the non-production preview vocabulary")
    normalized_observations = [{"kind": _bounded_text(row["kind"], "observation.kind"), "result": _bounded_text(row["result"], "observation.result", maximum=2000)} for row in observations]
    normalized_claims = [{"claim": _bounded_text(row["claim"], "claim.claim", maximum=2000), "scope": _bounded_text(row["scope"], "claim.scope")} for row in claims]
    receipts = []
    for row in receipt_rows:
        allowed = {"name", "status", "source", "details"}
        if set(row) - allowed or not {"name", "status", "source"}.issubset(row):
            raise PentaExecutionError("test receipt fields are invalid")
        status = _bounded_text(row["status"], "test_receipt.status", maximum=5).upper()
        if status not in {"PASS", "FAIL", "HOLD", "ERROR"}:
            raise PentaExecutionError("test receipt status is outside PASS/FAIL/HOLD/ERROR")
        details = row.get("details", "")
        if not isinstance(details, str) or len(details) > 2000:
            raise PentaExecutionError("test receipt details must be a string <= 2000 characters")
        receipts.append(TestReceipt(name=_bounded_text(row["name"], "test_receipt.name"), status=status, source=_repo_local_ref(row["source"], "test_receipt.source"), details=details))
    rollback, fallback = _recovery_contracts(ctx.payload["rollback"], ctx.payload["fallback"], head_sha=head_sha)
    try:
        bundle = build_bundle(
            work_order_id=_bounded_text(ctx.payload["work_order_id"], "work_order_id"), subject=_bounded_text(ctx.payload["subject"], "subject"),
            source_ref=_repo_local_ref(ctx.payload["source_ref"], "source_ref"), repo=repo,
            head_sha=head_sha, target_state=target_state,
            authority_level=authority_level, observations=normalized_observations,
            claims=normalized_claims, evidence_refs=ctx.evidence_refs, test_receipts=receipts,
            rollback=rollback, fallback=fallback, created_at=created_at,
        )
    except (TypeError, ValueError) as exc:
        raise PentaExecutionError(f"invalid evidence preview: {exc}") from exc
    return {"bundle": bundle, "adapter_boundary": "evidence_construction_only_unverified", "state_persisted": False, "independent_certification_performed": False, "provider_write": False, "production_promotion_authorized": False}


def _immune_repair_plan_preview(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_immune import WeaknessCandidate, build_repair_plan
    required = {
        "id", "kind", "source_ref", "authority_level", "handler", "severity",
        "recurrence", "confidence", "reversibility", "testability", "blast_radius",
        "rollback", "fallback", "metadata",
    }
    unknown, missing = set(ctx.payload) - required, required - set(ctx.payload)
    if unknown or missing:
        raise PentaExecutionError(f"repair preview payload fields invalid; missing={sorted(missing)} unknown={sorted(unknown)}")
    _reject_secret_fields(ctx.payload)
    if len(_canonical(ctx.payload).encode("utf-8")) > 50_000:
        raise PentaExecutionError("repair preview payload exceeds 50000 bytes")
    authority_level = _bounded_text(ctx.payload["authority_level"], "authority_level", maximum=2)
    if authority_level not in {"D0", "D1", "D2", "D3"} or authority_level != ctx.envelope.get("risk_class"):
        raise PentaExecutionError("candidate authority_level must equal the governed envelope risk_class")
    metadata = ctx.payload["metadata"]
    allowed_metadata = {"scope", "category", "component", "path", "failure_code", "test_name", "owner_ref", "description"}
    if not isinstance(metadata, Mapping) or len(metadata) > 16 or set(metadata) - allowed_metadata:
        raise PentaExecutionError("metadata must contain at most 16 allowlisted scalar fields")
    if any(not isinstance(value, (str, int, float, bool, type(None))) or isinstance(value, float) and not math.isfinite(value) for value in metadata.values()):
        raise PentaExecutionError("metadata values must be finite JSON scalars")
    if len(_canonical(metadata).encode("utf-8")) > 8_192:
        raise PentaExecutionError("metadata exceeds 8192 bytes")
    for field in ("severity", "recurrence", "confidence", "reversibility", "testability", "blast_radius"):
        if type(ctx.payload[field]) is not int or not 0 <= ctx.payload[field] <= 5:
            raise PentaExecutionError(f"{field} must be an integer from 0 through 5")
    rollback, fallback = _recovery_contracts(ctx.payload["rollback"], ctx.payload["fallback"])
    try:
        candidate = WeaknessCandidate(
            id=_bounded_text(ctx.payload["id"], "id", maximum=128),
            kind=_bounded_text(ctx.payload["kind"], "kind", maximum=64),
            source_ref=_repo_local_ref(ctx.payload["source_ref"], "source_ref"),
            authority_level=authority_level,
            handler=_bounded_text(ctx.payload["handler"], "handler", maximum=64),
            severity=ctx.payload["severity"], recurrence=ctx.payload["recurrence"], confidence=ctx.payload["confidence"],
            reversibility=ctx.payload["reversibility"], testability=ctx.payload["testability"], blast_radius=ctx.payload["blast_radius"],
            rollback=rollback, fallback=fallback, metadata=dict(metadata),
        )
        plan = build_repair_plan(candidate)
    except (TypeError, ValueError) as exc:
        raise PentaExecutionError(f"invalid repair preview: {exc}") from exc
    return {"plan": plan, "adapter_boundary": "bounded_plan_only_no_repair_execution", "state_persisted": False, "repair_executed": False, "provider_write": False, "production_promotion_authorized": False}


def _context_runtime_contract_status(ctx: AdapterContext) -> dict[str, Any]:
    if ctx.payload:
        _reject_secret_fields(ctx.payload)
        raise PentaExecutionError("context runtime contract status accepts no payload fields")
    fixed_paths = {
        "runtime": Path("runtime/penta_context.py"),
        "contract": Path("PENTACONTEXT.md"),
        "schema": Path("schemas/penta-context-record-v1.schema.json"),
    }
    resolved: dict[str, Path] = {}
    for role, relative in fixed_paths.items():
        path = (ctx.root / relative).resolve()
        if not path.is_relative_to(ctx.root.resolve()) or not path.is_file():
            raise PentaExecutionError(f"fixed PentaContext {role} is missing")
        resolved[role] = path
    module = _load_fixed_module("penta_context_exec_adapter", resolved["runtime"])
    if getattr(module, "SYSTEM_KEY", None) != "penta.context" or getattr(module, "VERSION", None) != "1.1.0":
        raise PentaExecutionError("unexpected PentaContext runtime identity/version")
    return {
        "schema": "ct.penta.context.runtime-contract-status.v1",
        "machine_key": module.SYSTEM_KEY,
        "runtime_version": module.VERSION,
        "source_sha256": {
            role: sha256(path.read_bytes()).hexdigest()
            for role, path in sorted(resolved.items())
        },
        "declared_actions": ["enqueue", "health", "ingest", "query", "queue_status"],
        "provider_binding_state": "SEPARATELY_GATED_NOT_EVALUATED",
        "current_provider_state": "NOT_EVALUATED_BY_LOCAL_ADAPTER",
        "context_is_authority": False,
        "credential_material_accepted": False,
        "network_probe_performed": False,
        "provider_write_performed": False,
        "provider_state_changed": False,
        "production_promotion_authorized": False,
    }


def _promoted_local_operation(ctx: AdapterContext, handler_name: str) -> dict[str, Any]:
    try:
        from runtime import penta_promoted_operations as promoted
    except ModuleNotFoundError:
        import penta_promoted_operations as promoted  # type: ignore[no-redef]
    handler = getattr(promoted, handler_name, None)
    if not callable(handler):
        raise PentaExecutionError(f"fixed promoted operation is unavailable: {handler_name}")
    try:
        result = handler(ctx)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        raise PentaExecutionError(f"promoted local operation failed closed: {exc}") from exc
    if not isinstance(result, dict):
        raise PentaExecutionError("promoted local operation must return an object")
    forbidden_truth = (
        "provider_write_performed",
        "provider_states_changed",
        "production_promotion_authorized",
        "self_certification_performed",
    )
    if any(result.get(field) is True for field in forbidden_truth):
        raise PentaExecutionError("promoted local operation attempted a forbidden authority effect")
    return result


def _mail_production_status(ctx: AdapterContext) -> dict[str, Any]:
    return _promoted_local_operation(ctx, "mail_production_status")


def _status_owner_snapshot(ctx: AdapterContext) -> dict[str, Any]:
    return _promoted_local_operation(ctx, "status_owner_snapshot")


def _credentials_binding_census(ctx: AdapterContext) -> dict[str, Any]:
    return _promoted_local_operation(ctx, "credentials_binding_census")


def _build_provider_adapter(ctx: AdapterContext) -> dict[str, Any]:
    return _promoted_local_operation(ctx, "build_provider_adapter")


def _certify_provider_static(ctx: AdapterContext) -> dict[str, Any]:
    return _promoted_local_operation(ctx, "certify_provider_static")


BUILTIN_HANDLERS: dict[str, Callable[[AdapterContext], dict[str, Any]]] = {
    "family_snapshot": _family_snapshot, "beata_heartbeat": _beata_heartbeat, "mesh_route_check": _mesh_route_check,
    "error_normalize": _error_normalize, "logger_emit": _logger_emit, "trace_new_context": _trace_new_context, "metric_snapshot": _metric_snapshot,
    "heartbeat_control_plane_probe": _heartbeat_control_plane_probe, "od_readiness_assess": _od_readiness_assess,
    "compliance_evaluate": _compliance_evaluate, "license_readiness": _license_readiness,
    "scribe_reconcile_preview": _scribe_reconcile_preview, "marketer_cycle_preview": _marketer_cycle_preview,
    "evi_bundle_preview": _evi_bundle_preview, "immune_repair_plan_preview": _immune_repair_plan_preview,
    "context_runtime_contract_status": _context_runtime_contract_status,
    "mail_production_status": _mail_production_status, "status_owner_snapshot": _status_owner_snapshot,
    "credentials_binding_census": _credentials_binding_census, "build_provider_adapter": _build_provider_adapter,
    "certify_provider_static": _certify_provider_static,
}


def family_validate(root: Path, registry: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    members, adapters = _members(snapshot), load_adapter_registry(root)
    blockers: list[dict[str, Any]] = []; warnings: list[dict[str, Any]] = []
    for key, member in members.items():
        for field in ("canonical_name", "maturity", "portal_route", "source"):
            if not member.get(field): blockers.append({"machine_key": key, "kind": "missing_member_field", "field": field})
        for dep in member.get("dependencies") or []:
            if dep not in members: warnings.append({"machine_key": key, "kind": "unresolved_dependency", "dependency": dep})
    adapter_members: set[str] = set()
    for adapter in adapters["adapters"]:
        target = adapter["member"]; adapter_members.add(target)
        if target not in members: blockers.append({"adapter_id": adapter["adapter_id"], "kind": "unknown_adapter_member", "member": target})
        elif adapter["requires_execution_eligible"] and members[target].get("maturity") not in EXECUTION_ELIGIBLE: blockers.append({"adapter_id": adapter["adapter_id"], "kind": "adapter_targets_ineligible_member", "member": target, "maturity": members[target].get("maturity")})
    eligible = sorted(key for key, member in members.items() if member.get("maturity") in EXECUTION_ELIGIBLE)
    missing_adapters = sorted(set(eligible) - adapter_members)
    for key in missing_adapters: blockers.append({"machine_key": key, "kind": "execution_eligible_member_missing_adapter", "maturity": members[key].get("maturity")})
    coverage = {"eligible_member_count": len(eligible), "eligible_members_with_adapter": len(set(eligible) & adapter_members), "missing_adapter_members": missing_adapters, "complete": not missing_adapters}
    return _receipt("family_validate", "pass" if not blockers else "fail_closed", {"family_registry_id": registry.get("registry_id"), "member_count": len(members), "adapter_count": len(adapters["adapters"]), "execution_adapter_coverage": coverage, "blockers": blockers, "warnings": warnings})


def invoke_member(root: Path, *, source_member: str, target_member: str, operation: str, evidence_refs: Iterable[str], payload: Optional[Mapping[str, Any]] = None, risk_class: str = "D1", authority_trace: Optional[Mapping[str, Optional[str]]] = None, human_gate: Optional[Mapping[str, Any]] = None, provider_binding_ref: Optional[str] = None, readback_strategy: Optional[str] = None, idempotency_key: Optional[str] = None) -> dict[str, Any]:
    registry, snapshot = load_family(root); _member(snapshot, source_member); target = _member(snapshot, target_member); adapters = load_adapter_registry(root); adapter = _find_adapter(adapters, target_member, operation)
    if adapter is None: return _receipt("member_invoke", "hold_fail_closed", {"source_member": source_member, "target_member": target_member, "operation": operation, "reason": "no registered executable adapter for member/operation"})
    if adapter["requires_execution_eligible"] and target.get("maturity") not in EXECUTION_ELIGIBLE: return _receipt("member_invoke", "hold_fail_closed", {"source_member": source_member, "target_member": target_member, "operation": operation, "reason": f"target maturity {target.get('maturity')!r} is not execution-eligible"})
    raw_refs = list(evidence_refs)
    if not 1 <= len(raw_refs) <= 50 or any(not isinstance(ref, str) for ref in raw_refs):
        raise PentaExecutionError("evidence_refs must contain 1..50 strings")
    refs = tuple(_repo_local_ref(ref, "evidence_ref") for ref in raw_refs)
    if len(refs) != len(set(refs)):
        raise PentaExecutionError("duplicate evidence_refs are not accepted")
    envelope = build_envelope(source_member=source_member, target_member=target_member, operation=operation, requested_effect=adapter["requested_effect"], evidence_refs=refs, risk_class=risk_class, authority_trace=authority_trace, human_gate=human_gate, provider_effect=adapter["provider_effect"], provider_binding_ref=provider_binding_ref, readback_strategy=readback_strategy, idempotency_key=idempotency_key, metadata={"adapter_id": adapter["adapter_id"], "runtime_version": RUNTIME_VERSION})
    decision = evaluate_handoff(snapshot, envelope)
    if decision.get("eligible") is not True: return _receipt("member_invoke", "hold_fail_closed", {"source_member": source_member, "target_member": target_member, "operation": operation, "adapter_id": adapter["adapter_id"], "handoff_decision": decision, "envelope_sha256": envelope.get("envelope_sha256")})
    ctx = AdapterContext(root, registry, snapshot, source_member, target_member, operation, dict(payload or {}), refs, envelope, decision)
    try: result = BUILTIN_HANDLERS[adapter["handler"]](ctx)
    except PentaExecutionError: raise
    except Exception as exc: return _receipt("member_invoke", "handler_failed", {"source_member": source_member, "target_member": target_member, "operation": operation, "adapter_id": adapter["adapter_id"], "error_type": type(exc).__name__, "error": str(exc)})
    return _receipt("member_invoke", "completed", {"source_member": source_member, "target_member": target_member, "operation": operation, "adapter_id": adapter["adapter_id"], "requested_effect": adapter["requested_effect"], "provider_effect": False, "handoff_disposition": decision.get("disposition"), "trace_id": envelope.get("trace_id"), "correlation_id": envelope.get("correlation_id"), "idempotency_key": envelope.get("idempotency_key"), "envelope_sha256": envelope.get("envelope_sha256"), "result": result})


def build_handoff(root: Path, *, source_member: str, target_member: str, operation: str, requested_effect: str, evidence_refs: Iterable[str], risk_class: str = "D1", authority_trace: Optional[Mapping[str, Optional[str]]] = None, human_gate: Optional[Mapping[str, Any]] = None, provider_effect: bool = False, provider_binding_ref: Optional[str] = None, readback_strategy: Optional[str] = None) -> dict[str, Any]:
    _, snapshot = load_family(root); _member(snapshot, source_member); _member(snapshot, target_member)
    envelope = build_envelope(source_member=source_member, target_member=target_member, operation=operation, requested_effect=requested_effect, evidence_refs=evidence_refs, risk_class=risk_class, authority_trace=authority_trace, human_gate=human_gate, provider_effect=provider_effect, provider_binding_ref=provider_binding_ref, readback_strategy=readback_strategy)
    decision = evaluate_handoff(snapshot, envelope); return _receipt("handoff", str(decision.get("disposition")), {"envelope": envelope, "decision": decision})


def _json_arg(value: Optional[str]) -> dict[str, Any]:
    if not value: return {}
    try: parsed = json.loads(value)
    except json.JSONDecodeError as exc: raise PentaExecutionError(f"invalid JSON argument: {exc}") from exc
    if not isinstance(parsed, dict): raise PentaExecutionError("JSON argument must be an object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executable CrownThrive Penta Family control plane"); parser.add_argument("--root", default="."); sub = parser.add_subparsers(dest="command", required=True); sub.add_parser("list"); status = sub.add_parser("status"); status.add_argument("machine_key"); sub.add_parser("validate")
    handoff = sub.add_parser("handoff"); handoff.add_argument("source_member"); handoff.add_argument("target_member"); handoff.add_argument("operation"); handoff.add_argument("--effect", choices=sorted(VALID_EFFECTS), default="prepare"); handoff.add_argument("--risk", choices=["D0", "D1", "D2", "D3"], default="D1"); handoff.add_argument("--evidence-ref", action="append", required=True); handoff.add_argument("--authority-json"); handoff.add_argument("--human-gate-json"); handoff.add_argument("--provider-effect", action="store_true"); handoff.add_argument("--provider-binding-ref"); handoff.add_argument("--readback-strategy")
    invoke = sub.add_parser("invoke"); invoke.add_argument("source_member"); invoke.add_argument("target_member"); invoke.add_argument("operation"); invoke.add_argument("--risk", choices=["D0", "D1", "D2", "D3"], default="D1"); invoke.add_argument("--evidence-ref", action="append", required=True); invoke.add_argument("--payload-json"); invoke.add_argument("--authority-json"); invoke.add_argument("--human-gate-json"); invoke.add_argument("--provider-binding-ref"); invoke.add_argument("--readback-strategy"); invoke.add_argument("--idempotency-key"); return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv); root = Path(args.root).resolve()
    try:
        registry, snapshot = load_family(root)
        if args.command == "list": result = family_list(snapshot)
        elif args.command == "status": result = member_status(snapshot, args.machine_key)
        elif args.command == "validate": result = family_validate(root, registry, snapshot)
        elif args.command == "handoff": result = build_handoff(root, source_member=args.source_member, target_member=args.target_member, operation=args.operation, requested_effect=args.effect, evidence_refs=args.evidence_ref, risk_class=args.risk, authority_trace=_json_arg(args.authority_json) or None, human_gate=_json_arg(args.human_gate_json) or None, provider_effect=args.provider_effect, provider_binding_ref=args.provider_binding_ref, readback_strategy=args.readback_strategy)
        else: result = invoke_member(root, source_member=args.source_member, target_member=args.target_member, operation=args.operation, evidence_refs=args.evidence_ref, payload=_json_arg(args.payload_json), risk_class=args.risk, authority_trace=_json_arg(args.authority_json) or None, human_gate=_json_arg(args.human_gate_json) or None, provider_binding_ref=args.provider_binding_ref, readback_strategy=args.readback_strategy, idempotency_key=args.idempotency_key)
    except Exception as exc:
        result = _receipt("runtime_error", "hold_fail_closed", {"error_type": type(exc).__name__, "error": str(exc)}); print(json.dumps(result, indent=2, sort_keys=True)); return 2
    print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result.get("disposition") not in {"fail_closed", "hold_fail_closed", "handler_failed"} else 3


if __name__ == "__main__": raise SystemExit(main())
