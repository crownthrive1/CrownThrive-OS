#!/usr/bin/env python3
"""Production queue and bounded dispatch runtime for PentaMarketer.

The runtime is live for governed compilation, queueing, artifact routing, and evidence.
It fails closed for external provider mutation until the exact adapter is certified.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


marketer = load_module("pentamarketer", ROOT / "penta/marketer/pentamarketer.py")
evidence = load_module("penta_evidence", ROOT / "penta/runtime/evidence.py")


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def adapter_map(registry: dict) -> dict[str, dict]:
    return {a["channel"]: a for a in registry.get("adapters", [])}


def queue_id(campaign_id: str, manifest_sha: str) -> str:
    return f"{campaign_id}-{manifest_sha[:12]}"


def enqueue(campaign_path: pathlib.Path, state_root: pathlib.Path, adapters_path: pathlib.Path, registry_path: pathlib.Path, policy_path: pathlib.Path) -> pathlib.Path:
    campaign = read_json(campaign_path)
    registry = read_json(registry_path)
    policy = read_json(policy_path)
    adapters = read_json(adapters_path)
    manifest = marketer.compile_manifest(campaign, registry, policy)
    amap = adapter_map(adapters)
    routes, holds = [], []
    for channel in manifest["channels"]:
        adapter = amap.get(channel)
        if not adapter:
            holds.append({"channel": channel, "reason": "NO_REGISTERED_ADAPTER"})
            continue
        route = {"channel": channel, "adapter_id": adapter["adapter_id"], "state": adapter["state"], "execution_mode": adapter["execution_mode"], "mutation_authority": adapter["mutation_authority"]}
        routes.append(route)
        if adapter["state"] == "hold_unbound" or adapter["execution_mode"] == "none":
            holds.append({"channel": channel, "reason": "HOLD_UNBOUND"})
    qid = queue_id(manifest["campaign_id"], manifest["manifest_sha256"])
    item = {
        "schema_version": "1.0.0",
        "queue_id": qid,
        "campaign_id": manifest["campaign_id"],
        "manifest": manifest,
        "routes": routes,
        "holds": holds,
        "queue_state": "READY_ARTIFACT_ROUTING" if not holds else "READY_WITH_HOLDS",
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "authority_note": "Queue readiness is not provider publication authority."
    }
    path = state_root / "queue" / f"{qid}.json"
    evidence.atomic_write_json(path, item)
    return path


def dispatch(item_path: pathlib.Path, state_root: pathlib.Path, adapters_path: pathlib.Path) -> dict:
    item = read_json(item_path)
    adapters = read_json(adapters_path)
    amap = adapter_map(adapters)
    out_dir = state_root / "dispatch" / item["queue_id"]
    results = []
    for channel in item["manifest"]["channels"]:
        adapter = amap.get(channel)
        if not adapter:
            results.append({"channel": channel, "status": "HOLD", "reason": "NO_REGISTERED_ADAPTER"})
            continue
        if adapter["execution_mode"] == "artifact_only" and not adapter["mutation_authority"]:
            payload = {
                "schema_version": "1.0.0",
                "queue_id": item["queue_id"],
                "campaign_id": item["campaign_id"],
                "channel": channel,
                "adapter_id": adapter["adapter_id"],
                "message": item["manifest"]["message"],
                "cta": item["manifest"]["cta"],
                "terminology": item["manifest"]["terminology"],
                "publication_state": "ARTIFACT_READY_NOT_PUBLISHED",
                "provider_write_authority": false
            }
            payload_path = out_dir / f"{channel}.json"
            evidence.atomic_write_json(payload_path, payload)
            results.append({"channel": channel, "status": "ARTIFACT_READY", "path": payload_path.as_posix(), "adapter_id": adapter["adapter_id"]})
            continue
        if adapter["mutation_authority"] is not True:
            results.append({"channel": channel, "status": "HOLD", "reason": "PROVIDER_WRITE_NOT_CERTIFIED", "adapter_id": adapter["adapter_id"]})
            continue
        # Live provider mutation is deliberately unreachable until an adapter-specific
        # executor with read-after-write certification is registered and reviewed.
        results.append({"channel": channel, "status": "HOLD", "reason": "LIVE_EXECUTOR_NOT_BOUND", "adapter_id": adapter["adapter_id"]})

    overall = "ARTIFACT_DISPATCHED" if results and all(r["status"] == "ARTIFACT_READY" for r in results) else "PARTIAL_HOLD"
    summary = {"schema_version": "1.0.0", "queue_id": item["queue_id"], "campaign_id": item["campaign_id"], "status": overall, "results": results}
    receipt = evidence.receipt(
        system="PentaMarketer",
        operation="bounded_dispatch",
        status=overall,
        authority_ref=item["manifest"]["chlom_authority_ref"],
        inputs=item,
        outputs=summary,
    )
    evidence.atomic_write_json(out_dir / "summary.json", summary)
    evidence.atomic_write_json(out_dir / "receipt.json", receipt)
    evidence.atomic_write_json(state_root / "latest.json", {"queue_id": item["queue_id"], "status": overall, "receipt_sha256": receipt["receipt_sha256"]})
    return {"summary": summary, "receipt": receipt}


def cycle(campaign_path: pathlib.Path, state_root: pathlib.Path, adapters_path: pathlib.Path, registry_path: pathlib.Path, policy_path: pathlib.Path) -> dict:
    item = enqueue(campaign_path, state_root, adapters_path, registry_path, policy_path)
    return dispatch(item, state_root, adapters_path)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["enqueue", "dispatch", "cycle"])
    p.add_argument("--campaign")
    p.add_argument("--item")
    p.add_argument("--state-root", default="var/pentamarketer")
    p.add_argument("--adapters", default="penta/marketer/adapters.registry.json")
    p.add_argument("--registry", default="penta/scribe/registry.json")
    p.add_argument("--policy", default="penta/marketer/policy.json")
    args = p.parse_args(argv)
    state_root = pathlib.Path(args.state_root)
    try:
        if args.command == "enqueue":
            if not args.campaign: raise ValueError("--campaign is required")
            print(enqueue(pathlib.Path(args.campaign), state_root, pathlib.Path(args.adapters), pathlib.Path(args.registry), pathlib.Path(args.policy)))
            return 0
        if args.command == "dispatch":
            if not args.item: raise ValueError("--item is required")
            result = dispatch(pathlib.Path(args.item), state_root, pathlib.Path(args.adapters))
        else:
            if not args.campaign: raise ValueError("--campaign is required")
            result = cycle(pathlib.Path(args.campaign), state_root, pathlib.Path(args.adapters), pathlib.Path(args.registry), pathlib.Path(args.policy))
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
".replace("false