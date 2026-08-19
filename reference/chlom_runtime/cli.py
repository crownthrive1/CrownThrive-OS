from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import CHLOMReferenceEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one request with the CHLOM Phase 2.99 reference runtime")
    parser.add_argument("request", type=Path)
    parser.add_argument("--policies", type=Path, default=Path(__file__).with_name("policies") / "core.v0.json")
    args = parser.parse_args()
    bundle = json.loads(args.policies.read_text(encoding="utf-8"))
    request = json.loads(args.request.read_text(encoding="utf-8"))
    engine = CHLOMReferenceEngine(bundle["rules"])
    decision = engine.evaluate(request)
    print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
