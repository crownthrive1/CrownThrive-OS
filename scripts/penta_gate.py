#!/usr/bin/env python3
"""PentaGate: dependency-free repository and CI contract preflight.

PentaGate is intentionally read-only. It finds deterministic defects before
expensive certification/merge work: Python syntax failures and unconditional
imports used by test modules that are unavailable in the actual runner.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import py_compile
import sys
from typing import Any, Iterable

SCHEMA = "ct.penta.gate-scan.20260826.v1"
IGNORED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__"}


def canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if not any(part in IGNORED_PARTS for part in path.parts):
            yield path


def _test_files(root: Path) -> Iterable[Path]:
    tests = root / "tests"
    if not tests.exists():
        return []
    return sorted(tests.rglob("test_*.py"))


def _local_module(root: Path, module: str) -> bool:
    candidates = [
        root / f"{module}.py",
        root / module / "__init__.py",
        root / "scripts" / f"{module}.py",
        root / "runtime" / f"{module}.py",
        root / "tests" / f"{module}.py",
    ]
    return any(path.exists() for path in candidates)


def _unconditional_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    # Only module-body imports are mandatory at discovery time. Imports nested
    # in try/except or functions are intentionally not treated as hard deps.
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".", 1)[0])
    return modules


def scan_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    for candidate in (root, root / "scripts", root / "runtime"):
        text = str(candidate)
        if text not in sys.path:
            sys.path.insert(0, text)

    findings: list[dict[str, Any]] = []
    python_files = sorted(_python_files(root))
    for path in python_files:
        rel = path.relative_to(root).as_posix()
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            findings.append({
                "code": "python_compile_failure",
                "path": rel,
                "severity": "BLOCK",
                "detail": str(exc),
                "repair_class": "patch_known_code",
            })

    tested_imports = 0
    for path in _test_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            imports = sorted(_unconditional_imports(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            findings.append({
                "code": "test_ast_failure",
                "path": rel,
                "severity": "BLOCK",
                "detail": str(exc),
                "repair_class": "patch_known_code",
            })
            continue
        for module in imports:
            tested_imports += 1
            if module in sys.stdlib_module_names or _local_module(root, module):
                continue
            try:
                available = importlib.util.find_spec(module) is not None
            except (ImportError, AttributeError, ValueError):
                available = False
            if not available:
                findings.append({
                    "code": "missing_test_import",
                    "path": rel,
                    "module": module,
                    "severity": "BLOCK",
                    "detail": f"unconditional test dependency unavailable in runner: {module}",
                    "repair_class": "repair_workflow",
                })

    workflows = root / ".github" / "workflows"
    unittest_discovery_refs = 0
    pytest_refs = 0
    if workflows.exists():
        for path in workflows.glob("*.yml"):
            text = path.read_text(encoding="utf-8", errors="replace")
            unittest_discovery_refs += text.count("unittest discover")
            pytest_refs += text.count("pytest")
        for path in workflows.glob("*.yaml"):
            text = path.read_text(encoding="utf-8", errors="replace")
            unittest_discovery_refs += text.count("unittest discover")
            pytest_refs += text.count("pytest")

    status = "PASS" if not findings else "HOLD"
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "scope": "repository_local_runner_contract",
        "python_files_scanned": len(python_files),
        "test_imports_checked": tested_imports,
        "unittest_discovery_refs": unittest_discovery_refs,
        "pytest_workflow_refs": pytest_refs,
        "findings": findings,
        "mutation_performed": False,
        "production_promotion_authorized": False,
    }
    result["receipt_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = scan_repository(Path(args.root))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
