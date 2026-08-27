#!/usr/bin/env python3
"""Integrate Penta Promotion Wave 3 additively into the current PentaOS mainline.

This transformer runs only in the temporary ECT integration workflow. It starts
from current main, preserves PentaOS V1.5, adds explicit evidence-bound maturity
promotion, binds bounded provider-effect-free operations, and never promotes or
executes D3/provider effects automatically.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

ROOT = Path.cwd()
OLD_HEAD = os.environ.get("OLD_HEAD", "105460c828e8baf0d034d43689b278b47d2f9833")
RUNTIME_VERSION = "1.4.0"
PROMOTION_TARGETS = [
    "penta.mail",
    "penta.status",
    "penta.credentials",
    "penta.build",
    "penta.certify",
]


class IntegrationError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IntegrationError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def git_show(path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{OLD_HEAD}:{path}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise IntegrationError(f"cannot read archived Wave 3 file {path}: {result.stderr.strip()}")
    return result.stdout


def copy_archived(path: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(git_show(path), encoding="utf-8")


def add_context_catalog() -> None:
    catalog_path = ROOT / "data/penta/systems.extensions.context.json"
    catalog = {
        "schema_version": "1.0.0",
        "registry_id": "crownthrive.penta.systems.extensions.context",
        "doctrine": "Discover -> Govern -> Execute -> Verify -> Preserve",
        "maturity_rule": "PentaContext production state is evidence-backed by its v1.0/v1.1 canaries, runtime contract tests, service-role boundary, and automated queue/maintenance schedules; registration creates no authority.",
        "systems": [
            {
                "machine_key": "penta.context",
                "canonical_name": "PentaContext",
                "aliases": ["Penta Context"],
                "category": "institutional_knowledge_context",
                "purpose": "Provide scoped, provenance-aware, redacted operational memory and bounded context retrieval across approved CrownThrive systems without manufacturing authority.",
                "human_surface": "Internal context health, queue, source provenance, retrieval and evidence views",
                "authority_boundary": "Context is evidence and operational memory only. It never creates credentials, permissions, governance approval, provider-write authority, legal authority, money movement, or D3 effects.",
                "risk_ceiling": "D2",
                "maturity": "production",
                "dependencies": ["penta.docs", "penta.route", "penta.credentials", "penta.status"],
                "runtime_refs": ["runtime/penta_context.py", "supabase/functions/penta-context/index.ts"],
                "evidence_refs": ["PENTACONTEXT.md", "tests/test_penta_context.py", ".github/workflows/penta-context-ci.yml"],
                "production_evidence": {
                    "v1_base_receipt_sha256": "1e47ec8fd0a190a663c0c6b1cf17490d87c798e3281022dc2d2553e2f090a01e",
                    "v1_1_automation_receipt_sha256": "b05577014efc06fa2f07f7ea9c175e14b5d43f2b45b3c61cd464a2cad2579dd5",
                    "edge_v2_artifact_sha256": "4b8902e1d639e9a80d3e9f028cac2bb26662658ff5a547af210514f76fc3d212",
                },
            }
        ],
    }
    write_json(catalog_path, catalog)

    family_path = ROOT / "data/penta/family.registry.json"
    family = load_json(family_path)
    catalogs = family.get("catalogs")
    if not isinstance(catalogs, list):
        raise IntegrationError("family catalogs must be a list")
    context_ref = {
        "catalog_id": "penta.context",
        "path": "data/penta/systems.extensions.context.json",
        "required": True,
        "role": "production_scoped_context_and_operational_memory_extension",
    }
    found = [item for item in catalogs if isinstance(item, dict) and item.get("catalog_id") == "penta.context"]
    if len(found) > 1:
        raise IntegrationError("duplicate penta.context catalog references")
    if found:
        found[0].clear(); found[0].update(context_ref)
    else:
        catalogs.append(context_ref)
    family["updated"] = "2026-08-27"
    write_json(family_path, family)

    families_path = ROOT / "penta/registry/penta-families.v1.json"
    families = load_json(families_path)
    family_rows = families.get("families")
    if not isinstance(family_rows, list):
        raise IntegrationError("Penta Families registry missing families")
    knowledge = next((row for row in family_rows if isinstance(row, dict) and row.get("family_id") == "knowledge-semantics-data"), None)
    if not isinstance(knowledge, dict):
        raise IntegrationError("knowledge-semantics-data family missing")
    explicit = knowledge.get("explicit_members")
    if not isinstance(explicit, list):
        raise IntegrationError("knowledge family explicit_members must be list")
    if "PentaContext" not in explicit:
        explicit.append("PentaContext")
    explicit[:] = sorted(set(str(item) for item in explicit))
    write_json(families_path, families)


def add_promotion_support() -> None:
    copy_archived("data/penta/production-promotions.v1.json")
    path = ROOT / "runtime/penta_family.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "guard. A production family never promotes a child system automatically: each\nmember retains its own maturity and may execute only when its own state and\nauthority gates permit it.",
        "guard. A production family never promotes a child automatically. A child may\nadvance only through an explicit evidence-bound promotion record whose prior\nmaturity, authority reference, evidence paths, runtime paths, and PASS state are\nvalidated. Provider, legal, economic, security, licensing, governance, fiduciary,\nand D3 authority remain independent and fail closed.",
    )
    if "PROMOTION_PATH =" not in text:
        marker = 'EXECUTION_ELIGIBLE = {"certified", "production"}\n'
        if marker not in text:
            raise IntegrationError("penta_family execution eligibility marker missing")
        text = text.replace(marker, marker + 'PROMOTION_PATH = Path("data/penta/production-promotions.v1.json")\n', 1)

    helper = r'''

def _safe_repo_ref(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and not value.startswith(("/", "..")) and "\\" not in value


def _apply_promotions(root: Path, members: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    path = root / PROMOTION_PATH
    if not path.exists():
        return {}
    manifest = _load_json(path)
    if manifest.get("schema") != "ct.penta.production-promotions.v1" or manifest.get("version") != "1.0.0" or manifest.get("fail_closed") is not True:
        raise PentaFamilyError("invalid production promotion manifest contract")
    promotions = manifest.get("promotions")
    if not isinstance(promotions, list):
        raise PentaFamilyError("production promotions must be a list")
    applied: Dict[str, Dict[str, Any]] = {}
    seen: set[str] = set()
    for item in promotions:
        if not isinstance(item, dict):
            raise PentaFamilyError("promotion entry must be an object")
        required = {"machine_key", "from_maturity", "to_maturity", "effective_at", "authority_ref", "evidence_status", "evidence_refs", "runtime_refs", "scope"}
        missing = required - set(item)
        if missing:
            raise PentaFamilyError("promotion missing fields: " + ", ".join(sorted(missing)))
        key = item["machine_key"]
        if not isinstance(key, str) or not key.startswith("penta.") or key not in members:
            raise PentaFamilyError(f"promotion targets unknown member: {key!r}")
        if key in seen:
            raise PentaFamilyError(f"duplicate promotion for {key}")
        seen.add(key)
        current = members[key].get("maturity")
        if item["from_maturity"] != current:
            raise PentaFamilyError(f"promotion prior maturity mismatch for {key}: expected {current!r}")
        if item["to_maturity"] not in EXECUTION_ELIGIBLE:
            raise PentaFamilyError(f"promotion target maturity must be certified/production for {key}")
        if item["evidence_status"] != "PASS":
            raise PentaFamilyError(f"promotion evidence is not PASS for {key}")
        if not isinstance(item["authority_ref"], str) or not item["authority_ref"].strip():
            raise PentaFamilyError(f"promotion authority_ref missing for {key}")
        if not isinstance(item["scope"], str) or not item["scope"].strip():
            raise PentaFamilyError(f"promotion scope missing for {key}")
        evidence_refs, runtime_refs = item["evidence_refs"], item["runtime_refs"]
        if not isinstance(evidence_refs, list) or not evidence_refs or not all(_safe_repo_ref(value) for value in evidence_refs):
            raise PentaFamilyError(f"invalid promotion evidence refs for {key}")
        if not isinstance(runtime_refs, list) or not runtime_refs or not all(_safe_repo_ref(value) for value in runtime_refs):
            raise PentaFamilyError(f"invalid promotion runtime refs for {key}")
        absent = [ref for ref in [*evidence_refs, *runtime_refs] if not (root / ref).exists()]
        if absent:
            raise PentaFamilyError(f"promotion evidence/runtime missing for {key}: {', '.join(absent)}")
        members[key]["maturity"] = item["to_maturity"]
        applied[key] = {
            "from_maturity": current,
            "to_maturity": item["to_maturity"],
            "effective_at": item["effective_at"],
            "authority_ref": item["authority_ref"],
            "evidence_refs": list(evidence_refs),
            "runtime_refs": list(runtime_refs),
            "scope": item["scope"],
            "promotion_manifest": str(PROMOTION_PATH),
        }
    return applied
'''
    if "def _apply_promotions" not in text:
        marker = "\ndef _resolve_control_planes(\n"
        if marker not in text:
            raise IntegrationError("penta_family control-plane marker missing")
        text = text.replace(marker, helper + marker, 1)

    marker = '    if not members:\n        raise PentaFamilyError("family has no registered members")\n\n'
    if "promotions = _apply_promotions" not in text:
        if marker not in text:
            raise IntegrationError("penta_family member composition marker missing")
        text = text.replace(marker, marker + "    promotions = _apply_promotions(root, members)\n\n", 1)

    if 'member_snapshot[key]["maturity_promotion"]' not in text:
        lines = text.splitlines()
        output: list[str] = []
        inside_member = False
        inserted = False
        for line in lines:
            output.append(line)
            if line == "        member_snapshot[key] = {":
                inside_member = True
                continue
            if inside_member and line == "        }":
                output.append("        if key in promotions:")
                output.append('            member_snapshot[key]["maturity_promotion"] = promotions[key]')
                inside_member = False
                inserted = True
        if not inserted:
            raise IntegrationError("penta_family member promotion projection insertion failed")
        text = "\n".join(output) + "\n"

    return_marker = '        "held_members": held,\n'
    if '"promotion_count": len(promotions)' not in text:
        if return_marker not in text:
            raise IntegrationError("penta_family return marker missing")
        text = text.replace(
            return_marker,
            return_marker
            + '        "promotion_count": len(promotions),\n'
            + '        "promoted_members": sorted(promotions),\n'
            + '        "promotion_manifest": str(PROMOTION_PATH) if promotions else None,\n',
            1,
        )

    portal_marker = '"execution_eligible": maturity in EXECUTION_ELIGIBLE,'
    if portal_marker in text and '"maturity_promotion": member.get("maturity_promotion")' not in text:
        text = text.replace(portal_marker, portal_marker + ' "maturity_promotion": member.get("maturity_promotion"),', 1)
    path.write_text(text, encoding="utf-8")


def add_wave3_operations() -> None:
    module_path = ROOT / "runtime/penta_wave3_operations.py"
    module = git_show("runtime/penta_promoted_operations.py")
    if "def context_contract_probe" not in module:
        module += r'''


def context_contract_probe(ctx: Any) -> dict[str, Any]:
    required = [
        "runtime/penta_context.py",
        "tests/test_penta_context.py",
        ".github/workflows/penta-context-ci.yml",
        "PENTACONTEXT.md",
        "data/penta/systems.extensions.context.json",
    ]
    missing = [ref for ref in required if not (ctx.root / ref).is_file()]
    member = (ctx.snapshot.get("members") or {}).get("penta.context") or {}
    evidence = _json(ctx.root / "data/penta/systems.extensions.context.json")
    return {
        "schema": "ct.penta.context.contract-probe.v1",
        "state": "PRODUCTION_CONTRACT_PRESENT" if not missing and member.get("maturity") == "production" else "HOLD",
        "effective_maturity": member.get("maturity"),
        "required_refs": required,
        "missing_refs": missing,
        "production_evidence": ((evidence.get("systems") or [{}])[0]).get("production_evidence"),
        "network_probe_performed": False,
        "provider_write_performed": False,
        "secret_values_returned": False,
        "state_persisted": False,
        "authority_expanded": False,
    }
'''
    module_path.write_text(module, encoding="utf-8")

    path = ROOT / "runtime/penta_exec.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace('RUNTIME_VERSION = "1.3.0"', f'RUNTIME_VERSION = "{RUNTIME_VERSION}"')
    text = text.replace(
        'if registry.get("version") != "1.3.0" or registry.get("fail_closed") is not True:',
        'if registry.get("version") != "1.4.0" or registry.get("fail_closed") is not True:',
    ).replace(
        'raise PentaExecutionError("adapter registry must be v1.3.0 and fail closed")',
        'raise PentaExecutionError("adapter registry must be v1.4.0 and fail closed")',
    )
    text = text.replace(
        '"source": member.get("source")})',
        '"source": member.get("source"), "maturity_promotion": member.get("maturity_promotion")})',
        1,
    )

    wrapper = r'''

def _wave3_operation(name: str, ctx: AdapterContext) -> dict[str, Any]:
    from runtime import penta_wave3_operations as operations
    try:
        return getattr(operations, name)(ctx)
    except Exception as exc:
        if exc.__class__.__name__ == "PromotedOperationError":
            raise PentaExecutionError(str(exc)) from exc
        raise


def _mail_production_status(ctx: AdapterContext) -> dict[str, Any]: return _wave3_operation("mail_production_status", ctx)
def _status_owner_snapshot(ctx: AdapterContext) -> dict[str, Any]: return _wave3_operation("status_owner_snapshot", ctx)
def _credentials_binding_census(ctx: AdapterContext) -> dict[str, Any]: return _wave3_operation("credentials_binding_census", ctx)
def _build_provider_adapter(ctx: AdapterContext) -> dict[str, Any]: return _wave3_operation("build_provider_adapter", ctx)
def _certify_provider_static(ctx: AdapterContext) -> dict[str, Any]: return _wave3_operation("certify_provider_static", ctx)
def _context_contract_probe(ctx: AdapterContext) -> dict[str, Any]: return _wave3_operation("context_contract_probe", ctx)
'''
    if "def _wave3_operation" not in text:
        marker = "\n\nBUILTIN_HANDLERS:"
        if marker not in text:
            raise IntegrationError("penta_exec builtin marker missing")
        text = text.replace(marker, wrapper + marker, 1)

    handler_marker = '    "evi_bundle_preview": _evi_bundle_preview, "immune_repair_plan_preview": _immune_repair_plan_preview,\n'
    if '"mail_production_status": _mail_production_status' not in text:
        if handler_marker not in text:
            raise IntegrationError("penta_exec handler insertion marker missing")
        text = text.replace(
            handler_marker,
            handler_marker
            + '    "mail_production_status": _mail_production_status, "status_owner_snapshot": _status_owner_snapshot,\n'
            + '    "credentials_binding_census": _credentials_binding_census, "build_provider_adapter": _build_provider_adapter,\n'
            + '    "certify_provider_static": _certify_provider_static, "context_contract_probe": _context_contract_probe,\n',
            1,
        )

    validate_marker = '"adapter_count": len(adapters["adapters"]), "execution_adapter_coverage": coverage,'
    if validate_marker in text and '"promotion_count": snapshot.get("promotion_count", 0)' not in text:
        text = text.replace(
            validate_marker,
            '"adapter_count": len(adapters["adapters"]), "promotion_count": snapshot.get("promotion_count", 0), "execution_adapter_coverage": coverage,',
            1,
        )
    path.write_text(text, encoding="utf-8")


def update_adapter_registry_and_contract() -> None:
    adapter_path = ROOT / "data/penta/execution-adapters.registry.json"
    registry = load_json(adapter_path)
    registry["version"] = RUNTIME_VERSION
    registry["provider_effect_policy"] = "Repository-local adapters perform no provider writes. PentaMail send and every other provider effect remain separately authorized, certified, credential-bound, readback-gated, and evidence-preserved."
    adapters = registry.get("adapters")
    if not isinstance(adapters, list):
        raise IntegrationError("adapter registry adapters must be list")
    additions = [
        {"adapter_id": "builtin.mail.production-status", "member": "penta.mail", "operation": "production_status", "handler": "mail_production_status", "requested_effect": "verify", "provider_effect": False, "requires_execution_eligible": True},
        {"adapter_id": "builtin.status.owner-snapshot", "member": "penta.status", "operation": "owner_snapshot", "handler": "status_owner_snapshot", "requested_effect": "verify", "provider_effect": False, "requires_execution_eligible": True},
        {"adapter_id": "builtin.credentials.binding-census", "member": "penta.credentials", "operation": "binding_census", "handler": "credentials_binding_census", "requested_effect": "verify", "provider_effect": False, "requires_execution_eligible": True},
        {"adapter_id": "builtin.build.provider-adapter", "member": "penta.build", "operation": "provider_adapter_probe", "handler": "build_provider_adapter", "requested_effect": "prepare", "provider_effect": False, "requires_execution_eligible": True},
        {"adapter_id": "builtin.certify.provider-static", "member": "penta.certify", "operation": "provider_static_probe", "handler": "certify_provider_static", "requested_effect": "verify", "provider_effect": False, "requires_execution_eligible": True},
        {"adapter_id": "builtin.context.contract-probe", "member": "penta.context", "operation": "contract_probe", "handler": "context_contract_probe", "requested_effect": "verify", "provider_effect": False, "requires_execution_eligible": True},
    ]
    by_id = {item.get("adapter_id"): item for item in adapters if isinstance(item, dict)}
    for addition in additions:
        existing = by_id.get(addition["adapter_id"])
        if existing:
            existing.clear(); existing.update(addition)
        else:
            adapters.append(addition)
    write_json(adapter_path, registry)

    contract_path = ROOT / "data/penta/member-runtime.contract.json"
    contract = load_json(contract_path)
    contract["schema_version"] = RUNTIME_VERSION
    contract["promotion_registry"] = "data/penta/production-promotions.v1.json"
    contract["ect_evidence"] = {
        "canonical_name": "Execution Certification and Testing",
        "evidence_path": "evidence/penta/penta-wave3-ect-20260827.json",
        "focused_certification_status": "PENDING_EXACT_MAINLINE_ECT",
        "fail_closed": True,
    }
    invariants = contract.get("invariants")
    if not isinstance(invariants, dict):
        raise IntegrationError("member runtime invariants missing")
    invariants.update({
        "evidence_bound_promotion_only": True,
        "promotion_prior_maturity_must_match": True,
        "promotion_evidence_and_runtime_paths_must_exist": True,
        "provider_effect_operations_remain_separately_certified": True,
        "exact_head_ect_required_before_merge": True,
    })
    operations = contract.get("production_member_adapters")
    if not isinstance(operations, list):
        raise IntegrationError("production_member_adapters missing")
    for operation in [
        "penta.mail:production_status",
        "penta.status:owner_snapshot",
        "penta.credentials:binding_census",
        "penta.build:provider_adapter_probe",
        "penta.certify:provider_static_probe",
        "penta.context:contract_probe",
    ]:
        if operation not in operations:
            operations.append(operation)
    contract["execution_boundary"] = (
        "PentaOS V1.5 adapters remain repository-local and provider-effect false. Explicit Wave 3 promotions recognize proven maturity but never create authority. PentaMail reports separately proven send/readback evidence without sending; PentaCredentials returns no secrets; PentaBuild uses temporary deterministic artifacts; PentaCertify disables network probes; PentaContext performs contract/readiness verification only; PentaEVIBuilder remains UNVERIFIED preview-only; PentaImmune remains plan-only."
    )
    write_json(contract_path, contract)


def update_runtime_suite() -> None:
    text = git_show("runtime/penta_runtime_suite.py")
    marker = '    for path in sorted(data.glob("*.json")):\n'
    if marker not in text:
        raise IntegrationError("archived Runtime Suite collection marker missing")
    if "os-v1.discoveries.json" not in text:
        text = text.replace(
            marker,
            marker + '        if path.name in {"os-v1.discoveries.json", "os-v1.registry.json"}:\n            continue\n',
            1,
        )
    text = text.replace(
        '"penta.nurture":[root/"runtime"/"penta-provider-control-plane"/"penta_control_plane.py"],',
        '"penta.nurture":[root/"runtime"/"penta-provider-control-plane"/"penta_control_plane.py"],\n        "penta.context":[root/"runtime"/"penta_context.py",root/"tests"/"test_penta_context.py"],',
        1,
    )
    (ROOT / "runtime/penta_runtime_suite.py").write_text(text, encoding="utf-8")


def patch_tests() -> None:
    exec_path = ROOT / "tests/test_penta_exec.py"
    text = exec_path.read_text(encoding="utf-8")
    text = text.replace("test_specified_member_has_real_status_without_fake_execution_promotion", "test_evidence_promoted_member_has_real_status")
    text = text.replace('assert result["details"]["maturity"] == "specified"', 'assert result["details"]["maturity"] == "production"', 1)
    text = text.replace('assert result["details"]["execution_gate"]["eligible"] is False', 'assert result["details"]["execution_gate"]["eligible"] is True', 1)
    status_anchor = 'assert result["details"]["portal_route"] == "/penta/mail"'
    if status_anchor in text and 'maturity_promotion' not in text.split(status_anchor, 1)[0][-300:]:
        text = text.replace(status_anchor, status_anchor + '\n    assert result["details"]["maturity_promotion"]["authority_ref"].startswith("PR-511/")', 1)
    text = text.replace('registry["version"] == "1.3.0"', 'registry["version"] == "1.4.0"')
    text = re.sub(r'len\(registry\["adapters"\]\) == \d+', 'len(registry["adapters"]) == 21', text, count=1)
    text = text.replace('result["details"]["adapter_count"] == 15', 'result["details"]["adapter_count"] == 21')
    text = text.replace('coverage["eligible_member_count"] == 15', 'coverage["eligible_member_count"] == 21')
    text = text.replace('coverage["eligible_members_with_adapter"] == 15', 'coverage["eligible_members_with_adapter"] == 21')
    text = text.replace('probe["production_member_count"] == 15', 'probe["production_member_count"] == 21')
    text = text.replace('route["maturity"] == "specified" and route["execution_eligible"] is False', 'route["maturity"] == "production" and route["execution_eligible"] is True')

    added = r'''

def test_wave3_promoted_operations_and_context_are_bounded() -> None:
    mail = invoke_member(ROOT, source_member="penta.status", target_member="penta.mail", operation="production_status", evidence_refs=["test:ect:mail"], risk_class="D0")
    assert mail["disposition"] == "completed"
    assert mail["details"]["result"]["state"] == "PRODUCTION_VERIFIED"
    assert mail["details"]["result"]["provider_write_performed_by_this_adapter"] is False

    owner = invoke_member(ROOT, source_member="penta.status", target_member="penta.status", operation="owner_snapshot", evidence_refs=["test:ect:status"], risk_class="D0")
    assert owner["disposition"] == "completed"
    assert owner["details"]["result"]["production_adapter_coverage_complete"] is True
    assert owner["details"]["result"]["promotion_count"] == 5

    credentials = invoke_member(ROOT, source_member="penta.status", target_member="penta.credentials", operation="binding_census", evidence_refs=["test:ect:credentials"], risk_class="D0")
    assert credentials["details"]["result"]["secret_values_returned"] is False
    assert credentials["details"]["result"]["state_persisted"] is False

    build = invoke_member(ROOT, source_member="penta.status", target_member="penta.build", operation="provider_adapter_probe", evidence_refs=["test:ect:build"], payload={"provider_id": "resend"}, risk_class="D0")
    assert build["details"]["result"]["build"]["provider_write_performed"] is False
    assert build["details"]["result"]["build"]["state_persisted"] is False

    certify = invoke_member(ROOT, source_member="penta.status", target_member="penta.certify", operation="provider_static_probe", evidence_refs=["test:ect:certify"], payload={"provider_id": "resend"}, risk_class="D0")
    assert certify["details"]["result"]["runtime_probe"]["network_probe_performed"] is False
    assert certify["details"]["result"]["runtime_probe"]["provider_write_performed"] is False

    context = invoke_member(ROOT, source_member="penta.status", target_member="penta.context", operation="contract_probe", evidence_refs=["test:ect:context"], risk_class="D0")
    assert context["disposition"] == "completed"
    assert context["details"]["result"]["state"] == "PRODUCTION_CONTRACT_PRESENT"
    assert context["details"]["result"]["missing_refs"] == []
    assert context["details"]["result"]["secret_values_returned"] is False


def test_pentamail_send_still_has_no_local_provider_adapter() -> None:
    result = invoke_member(ROOT, source_member="penta.status", target_member="penta.mail", operation="send", evidence_refs=["test:ect:no-local-send"], risk_class="D1")
    assert result["disposition"] == "hold_fail_closed"
    assert "no registered executable adapter" in result["details"]["reason"]
'''
    if "test_wave3_promoted_operations_and_context_are_bounded" not in text:
        marker = "\ndef run() -> None:\n"
        if marker not in text:
            raise IntegrationError("test_penta_exec run marker missing")
        text = text.replace(marker, added + marker, 1)
    exec_path.write_text(text, encoding="utf-8")

    family_path = ROOT / "tests/test_penta_family.py"
    family_text = family_path.read_text(encoding="utf-8")
    family_text = family_text.replace('assert control["eligible"] is False', 'assert control["eligible"] is False')
    promotion_test = r'''

def test_exact_evidence_promotions_apply_without_automatic_authority() -> None:
    _, snapshot = load_family(ROOT)
    assert snapshot["promotion_count"] == 5
    assert set(snapshot["promoted_members"]) == {"penta.mail", "penta.status", "penta.credentials", "penta.build", "penta.certify"}
    for key in snapshot["promoted_members"]:
        member = snapshot["members"][key]
        assert member["maturity"] == "production"
        assert member["maturity_promotion"]["from_maturity"] == "specified"
        assert member["maturity_promotion"]["authority_ref"]
        assert member_dispatch_gate(snapshot, key)["eligible"] is True
    assert snapshot["members"]["penta.context"]["maturity"] == "production"
    assert snapshot["members"]["penta.context"].get("maturity_promotion") is None
'''
    if "test_exact_evidence_promotions_apply_without_automatic_authority" not in family_text:
        marker = "\ndef run() -> None:\n"
        if marker not in family_text:
            raise IntegrationError("test_penta_family run marker missing")
        family_text = family_text.replace(marker, promotion_test + marker, 1)
    family_path.write_text(family_text, encoding="utf-8")

    runtime_test_path = ROOT / "tests/test_penta_runtime_suite.py"
    runtime_tests = git_show("tests/test_penta_runtime_suite.py")
    extra = r'''

    def test_generated_os_v1_census_is_not_a_second_source(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = root / "data" / "penta"
            data.mkdir(parents=True)
            payload = {"systems": [{"machine_key": "penta.mail", "canonical_name": "PentaMail", "maturity": "specified"}]}
            (data / "systems.registry.json").write_text(json.dumps(payload), encoding="utf-8")
            (data / "os-v1.registry.json").write_text(json.dumps(payload), encoding="utf-8")
            members = prs.collect_members(root)
            self.assertEqual(set(members), {"penta.mail"})
'''
    if "test_generated_os_v1_census_is_not_a_second_source" not in runtime_tests:
        runtime_tests = runtime_tests.replace("\n\nif __name__ == \"__main__\":", extra + "\n\nif __name__ == \"__main__\":")
    runtime_test_path.write_text(runtime_tests, encoding="utf-8")


def write_ect_candidate() -> None:
    ect = {
        "schema": "ct.penta.ect.v1",
        "ect_id": "ct.penta.ect.production-promotion-wave3.20260827",
        "canonical_name": "Execution Certification and Testing",
        "repository": "crownthrive1/CrownThrive-OS",
        "pull_request": 552,
        "base_main_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "status": "INTEGRATED_PENDING_EXACT_HEAD_ECT",
        "required_scope": {
            "evidence_promotions": PROMOTION_TARGETS,
            "context_member": "penta.context",
            "provider_effect_adapters": 0,
            "authority_expanded": False,
            "d3_automatic_authority": False,
        },
    }
    write_json(ROOT / "evidence/penta/penta-wave3-ect-20260827.json", ect)


def ensure_gitignore() -> None:
    path = ROOT / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    additions = "\n# Python generated artifacts\n__pycache__/\n*.py[cod]\n.pytest_cache/\n.mypy_cache/\n.ruff_cache/\n"
    if "__pycache__/" not in existing:
        path.write_text(existing.rstrip() + additions, encoding="utf-8")


def validate_static_state() -> dict[str, Any]:
    family = load_json(ROOT / "data/penta/family.registry.json")
    catalogs = family.get("catalogs") or []
    required_paths = {"data/penta/systems.extensions.context.json", "data/penta/systems.extensions.penta-immune.json"}
    paths = {item.get("path") for item in catalogs if isinstance(item, dict)}
    if not required_paths.issubset(paths):
        raise IntegrationError("required context/immune family catalogs missing")
    registry = load_json(ROOT / "data/penta/execution-adapters.registry.json")
    adapters = registry.get("adapters") or []
    if registry.get("version") != RUNTIME_VERSION or len(adapters) != 21:
        raise IntegrationError(f"adapter contract drift: version={registry.get('version')} count={len(adapters)}")
    if any(item.get("provider_effect") is not False for item in adapters if isinstance(item, dict)):
        raise IntegrationError("local provider-effect adapter detected")
    manifest = load_json(ROOT / "data/penta/production-promotions.v1.json")
    if len(manifest.get("promotions") or []) != 5:
        raise IntegrationError("exact five Wave 3 promotions required")
    return {"adapter_count": len(adapters), "promotion_count": 5, "provider_effect_adapters": 0}


def main() -> int:
    ensure_gitignore()
    add_context_catalog()
    add_promotion_support()
    add_wave3_operations()
    update_adapter_registry_and_contract()
    update_runtime_suite()
    patch_tests()
    write_ect_candidate()
    state = validate_static_state()
    print(json.dumps({"ok": True, **state}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
