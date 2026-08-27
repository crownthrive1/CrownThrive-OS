#!/usr/bin/env python3
"""Executable control plane for the CrownThrive Penta Family.

Every registered Penta is addressable for status and governed handoffs. Actual
member invocation requires a statically registered bounded adapter and passes
family/interoperability gates. No arbitrary shell, user-selected dynamic import,
credential material, money movement or provider write is exposed by this local
adapter layer.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable, Iterable, Mapping, Optional
from uuid import uuid4

try:
    from runtime.penta_family import load_family, member_dispatch_gate
    from runtime.penta_interop import build_envelope, evaluate_handoff
except ModuleNotFoundError:
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
    from runtime.penta_family import load_family, member_dispatch_gate
    from runtime.penta_interop import build_envelope, evaluate_handoff

RUNTIME_VERSION = "1.4.0"
ADAPTER_REGISTRY = Path("data/penta/execution-adapters.registry.json")
EXECUTION_ELIGIBLE = {"certified", "production"}
VALID_EFFECTS = {"analyze", "prepare", "route", "execute", "verify", "preserve"}


class PentaExecutionError(ValueError): pass


def _utcnow() -> str: return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def _canonical(value: Mapping[str, Any]) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
def _seal(value: Mapping[str, Any]) -> str: return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _receipt(kind: str, disposition: str, details: Mapping[str, Any]) -> dict[str, Any]:
    value: dict[str, Any] = {"schema": "ct.penta.execution-receipt.v1", "runtime_version": RUNTIME_VERSION, "receipt_id": f"pex-{uuid4().hex}", "kind": kind, "disposition": disposition, "created_at": _utcnow(), "details": dict(details)}
    value["receipt_sha256"] = _seal(value); return value


def _load_json(path: Path) -> dict[str, Any]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise PentaExecutionError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict): raise PentaExecutionError(f"JSON root must be object: {path}")
    return value


def _load_fixed_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise PentaExecutionError(f"cannot load fixed runtime: {path}")
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


def _members(snapshot: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    value = snapshot.get("members")
    if not isinstance(value, Mapping): raise PentaExecutionError("family snapshot has no members map")
    return value  # type: ignore[return-value]


def _member(snapshot: Mapping[str, Any], machine_key: str) -> Mapping[str, Any]:
    value = _members(snapshot).get(machine_key)
    if not isinstance(value, Mapping): raise PentaExecutionError(f"unknown or unregistered Penta member: {machine_key}")
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
    missing = sorted(row["machine_key"] for row in deps if not row["registered"])
    return _receipt("member_status", "healthy_control_plane" if not missing else "degraded_control_plane", {"machine_key": machine_key, "canonical_name": member.get("canonical_name"), "category": member.get("category"), "purpose": member.get("purpose"), "authority_boundary": member.get("authority_boundary"), "risk_ceiling": member.get("risk_ceiling"), "maturity": member.get("maturity"), "maturity_promotion": member.get("maturity_promotion"), "portal_route": member.get("portal_route"), "execution_gate": member_dispatch_gate(snapshot, machine_key), "dependencies": deps, "missing_dependencies": missing, "source": member.get("source")})


def validate_adapter_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("registry_id") != "crownthrive.penta.execution-adapters": raise PentaExecutionError("unexpected adapter registry_id")
    if registry.get("version") != "1.4.0" or registry.get("fail_closed") is not True: raise PentaExecutionError("adapter registry must be v1.4.0 and fail closed")
    adapters = registry.get("adapters")
    if not isinstance(adapters, list): raise PentaExecutionError("adapters must be a list")
    seen_ids: set[str] = set(); seen_routes: set[tuple[str, str]] = set()
    for adapter in adapters:
        if not isinstance(adapter, Mapping): raise PentaExecutionError("adapter entry must be object")
        required = {"adapter_id", "member", "operation", "handler", "requested_effect", "provider_effect", "requires_execution_eligible"}
        missing = required - set(adapter)
        if missing: raise PentaExecutionError(f"adapter missing fields: {sorted(missing)}")
        aid, member, operation = adapter["adapter_id"], adapter["member"], adapter["operation"]
        if not isinstance(aid, str) or not aid: raise PentaExecutionError("adapter_id must be non-empty string")
        if aid in seen_ids: raise PentaExecutionError(f"duplicate adapter_id: {aid}")
        seen_ids.add(aid)
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
    return next((a for a in registry.get("adapters") or [] if a.get("member") == member and a.get("operation") == operation), None)


def _member_adapter_operations(registry: Mapping[str, Any], key: str) -> list[str]: return sorted(str(a["operation"]) for a in registry.get("adapters") or [] if a.get("member") == key)


@dataclass(frozen=True)
class AdapterContext:
    root: Path; registry: Mapping[str, Any]; snapshot: Mapping[str, Any]; source_member: str; target_member: str; operation: str; payload: Mapping[str, Any]; evidence_refs: tuple[str, ...]; envelope: Mapping[str, Any]; handoff_decision: Mapping[str, Any]


def _family_snapshot(ctx: AdapterContext) -> dict[str, Any]: return {"family_status": ctx.snapshot.get("family_status"), "production_scope": ctx.snapshot.get("production_scope"), "member_count": ctx.snapshot.get("member_count"), "maturity_counts": ctx.snapshot.get("maturity_counts"), "execution_eligible_members": ctx.snapshot.get("execution_eligible_members"), "promoted_members": ctx.snapshot.get("promoted_members", []), "held_members": ctx.snapshot.get("held_members")}

def _beata_heartbeat(ctx: AdapterContext) -> dict[str, Any]:
    details = member_status(ctx.snapshot, "penta.beata")["details"]; return {"state": "alive" if not details["missing_dependencies"] else "degraded", "machine_key": "penta.beata", "maturity": details["maturity"], "missing_dependencies": details["missing_dependencies"], "observed_at": _utcnow()}

def _mesh_route_check(ctx: AdapterContext) -> dict[str, Any]:
    candidate = ctx.payload.get("candidate_target")
    if not isinstance(candidate, str) or not candidate.startswith("penta."): raise PentaExecutionError("route_check payload.candidate_target must be exact penta.* machine key")
    member, gate = _member(ctx.snapshot, candidate), member_dispatch_gate(ctx.snapshot, candidate); return {"candidate_target": candidate, "registered": True, "maturity": member.get("maturity"), "execution_eligible": bool(gate.get("eligible")), "portal_route": member.get("portal_route"), "dependency_count": len(member.get("dependencies") or [])}

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
    lines: list[str] = []; record = PentaLogger(service=service, penta_member="penta.logger", minimum_severity=Severity.DEBUG, sink=lines.append).emit(severity, message, event=event, context=context)
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
    metrics, count = MetricRegistry(), 0
    for name, value in counters.items():
        if not isinstance(value, (int, float)): raise PentaExecutionError("counter values must be numeric")
        metrics.increment(str(name), float(value))
    for name, value in gauges.items():
        if not isinstance(value, (int, float)): raise PentaExecutionError("gauge values must be numeric")
        metrics.gauge(str(name), float(value))
    for name, values in observations.items():
        if not isinstance(values, list): raise PentaExecutionError("observation values must be arrays")
        count += len(values)
        if count > 1000: raise PentaExecutionError("metric_snapshot accepts at most 1000 observations")
        for value in values:
            if not isinstance(value, (int, float)): raise PentaExecutionError("observation values must be numeric")
            metrics.observe(str(name), float(value))
    return metrics.snapshot()

def _heartbeat_control_plane_probe(ctx: AdapterContext) -> dict[str, Any]:
    ar = load_adapter_registry(ctx.root); production = sorted(k for k, m in _members(ctx.snapshot).items() if m.get("maturity") == "production"); rows=[]
    for key in production:
        status=member_status(ctx.snapshot,key)["details"]; ops=_member_adapter_operations(ar,key); rows.append({"machine_key":key,"maturity":status["maturity"],"registered":True,"dependency_gaps":status["missing_dependencies"],"adapter_operations":ops,"adapter_bound":bool(ops)})
    return {"schema":"ct.penta.heartbeat.control-plane-probe.v1","observed_at":_utcnow(),"production_member_count":len(rows),"healthy":all(r["adapter_bound"] and not r["dependency_gaps"] for r in rows),"members":rows}

def _od_readiness_assess(ctx: AdapterContext) -> dict[str, Any]:
    candidate=ctx.payload.get("candidate_target")
    if not isinstance(candidate,str) or not candidate.startswith("penta."): raise PentaExecutionError("readiness_assess requires payload.candidate_target")
    ar=load_adapter_registry(ctx.root); member=_member(ctx.snapshot,candidate); status=member_status(ctx.snapshot,candidate)["details"]; gate=member_dispatch_gate(ctx.snapshot,candidate); ops=_member_adapter_operations(ar,candidate); ready=bool(gate.get("eligible")) and bool(ops) and not status["missing_dependencies"]
    return {"schema":"ct.penta.od.readiness.v1","candidate_target":candidate,"maturity":member.get("maturity"),"execution_eligible":bool(gate.get("eligible")),"adapter_operations":ops,"dependency_gaps":status["missing_dependencies"],"ready_for_bounded_dispatch":ready,"authority_expanded":False,"observed_at":_utcnow()}

def _compliance_evaluate(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_compliance_license import evaluate_compliance
    obligations,jurisdictions,scopes,evidence_index,as_of=ctx.payload.get("obligations"),ctx.payload.get("jurisdictions"),ctx.payload.get("scopes"),ctx.payload.get("evidence_index"),ctx.payload.get("as_of")
    if not isinstance(obligations,list) or not isinstance(jurisdictions,list) or not isinstance(scopes,list) or not isinstance(evidence_index,Mapping): raise PentaExecutionError("compliance evaluate requires obligations/jurisdictions/scopes/evidence_index")
    try: as_of_date=date.fromisoformat(str(as_of))
    except ValueError as exc: raise PentaExecutionError("compliance as_of must be ISO date") from exc
    return evaluate_compliance(obligations,jurisdictions=jurisdictions,scopes=scopes,evidence_index=evidence_index,as_of=as_of_date)

def _license_readiness(ctx: AdapterContext) -> dict[str, Any]:
    from runtime.penta_compliance_license import evaluate_license_request
    asset,request=ctx.payload.get("asset"),ctx.payload.get("request")
    if not isinstance(asset,Mapping) or not isinstance(request,Mapping): raise PentaExecutionError("license readiness requires asset and request objects")
    return {"decision":evaluate_license_request(asset,request),"adapter_boundary":"readiness_only_no_license_grant_issued","binding_action_performed":False}

def _scribe_reconcile_preview(ctx: AdapterContext) -> dict[str, Any]:
    runtime=_load_fixed_module("penta_exec_scribe_runtime",ctx.root/"penta/scribe/runtime.py"); scan=ctx.payload.get("scan_text","PentaScribe production adapter health probe.")
    if not isinstance(scan,str) or len(scan)>100000: raise PentaExecutionError("scribe scan_text must be a string <= 100000 chars")
    authority=ctx.payload.get("authority_ref") or f"penta-exec:{ctx.evidence_refs[0]}"
    with tempfile.TemporaryDirectory() as tmp:
        state,source=Path(tmp)/"state",Path(tmp)/"source.md"; source.write_text(scan,encoding="utf-8"); result=runtime.cycle(ctx.root/"penta/scribe/registry.json",state,[source],authority); return {"summary":result["summary"],"receipt":result["receipt"],"state_persisted":False,"provider_write":False}

def _marketer_cycle_preview(ctx: AdapterContext) -> dict[str, Any]:
    runtime=_load_fixed_module("penta_exec_marketer_runtime",ctx.root/"penta/marketer/runtime.py"); campaign=ctx.payload.get("campaign")
    with tempfile.TemporaryDirectory() as tmp:
        tr=Path(tmp)
        if campaign is None: cp=ctx.root/"penta/marketer/campaign.example.json"
        else:
            if not isinstance(campaign,Mapping): raise PentaExecutionError("marketer campaign must be an object")
            cp=tr/"campaign.json"; cp.write_text(json.dumps(dict(campaign),sort_keys=True),encoding="utf-8")
        result=runtime.cycle(cp,tr/"state",ctx.root/"penta/marketer/adapters.registry.json",ctx.root/"penta/scribe/registry.json",ctx.root/"penta/marketer/policy.json"); return {"summary":result["summary"],"receipt":result["receipt"],"state_persisted":False,"provider_write":False}


def _promoted(name: str, ctx: AdapterContext) -> dict[str, Any]:
    from runtime import penta_promoted_operations as ppo
    try: return getattr(ppo, name)(ctx)
    except Exception as exc:
        if exc.__class__.__name__ == "PromotedOperationError": raise PentaExecutionError(str(exc)) from exc
        raise


def _mail_production_status(ctx: AdapterContext): return _promoted("mail_production_status",ctx)
def _status_owner_snapshot(ctx: AdapterContext): return _promoted("status_owner_snapshot",ctx)
def _credentials_binding_census(ctx: AdapterContext): return _promoted("credentials_binding_census",ctx)
def _build_provider_adapter(ctx: AdapterContext): return _promoted("build_provider_adapter",ctx)
def _certify_provider_static(ctx: AdapterContext): return _promoted("certify_provider_static",ctx)
def _evi_builder_evidence_preview(ctx: AdapterContext): return _promoted("evi_builder_evidence_preview",ctx)
def _immune_repair_plan_preview(ctx: AdapterContext): return _promoted("immune_repair_plan_preview",ctx)

BUILTIN_HANDLERS: dict[str, Callable[[AdapterContext],dict[str,Any]]] = {
    "family_snapshot":_family_snapshot,"beata_heartbeat":_beata_heartbeat,"mesh_route_check":_mesh_route_check,"error_normalize":_error_normalize,"logger_emit":_logger_emit,"trace_new_context":_trace_new_context,"metric_snapshot":_metric_snapshot,"heartbeat_control_plane_probe":_heartbeat_control_plane_probe,"od_readiness_assess":_od_readiness_assess,"compliance_evaluate":_compliance_evaluate,"license_readiness":_license_readiness,"scribe_reconcile_preview":_scribe_reconcile_preview,"marketer_cycle_preview":_marketer_cycle_preview,
    "mail_production_status":_mail_production_status,"status_owner_snapshot":_status_owner_snapshot,"credentials_binding_census":_credentials_binding_census,"build_provider_adapter":_build_provider_adapter,"certify_provider_static":_certify_provider_static,
    "evi_builder_evidence_preview":_evi_builder_evidence_preview,"immune_repair_plan_preview":_immune_repair_plan_preview,
}


def family_validate(root: Path, registry: Mapping[str,Any], snapshot: Mapping[str,Any]) -> dict[str,Any]:
    members, adapters = _members(snapshot), load_adapter_registry(root); blockers=[]; warnings=[]
    for key, member in members.items():
        for field in ("canonical_name","maturity","portal_route","source"):
            if not member.get(field): blockers.append({"machine_key":key,"kind":"missing_member_field","field":field})
        for dep in member.get("dependencies") or []:
            if dep not in members: warnings.append({"machine_key":key,"kind":"unresolved_dependency","dependency":dep})
    adapter_members=set()
    for adapter in adapters["adapters"]:
        target=adapter["member"]; adapter_members.add(target)
        if target not in members: blockers.append({"adapter_id":adapter["adapter_id"],"kind":"unknown_adapter_member","member":target})
        elif adapter["requires_execution_eligible"] and members[target].get("maturity") not in EXECUTION_ELIGIBLE: blockers.append({"adapter_id":adapter["adapter_id"],"kind":"adapter_targets_ineligible_member","member":target,"maturity":members[target].get("maturity")})
    eligible=sorted(k for k,m in members.items() if m.get("maturity") in EXECUTION_ELIGIBLE); missing=sorted(set(eligible)-adapter_members)
    for key in missing: blockers.append({"machine_key":key,"kind":"execution_eligible_member_missing_adapter","maturity":members[key].get("maturity")})
    coverage={"eligible_member_count":len(eligible),"eligible_members_with_adapter":len(set(eligible)&adapter_members),"missing_adapter_members":missing,"complete":not missing}
    return _receipt("family_validate","pass" if not blockers else "fail_closed",{"family_registry_id":registry.get("registry_id"),"member_count":len(members),"adapter_count":len(adapters["adapters"]),"promotion_count":snapshot.get("promotion_count",0),"execution_adapter_coverage":coverage,"blockers":blockers,"warnings":warnings})


def invoke_member(root: Path, *, source_member: str, target_member: str, operation: str, evidence_refs: Iterable[str], payload: Optional[Mapping[str,Any]]=None, risk_class: str="D1", authority_trace: Optional[Mapping[str,Optional[str]]]=None, human_gate: Optional[Mapping[str,Any]]=None, provider_binding_ref: Optional[str]=None, readback_strategy: Optional[str]=None, idempotency_key: Optional[str]=None) -> dict[str,Any]:
    registry,snapshot=load_family(root); _member(snapshot,source_member); target=_member(snapshot,target_member); adapters=load_adapter_registry(root); adapter=_find_adapter(adapters,target_member,operation)
    if adapter is None: return _receipt("member_invoke","hold_fail_closed",{"source_member":source_member,"target_member":target_member,"operation":operation,"reason":"no registered executable adapter for member/operation"})
    if adapter["requires_execution_eligible"] and target.get("maturity") not in EXECUTION_ELIGIBLE: return _receipt("member_invoke","hold_fail_closed",{"source_member":source_member,"target_member":target_member,"operation":operation,"reason":f"target maturity {target.get('maturity')!r} is not execution-eligible"})
    refs=tuple(dict.fromkeys(str(ref) for ref in evidence_refs if str(ref).strip()))
    if not refs: raise PentaExecutionError("at least one evidence reference is required")
    envelope=build_envelope(source_member=source_member,target_member=target_member,operation=operation,requested_effect=adapter["requested_effect"],evidence_refs=refs,risk_class=risk_class,authority_trace=authority_trace,human_gate=human_gate,provider_effect=adapter["provider_effect"],provider_binding_ref=provider_binding_ref,readback_strategy=readback_strategy,idempotency_key=idempotency_key,metadata={"adapter_id":adapter["adapter_id"],"runtime_version":RUNTIME_VERSION})
    decision=evaluate_handoff(snapshot,envelope)
    if decision.get("eligible") is not True: return _receipt("member_invoke","hold_fail_closed",{"source_member":source_member,"target_member":target_member,"operation":operation,"adapter_id":adapter["adapter_id"],"handoff_decision":decision,"envelope_sha256":envelope.get("envelope_sha256")})
    ctx=AdapterContext(root,registry,snapshot,source_member,target_member,operation,dict(payload or {}),refs,envelope,decision)
    try: result=BUILTIN_HANDLERS[adapter["handler"]](ctx)
    except PentaExecutionError: raise
    except Exception as exc: return _receipt("member_invoke","handler_failed",{"source_member":source_member,"target_member":target_member,"operation":operation,"adapter_id":adapter["adapter_id"],"error_type":type(exc).__name__,"error":str(exc)})
    return _receipt("member_invoke","completed",{"source_member":source_member,"target_member":target_member,"operation":operation,"adapter_id":adapter["adapter_id"],"requested_effect":adapter["requested_effect"],"provider_effect":False,"handoff_disposition":decision.get("disposition"),"trace_id":envelope.get("trace_id"),"correlation_id":envelope.get("correlation_id"),"idempotency_key":envelope.get("idempotency_key"),"envelope_sha256":envelope.get("envelope_sha256"),"result":result})


def build_handoff(root: Path, *, source_member: str,target_member: str,operation: str,requested_effect: str,evidence_refs: Iterable[str],risk_class: str="D1",authority_trace: Optional[Mapping[str,Optional[str]]]=None,human_gate: Optional[Mapping[str,Any]]=None,provider_effect: bool=False,provider_binding_ref: Optional[str]=None,readback_strategy: Optional[str]=None) -> dict[str,Any]:
    _,snapshot=load_family(root); _member(snapshot,source_member); _member(snapshot,target_member); envelope=build_envelope(source_member=source_member,target_member=target_member,operation=operation,requested_effect=requested_effect,evidence_refs=evidence_refs,risk_class=risk_class,authority_trace=authority_trace,human_gate=human_gate,provider_effect=provider_effect,provider_binding_ref=provider_binding_ref,readback_strategy=readback_strategy); decision=evaluate_handoff(snapshot,envelope); return _receipt("handoff",str(decision.get("disposition")),{"envelope":envelope,"decision":decision})


def _json_arg(value: Optional[str]) -> dict[str,Any]:
    if not value: return {}
    try: parsed=json.loads(value)
    except json.JSONDecodeError as exc: raise PentaExecutionError(f"invalid JSON argument: {exc}") from exc
    if not isinstance(parsed,dict): raise PentaExecutionError("JSON argument must be an object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="Executable CrownThrive Penta Family control plane"); p.add_argument("--root",default="."); sub=p.add_subparsers(dest="command",required=True); sub.add_parser("list"); s=sub.add_parser("status"); s.add_argument("machine_key"); sub.add_parser("validate")
    h=sub.add_parser("handoff"); h.add_argument("source_member"); h.add_argument("target_member"); h.add_argument("operation"); h.add_argument("--effect",choices=sorted(VALID_EFFECTS),default="prepare"); h.add_argument("--risk",choices=["D0","D1","D2","D3"],default="D1"); h.add_argument("--evidence-ref",action="append",required=True); h.add_argument("--authority-json"); h.add_argument("--human-gate-json"); h.add_argument("--provider-effect",action="store_true"); h.add_argument("--provider-binding-ref"); h.add_argument("--readback-strategy")
    i=sub.add_parser("invoke"); i.add_argument("source_member"); i.add_argument("target_member"); i.add_argument("operation"); i.add_argument("--risk",choices=["D0","D1","D2","D3"],default="D1"); i.add_argument("--evidence-ref",action="append",required=True); i.add_argument("--payload-json"); i.add_argument("--authority-json"); i.add_argument("--human-gate-json"); i.add_argument("--provider-binding-ref"); i.add_argument("--readback-strategy"); i.add_argument("--idempotency-key"); return p


def main(argv: Optional[list[str]]=None) -> int:
    args=_parser().parse_args(argv); root=Path(args.root).resolve()
    try:
        registry,snapshot=load_family(root)
        if args.command=="list": result=family_list(snapshot)
        elif args.command=="status": result=member_status(snapshot,args.machine_key)
        elif args.command=="validate": result=family_validate(root,registry,snapshot)
        elif args.command=="handoff": result=build_handoff(root,source_member=args.source_member,target_member=args.target_member,operation=args.operation,requested_effect=args.effect,evidence_refs=args.evidence_ref,risk_class=args.risk,authority_trace=_json_arg(args.authority_json) or None,human_gate=_json_arg(args.human_gate_json) or None,provider_effect=args.provider_effect,provider_binding_ref=args.provider_binding_ref,readback_strategy=args.readback_strategy)
        else: result=invoke_member(root,source_member=args.source_member,target_member=args.target_member,operation=args.operation,evidence_refs=args.evidence_ref,payload=_json_arg(args.payload_json),risk_class=args.risk,authority_trace=_json_arg(args.authority_json) or None,human_gate=_json_arg(args.human_gate_json) or None,provider_binding_ref=args.provider_binding_ref,readback_strategy=args.readback_strategy,idempotency_key=args.idempotency_key)
    except Exception as exc:
        result=_receipt("runtime_error","hold_fail_closed",{"error_type":type(exc).__name__,"error":str(exc)}); print(json.dumps(result,indent=2,sort_keys=True)); return 2
    print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result.get("disposition") not in {"fail_closed","hold_fail_closed","handler_failed"} else 3

if __name__=="__main__": raise SystemExit(main())
