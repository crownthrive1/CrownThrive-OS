#!/usr/bin/env python3
"""Run zero-argument function tests with only the Python standard library.

Several CrownThrive suites intentionally use plain ``test_*`` functions while
the repository does not install pytest.  ``unittest discover`` reports those
modules as successful while executing zero cases, so release workflows use
this runner to make every declared function test observable and fail-closed.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
from pathlib import Path
import sys
import traceback


def load_module(path: Path, index: int):
    name = f"crownthrive_function_tests_{index}_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Function-style test modules")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    sys.path.insert(0, str(root))
    passed = 0
    failed = 0

    for index, raw in enumerate(args.paths):
        path = (root / raw).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.suffix != ".py":
            print(f"FAIL invalid test path: {raw}", file=sys.stderr)
            failed += 1
            continue
        module = load_module(path, index)
        candidates = [
            (name, function)
            for name, function in sorted(vars(module).items())
            if name.startswith("test_")
            and inspect.isfunction(function)
            and function.__module__ == module.__name__
        ]
        unsupported = [
            name
            for name, function in candidates
            if inspect.signature(function).parameters
            or inspect.iscoroutinefunction(function)
            or inspect.isgeneratorfunction(function)
            or inspect.isasyncgenfunction(function)
        ]
        for name in unsupported:
            print(
                f"FAIL unsupported function test signature/type: {raw}::{name}",
                file=sys.stderr,
            )
            failed += 1
        tests = [
            (name, function)
            for name, function in candidates
            if name not in unsupported
        ]
        if not tests:
            if not unsupported:
                print(f"FAIL no zero-argument function tests discovered: {raw}", file=sys.stderr)
                failed += 1
            continue
        for name, function in tests:
            try:
                function()
            except Exception:  # noqa: BLE001 - a test runner must capture every failure.
                failed += 1
                print(f"FAIL {raw}::{name}", file=sys.stderr)
                traceback.print_exc()
            else:
                passed += 1
                print(f"PASS {raw}::{name}")

    print(f"FUNCTION_TESTS passed={passed} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
