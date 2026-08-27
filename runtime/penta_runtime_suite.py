#!/usr/bin/env python3
"""Penta Runtime Suite: repository-native control-plane inventory and truth report.

This is deliberately NOT PentaSuite (the agent laboratory). It is a shared
runtime/audit facade that composes Penta Family state, provider readiness and
repository implementation signals. It projects only separately governed,
exact-evidence-bound maturity promotions; provider state remains independent.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from runtime.penta_promotions import PentaPromotionError, apply_promotions
except ModuleNotFoundError:
    runtime_dir = str(Path(__file__).resolve().parent)
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)
    from penta_promotions import PentaPromotionError, apply_promotions


class PentaRuntimeSuiteError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PentaRuntimeSuiteError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaRuntimeSuiteError(f"JSON root must be object: {path}")
    return value


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PentaRuntimeSuiteError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _token(machine_key: str) -> str:
    return machine_key.split(".", 1)[1].replace(".", "-")


def collect_members(root: Path) -> dict[str, dict[str, Any]]:
    data = root / "data" / "penta"
    members: dict[str, dict[str, Any]] = {}
    for path in sorted(data.glob("*.json")):
        # These files are derived whole-system censuses; ingesting them again
        # would duplicate the original registry members and blur provenance.
        if path.name in {"os-v1.discoveries.json", "os-v1.registry.json"}:
            continue
        raw = _load_json(path)
        systems = raw.get("systems")
        if not isinstance(systems, list):
            continue
        for item in systems:
            if not isinstance(item, dict) or not isinstance(item.get("machine_key"), str):
                continue
            key = item["machine_key"]
            if not key.startswith("penta."):
                continue
            if key in members:
                raise PentaRuntimeSuiteError(f"duplicate machine_key: {key}")
            members[key] = {**item, "source": str(path.relative_to(root))}
    if not members:
        raise PentaRuntimeSuiteError("no Penta members discovered")
    return members


def implementation_signals(root: Path, machine_key: str) -> list[str]:
    token = _token(machine_key)
    compact = re.sub(r"[^a-z0-9]", "", token.casefold())
    candidates: list[Path] = []
    scan_roots = [
        root / "runtime",
        root / "penta" / "runtime",
        root / "scripts",
        root / "tests",
        root / ".github" / "workflows",
    ]
    for base in scan_roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            normalized = re.sub(r"[^a-z0-9]", "", path.name.casefold())
            if compact and compact in normalized:
                candidates.append(path)
    special = {
        "penta.mail": [
            root / "runtime" / "penta_mail.py",
            root / "tests" / "test_penta_mail.py",
            root / ".github" / "workflows" / "penta-mail-live-certification.yml",
        ],
        "penta.status": [root / "runtime" / "penta_mail.py"],
        "penta.credentials": [root / "runtime" / "penta-provider-control-plane" / "penta_control_plane.py"],
        "penta.build": [root / "runtime" / "penta-provider-control-plane" / "penta_control_plane.py"],
        "penta.certify": [root / "runtime" / "penta-provider-control-plane" / "penta_control_plane.py"],
        "penta.nurture": [root / "runtime" / "penta-provider-control-plane" / "penta_control_plane.py"],
    }
    candidates.extend(special.get(machine_key, []))
    return sorted({str(path.relative_to(root)) for path in candidates if path.exists()})


def provider_control_snapshot(root: Path) -> dict[str, Any]:
    module_path = root / "runtime" / "penta-provider-control-plane" / "penta_control_plane.py"
    registry_path = root / "runtime" / "penta-provider-control-plane" / "providers.json"
    if not module_path.exists() or not registry_path.exists():
        return {"available": False, "errors": ["provider control plane missing"]}
    mod = _load_module("penta_provider_control_plane_runtime_suite", module_path)
    registry = mod.Registry(registry_path)
    errors = mod.validate_registry(registry)
    providers = []
    for provider_id, provider in sorted(registry.providers.items()):
        providers.append({
            "provider_id": provider_id,
            "operations": [op["operation"] for op in provider.get("adapter", {}).get("operations", [])],
            "priority": provider.get("priority"),
        })
    return {
        "available": True,
        "registry_schema": registry.raw.get("schema"),
        "registry_version": registry.raw.get("version"),
        "provider_count": len(providers),
        "providers": providers,
        "contract_errors": errors,
        "network_probe_mode": "disabled_for_static_audit",
    }


def build_snapshot(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    try:
        members, promotions = apply_promotions(root, collect_members(root))
    except PentaPromotionError as exc:
        raise PentaRuntimeSuiteError(f"invalid evidence-bound maturity promotion: {exc}") from exc
    rows: list[dict[str, Any]] = []
    maturity_counts: dict[str, int] = {}
    with_signals = 0
    for key in sorted(members):
        member = members[key]
        maturity = member.get("maturity", "unknown")
        maturity_counts[maturity] = maturity_counts.get(maturity, 0) + 1
        signals = implementation_signals(root, key)
        if signals:
            with_signals += 1
        rows.append({
            "machine_key": key,
            "canonical_name": member.get("canonical_name"),
            "catalog_maturity": member.get("catalog_maturity", maturity),
            "maturity": maturity,
            "maturity_promotion": member.get("maturity_promotion"),
            "risk_ceiling": member.get("risk_ceiling"),
            "source": member["source"],
            "implementation_signals": signals,
            "signal_count": len(signals),
            "execution_eligible_by_registry": maturity in {"certified", "production"},
        })
    provider = provider_control_snapshot(root)
    mail = next((row for row in rows if row["machine_key"] == "penta.mail"), None)
    return {
        "schema": "ct.penta.runtime-suite.snapshot.v1",
        "truth_rule": "implementation signals are evidence locations, not maturity promotion; only exact-evidence-bound promotion records may change effective system maturity, and they never change provider state",
        "member_count": len(rows),
        "maturity_counts": dict(sorted(maturity_counts.items())),
        "members_with_implementation_signals": with_signals,
        "promotion_count": len(promotions),
        "promoted_members": sorted(promotions),
        "provider_states_promoted": False,
        "members": rows,
        "provider_control_plane": provider,
        "pentamail": {
            "registered": mail is not None,
            "catalog_maturity": mail.get("catalog_maturity") if mail else None,
            "effective_maturity": mail.get("maturity") if mail else None,
            "provider_state": "SEPARATELY_GATED_NOT_PROMOTED_BY_RUNTIME_SUITE",
            "implementation_signals": mail.get("implementation_signals") if mail else [],
            "resend_registered": any(p["provider_id"] == "resend" for p in provider.get("providers", [])),
            "mailgun_registered": any(p["provider_id"] == "mailgun" for p in provider.get("providers", [])),
        },
    }


def gate_member(snapshot: dict[str, Any], machine_key: str) -> dict[str, Any]:
    row = next((item for item in snapshot.get("members", []) if item.get("machine_key") == machine_key), None)
    if row is None:
        return {"machine_key": machine_key, "eligible": False, "disposition": "hold_fail_closed", "reason": "unregistered member"}
    if not row.get("execution_eligible_by_registry"):
        return {
            "machine_key": machine_key,
            "eligible": False,
            "disposition": "hold_fail_closed",
            "reason": f"registry maturity {row.get('maturity')!r} is not execution-eligible",
        }
    if not row.get("implementation_signals"):
        return {
            "machine_key": machine_key,
            "eligible": False,
            "disposition": "hold_fail_closed",
            "reason": "no repository implementation signal",
        }
    return {
        "machine_key": machine_key,
        "eligible": True,
        "disposition": "member_registry_and_implementation_gate_passed",
        "reason": "downstream authority/provider/readback gates still apply",
    }


def owner_summary(snapshot: dict[str, Any]) -> str:
    mail = snapshot["pentamail"]
    provider = snapshot["provider_control_plane"]
    lines = [
        "Penta Runtime Suite truth snapshot",
        f"Registered Penta members: {snapshot['member_count']}",
        f"Members with repository implementation signals: {snapshot['members_with_implementation_signals']}",
        f"Maturity counts: {json.dumps(snapshot['maturity_counts'], sort_keys=True)}",
        f"Evidence-bound maturity promotions: {snapshot['promotion_count']}",
        f"Provider control plane present: {provider.get('available')}",
        f"Provider count: {provider.get('provider_count', 0)}",
        f"PentaMail registered: {mail['registered']}",
        f"PentaMail catalog/effective maturity: {mail['catalog_maturity']}/{mail['effective_maturity']}",
        f"PentaMail provider state: {mail['provider_state']}",
        f"PentaMail implementation signals: {len(mail['implementation_signals'])}",
        f"Resend registered: {mail['resend_registered']}",
        f"Mailgun registered: {mail['mailgun_registered']}",
    ]
    if provider.get("contract_errors"):
        lines.append("Provider contract errors: " + "; ".join(provider["contract_errors"]))
    return "\n".join(lines)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Penta Runtime Suite truth/audit control plane")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--gate")
    args = parser.parse_args()
    snapshot = build_snapshot(Path(args.root))
    result: Any = gate_member(snapshot, args.gate) if args.gate else snapshot
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
