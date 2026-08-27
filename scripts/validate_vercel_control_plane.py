#!/usr/bin/env python3
"""Validate the CrownThrive OS Control Plane Vercel source contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "ct.penta.vercel.source-validation.20260827.v1"


def validate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    app = root / "apps/crownthrive-os-control-plane"
    required = [
        app / "index.html",
        app / "app.js",
        app / "styles.css",
        app / "api/health.js",
        app / "vercel.json",
        root / "config/vercel_control_plane.json",
    ]
    findings: list[dict[str, str]] = []
    for path in required:
        if not path.exists():
            findings.append({"code": "missing_file", "path": path.relative_to(root).as_posix()})

    if not findings:
        html = (app / "index.html").read_text(encoding="utf-8")
        js = (app / "app.js").read_text(encoding="utf-8")
        health = (app / "api/health.js").read_text(encoding="utf-8")
        config = json.loads((app / "vercel.json").read_text(encoding="utf-8"))
        binding = json.loads((root / "config/vercel_control_plane.json").read_text(encoding="utf-8"))
        checks = {
            "html_has_main": '<main id="main"' in html,
            "html_has_skip_link": "skip-link" in html,
            "app_uses_same_origin_health": "fetch('/api/health'" in js,
            "health_disclaims_manufactured_pass": "pass_manufactured: false" in health,
            "health_exposes_provider_readback": "provider_readback" in health,
            "csp_frame_ancestors_none": any(
                header.get("key") == "Content-Security-Policy" and "frame-ancestors 'none'" in header.get("value", "")
                for rule in config.get("headers", [])
                for header in rule.get("headers", [])
            ),
            "binding_requires_readback": binding.get("provider_binding", {}).get("readback_required") is True,
            "binding_not_falsely_production": binding.get("provider_binding", {}).get("production_deployment_id") is None,
        }
        for key, passed in checks.items():
            if not passed:
                findings.append({"code": key, "path": "apps/crownthrive-os-control-plane"})

    state = "PASS" if not findings else "HOLD"
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "state": state,
        "root_directory": "apps/crownthrive-os-control-plane",
        "findings": findings,
        "provider_deployment_claimed": False,
        "provider_readback_required": True,
    }
    result["receipt_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = validate(Path(args.root))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["state"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
