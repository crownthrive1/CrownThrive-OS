#!/usr/bin/env python3
"""Run the dependency-free COS V1 source validation gate locally or in CI.

This validates source contracts only. It performs no provider mutation and does
not claim deployment, production readback, or institutional certification.
"""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path
import re
import subprocess
import sys

import yaml


MINIMUM_PYTHON = (3, 12)
REQUIRED_NODE_MAJOR = 24
REQUIRED_JSONSCHEMA_VERSION = "4.26.0"
REQUIRED_PYYAML_VERSION = "6.0.3"
CONTROL_PLANE = Path("apps/crownthrive-os-control-plane")
WORKFLOW_DIR = Path(".github/workflows")
PENTAFABRIC_INGEST = Path("supabase/functions/pentafabric-ingest/index.ts")
PENTAFABRIC_CONFIG = Path("supabase/config.toml")
PENTAFABRIC_BUILD_BINDING = Path(
    "supabase/migrations/20260830010000_pentafabric_signed_build_binding.sql"
)
PENTAFABRIC_CANARY = Path(
    ".github/workflows/pentafabric-production-canary.yml"
)
VERCEL_PROVIDER_READBACK = Path(
    ".github/workflows/vercel-provider-readback.yml"
)
FUNCTION_TEST_MODULES = (
    "tests/test_cos_v1_convergence_core_contract.py",
    "tests/test_penta_family.py",
    "tests/test_penta_protocol_suite.py",
)
UNITTEST_MODULES = (
    "tests.test_penta_provider_control_plane",
    "tests.test_penta_mail",
    "tests.test_penta_os_v1",
    "tests.test_penta_runtime_suite",
    "tests.test_penta_context",
    "tests.test_penta_convergence_certifier",
    "tests.test_penta_institutional_services",
    "tests.test_run_function_tests",
)


class ValidationError(RuntimeError):
    """Raised when the local validation environment is incomplete."""


def run(command: list[str], *, cwd: Path) -> None:
    print(f"\n$ {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode:
        raise subprocess.CalledProcessError(completed.returncode, command)


def node_version(root: Path) -> tuple[int, int]:
    completed = subprocess.run(
        ["node", "--version"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise ValidationError("Node.js is required for control-plane validation")
    match = re.fullmatch(r"v(\d+)\.(\d+)\.\d+\s*", completed.stdout)
    if not match:
        raise ValidationError(f"unrecognized Node.js version: {completed.stdout!r}")
    return int(match.group(1)), int(match.group(2))


def require_environment(root: Path) -> None:
    if sys.version_info[:2] < MINIMUM_PYTHON:
        raise ValidationError(
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}+ is required; "
            f"found {sys.version_info.major}.{sys.version_info.minor}"
        )
    observed_node = node_version(root)
    if observed_node[0] != REQUIRED_NODE_MAJOR:
        raise ValidationError(
            f"Node.js {REQUIRED_NODE_MAJOR}.x is required; "
            f"found {observed_node[0]}.{observed_node[1]}"
        )
    try:
        jsonschema_version = importlib.metadata.version("jsonschema")
    except importlib.metadata.PackageNotFoundError as error:
        raise ValidationError(
            "pinned validation dependencies are missing; run "
            "python3 -m pip install -r requirements/cos-v1-validation.txt"
        ) from error
    if jsonschema_version != REQUIRED_JSONSCHEMA_VERSION:
        raise ValidationError(
            f"jsonschema {REQUIRED_JSONSCHEMA_VERSION} is required; "
            f"found {jsonschema_version}"
        )
    try:
        pyyaml_version = importlib.metadata.version("PyYAML")
    except importlib.metadata.PackageNotFoundError as error:
        raise ValidationError(
            "pinned validation dependencies are missing; run "
            "python3 -m pip install -r requirements/cos-v1-validation.txt"
        ) from error
    if pyyaml_version != REQUIRED_PYYAML_VERSION:
        raise ValidationError(
            f"PyYAML {REQUIRED_PYYAML_VERSION} is required; "
            f"found {pyyaml_version}"
        )

    required = (
        CONTROL_PLANE / "package.json",
        CONTROL_PLANE / "scripts/validate-source.mjs",
        PENTAFABRIC_INGEST,
        PENTAFABRIC_CONFIG,
        PENTAFABRIC_BUILD_BINDING,
        PENTAFABRIC_CANARY,
        VERCEL_PROVIDER_READBACK,
        Path("requirements/cos-v1-validation.txt"),
        Path("scripts/validate_github_actions_runtime_policy.py"),
        Path("scripts/validate_gate_registry_v4.py"),
        Path("scripts/run_function_tests.py"),
        *(Path(path) for path in FUNCTION_TEST_MODULES),
        *(Path(*module.split(".")).with_suffix(".py") for module in UNITTEST_MODULES),
    )
    missing = [path.as_posix() for path in required if not (root / path).is_file()]
    if missing:
        raise ValidationError(f"required validation source missing: {', '.join(missing)}")


def validate_workflow_yaml(root: Path) -> None:
    workflow_root = root / WORKFLOW_DIR
    paths = sorted(set(workflow_root.glob("*.yml")) | set(workflow_root.glob("*.yaml")))
    if not paths:
        raise ValidationError("GitHub Actions workflow inventory is empty")
    for path in paths:
        try:
            document = yaml.compose(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            relative = path.relative_to(root).as_posix()
            raise ValidationError(f"invalid GitHub Actions YAML in {relative}: {error}") from error
        if document is None:
            raise ValidationError(
                f"empty GitHub Actions workflow: {path.relative_to(root).as_posix()}"
            )
    print(f"GITHUB_ACTIONS_YAML files={len(paths)} status=PASS", flush=True)


def validate(root: Path) -> None:
    root = root.resolve()
    require_environment(root)
    print(
        "COS V1 source validation boundary: source/tests only; "
        "no provider mutation, deployment readback, or production certification.",
        flush=True,
    )
    validate_workflow_yaml(root)
    run(["node", "scripts/validate-source.mjs"], cwd=root / CONTROL_PLANE)
    run(
        ["node", "--experimental-strip-types", "--check", str(PENTAFABRIC_INGEST)],
        cwd=root,
    )
    run([sys.executable, "-B", "scripts/validate_penta_provider_control_plane.py"], cwd=root)
    run(
        [sys.executable, "-B", "scripts/run_function_tests.py", *FUNCTION_TEST_MODULES],
        cwd=root,
    )
    run(
        [sys.executable, "-B", "-m", "unittest", "-v", *UNITTEST_MODULES],
        cwd=root,
    )
    run([sys.executable, "-B", "scripts/validate_github_actions_runtime_policy.py"], cwd=root)
    run([sys.executable, "-B", "scripts/validate_gate_registry_v4.py"], cwd=root)
    print(
        "\nCOS_V1_SOURCE_VALIDATION status=PASS "
        "provider_mutation=false production_certification_claimed=false",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()
    try:
        validate(Path(args.root))
    except (OSError, ValidationError, subprocess.CalledProcessError) as error:
        print(f"COS_V1_SOURCE_VALIDATION status=HOLD detail={error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
