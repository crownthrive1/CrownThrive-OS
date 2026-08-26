from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .engine import PentaResilienceLoop, plan_json, report_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="penta-resilience")
    sub = parser.add_subparsers(dest="command", required=True)

    drill = sub.add_parser("drill", help="Run a sandbox-only PentaRed/PentaBlue drill against an ephemeral clone")
    drill.add_argument("source", type=Path)
    drill.add_argument("--scenario", action="append", dest="scenarios")

    plan = sub.add_parser("plan", help="Run the safe drill and emit a PentaLiency hardening plan")
    plan.add_argument("source", type=Path)
    plan.add_argument("--scenario", action="append", dest="scenarios")

    harden = sub.add_parser("harden", help="Apply generated policy controls with snapshot/rollback protection")
    harden.add_argument("source", type=Path)
    harden.add_argument("--approved-change-id", required=True)
    harden.add_argument("--scenario", action="append", dest="scenarios")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    loop = PentaResilienceLoop()
    report, plan = loop.drill_and_plan(args.source, args.scenarios)
    if args.command == "drill":
        print(report_json(report))
        return 0
    if args.command == "plan":
        print(plan_json(plan))
        return 0
    result = loop.liency.apply(plan, args.source, approved_change_id=args.approved_change_id)
    print(json.dumps({"report": asdict(report), "plan": asdict(plan), "apply": result}, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
