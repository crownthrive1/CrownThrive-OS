#!/usr/bin/env python3
"""Command-line entrypoint for the CrownThrive GitHub execution fabric."""
from __future__ import annotations

import argparse
from pathlib import Path

from penta.github_fabric.fabric import execute_request, load_contract, write_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = execute_request(load_contract(args.contract), load_contract(args.request))
    write_receipt(args.receipt, result.receipt)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
