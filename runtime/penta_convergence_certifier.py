#!/usr/bin/env python3
"""Family-wide PENTA convergence certification.

This runtime invokes every registered Penta identity visible across the canonical
Penta Family and repository runtime/observability registries, records evidence,
and produces one hash-bound certification manifest. It never promotes member
maturity and never manufactures provider, governance, legal, economic, security,
or human authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


class PentaConvergenceError(ValueError):
    pass


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PentaConvergenceError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def certify(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    family_mod = _load_module("penta_family_convergence", root / "runtime" / "penta_family.py")
    runtime_mod = _load_module("penta_runtime_suite_convergence", root / "runtime" / "penta_runtime_suite.py")
    obs_mod = _load_module("penta_observability_convergence", root / "runtime" / "penta_observability.py")
    compliance_license_mod = _load_module(
        "penta_compliance_license_convergence", root / "runtime" / "penta_compliance_license.py"
    )
    self_build_mod = _load_module("penta_self_build_convergence", root / "runtime" / "penta_self_build.py")

    family_registry, family_snapshot = family_mod.load_family(root)
    runtime_snapshot = runtime_mod.build_snapshot(root)
    compliance_license_self_test = compliance_license_mod.self_test()
    self_build_coverage = self_build_mod.coverage_report(root)

    family_members = family_snapshot.get("members", {})
    if not isinstance(family_members, dict) or not family_members:
        raise PentaConvergenceError("Penta Family returned no registered members")

    runtime_rows = {
        row["machine_key"]: row
        for row in runtime_snapshot.get("members", [])
        if isinstance(row, dict) and isinstance(row.get("machine_key"), str)
    }
    if not runtime_rows:
        raise PentaConvergenceError("Penta runtime suite returned no registered members")

    missing_runtime = sorted(set(family_members) - set(runtime_rows))
    if missing_runtime:
        raise PentaConvergenceError(
            "family members missing from runtime census: " + ", ".join(missing_runtime)
        )

    runtime_extensions = sorted(set(runtime_rows) - set(family_members))
    registered_universe = sorted(set(family_members) | set(runtime_rows))

    log_lines: list[str] = []
    logger = obs_mod.PentaLogger(
        service="penta-convergence-certifier",
        penta_member="penta.certify",
        sink=log_lines.append,
    )
    metrics = obs_mod.MetricRegistry()

    invocations: list[dict[str, Any]] = []
    with obs_mod.bind_trace() as trace:
        for machine_key in registered_universe:
            runtime_row = runtime_rows[machine_key]
            runtime_gate = runtime_mod.gate_member(runtime_snapshot, machine_key)
            if machine_key in family_members:
                family_gate = family_mod.member_dispatch_gate(family_snapshot, machine_key)
                effective_eligible = bool(family_gate.get("eligible") and runtime_gate.get("eligible"))
                registry_scope = "family_and_runtime"
                canonical_name = family_members[machine_key].get("canonical_name")
                maturity = family_members[machine_key].get("maturity")
            else:
                # The observability spine is registered by the runtime catalog and
                # deliberately sits outside the family child-member map. Evaluate
                # its runtime gate without synthesizing a family child registration.
                family_gate = {
                    "eligible": None,
                    "disposition": "not_a_family_child",
                    "reason": "registered runtime/observability spine member outside family child-member map",
                }
                effective_eligible = bool(runtime_gate.get("eligible"))
                registry_scope = "runtime_spine_extension"
                canonical_name = runtime_row.get("canonical_name")
                maturity = runtime_row.get("maturity")

            disposition = "eligible_for_downstream_gates" if effective_eligible else "hold_preserved"
            record = {
                "machine_key": machine_key,
                "canonical_name": canonical_name,
                "maturity": maturity,
                "registry_scope": registry_scope,
                "family_gate": family_gate,
                "runtime_gate": runtime_gate,
                "effective_execution_eligible": effective_eligible,
                "disposition": disposition,
            }
            invocations.append(record)
            metrics.increment("penta.convergence.members_invoked")
            metrics.increment(
                "penta.convergence.members_eligible" if effective_eligible
                else "penta.convergence.members_held"
            )
            if registry_scope == "runtime_spine_extension":
                metrics.increment("penta.convergence.runtime_spine_extensions")
            logger.info(
                "Penta member evaluated",
                event="penta.convergence.member_evaluated",
                context={
                    "machine_key": machine_key,
                    "maturity": maturity,
                    "registry_scope": registry_scope,
                    "disposition": disposition,
                },
            )

        provider = runtime_snapshot.get("provider_control_plane", {})
        critical_checks = {
            "family_status_production": family_snapshot.get("family_status") == "production",
            "family_fail_closed": family_snapshot.get("fail_closed") is True,
            "all_family_members_present_in_runtime": not missing_runtime,
            "full_registered_universe_invoked": len(invocations) == len(registered_universe),
            "runtime_extension_inventory_explicit": all(
                item["registry_scope"] == "runtime_spine_extension"
                for item in invocations
                if item["machine_key"] in runtime_extensions
            ),
            "provider_control_plane_present": provider.get("available") is True,
            "provider_contract_clean": not provider.get("contract_errors"),
            "pentamail_registered": runtime_snapshot.get("pentamail", {}).get("registered") is True,
            "resend_registered": runtime_snapshot.get("pentamail", {}).get("resend_registered") is True,
            "penta_compliance_registered_production": family_members.get("penta.compliance", {}).get("maturity") == "production",
            "penta_license_registered_production": family_members.get("penta.license", {}).get("maturity") == "production",
            "compliance_license_runtime_self_test": compliance_license_self_test.get("ok") is True,
            "self_build_all_members_covered": self_build_coverage.get("disposition") == "PASS" and self_build_coverage.get("member_count") == self_build_coverage.get("covered_member_count"),
        }
        passed = all(critical_checks.values())
        metrics.gauge("penta.convergence.family_pass", 1.0 if passed else 0.0)

        evidence = {
            "schema": "ct.penta.convergence-certification.v1",
            "disposition": "PASS" if passed else "HOLD_FAIL_CLOSED",
            "truth_rule": "all registered Pentas across family and runtime spine are evaluated; held maturity is preserved and registry scope is never synthesized",
            "family": {
                "registry_id": family_registry.get("registry_id"),
                "status": family_snapshot.get("family_status"),
                "fail_closed": family_snapshot.get("fail_closed"),
                "family_child_count": family_snapshot.get("member_count"),
                "runtime_registered_count": len(runtime_rows),
                "runtime_extension_count": len(runtime_extensions),
                "runtime_extensions": runtime_extensions,
                "member_count": len(registered_universe),
                "invocation_count": len(invocations),
                "eligible_count": sum(1 for item in invocations if item["effective_execution_eligible"]),
                "held_count": sum(1 for item in invocations if not item["effective_execution_eligible"]),
                "maturity_counts": runtime_snapshot.get("maturity_counts", {}),
            },
            "critical_checks": critical_checks,
            "control_plane_resolution": family_snapshot.get("control_plane_resolution", {}),
            "provider_control_plane": provider,
            "pentamail": runtime_snapshot.get("pentamail", {}),
            "penta_compliance_license": compliance_license_self_test,
            "penta_self_build": self_build_coverage,
            "invocations": invocations,
            "observability": {
                "trace": trace.as_dict(),
                "metrics": metrics.snapshot(),
                "log_event_count": len(log_lines),
                "logs_sha256": hashlib.sha256("\n".join(log_lines).encode("utf-8")).hexdigest(),
            },
        }
        evidence["evidence_sha256"] = _digest(evidence)
        return evidence


def owner_summary(evidence: dict[str, Any]) -> str:
    family = evidence["family"]
    checks = evidence["critical_checks"]
    failed = [name for name, ok in checks.items() if not ok]
    lines = [
        "Penta Family + runtime-spine convergence certification",
        f"Disposition: {evidence['disposition']}",
        f"Registered/invoked Pentas: {family['member_count']}/{family['invocation_count']}",
        f"Family child members: {family['family_child_count']}",
        f"Runtime/observability spine extensions: {family['runtime_extension_count']}",
        f"Execution-eligible after applicable gates: {family['eligible_count']}",
        f"Held without promotion: {family['held_count']}",
        f"Critical checks: {sum(1 for ok in checks.values() if ok)}/{len(checks)} PASS",
        f"Evidence SHA-256: {evidence['evidence_sha256']}",
    ]
    if failed:
        lines.append("Failed checks: " + ", ".join(failed))
    lines.append("All maturity, authority, provider, and human gates remain independently fail-closed.")
    return "\n".join(lines)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Invoke and certify every registered Penta identity")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="penta-convergence-certification.json")
    parser.add_argument("--summary-output", default="penta-convergence-summary.txt")
    args = parser.parse_args()

    evidence = certify(Path(args.root))
    Path(args.output).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = owner_summary(evidence)
    Path(args.summary_output).write_text(summary + "\n", encoding="utf-8")
    print(summary)
    if evidence["disposition"] != "PASS":
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
