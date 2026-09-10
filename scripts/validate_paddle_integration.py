#!/usr/bin/env python3
"""Validate the CrownThrive Paddle Billing source and serving MCP integration."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

UPSTREAM_SHA = "de7fcd3f6cc43bf87a65d6b2e65067611b47353c"
UPSTREAM_REPOSITORY = "https://github.com/PaddleHQ/paddle-agent-skills.git"
UPSTREAM_SUBDIR = "./providers/codex/plugin"

EXPECTED_MCP_SERVERS: dict[str, dict[str, str]] = {
    "paddle-docs": {"type": "http", "url": "https://paddlehq.mcp.kapa.ai"},
    "paddle-live": {"type": "http", "url": "https://mcp.paddle.com/mcp"},
    "paddle-sandbox": {
        "type": "http",
        "url": "https://sandbox-mcp.paddle.com/mcp",
        "bearer_token_env_var": "PADDLE_SANDBOX_API_KEY",
    },
}

PRESERVED_MCP_SERVERS: dict[str, dict[str, object]] = {
    "crownthrive-os": {
        "url": "https://crown-thrive-os.vercel.app/api/mcp",
        "headers": {"Authorization": "Bearer ${CROWNTHRIVE_CONTROL_TOKEN}"},
    },
    "chlom-chain-evidence": {
        "url": "https://chlom-protocol.vercel.app/api/mcp",
        "headers": {"Authorization": "Bearer ${CHLOM_API_TOKEN}"},
    },
    "vercel": {"url": "https://mcp.vercel.com"},
}

EXPECTED_SKILLS = (
    "paddle-billing-history",
    "paddle-catalog-setup",
    "paddle-checkout-web",
    "paddle-customer-portal",
    "paddle-pricing-pages",
    "paddle-sandbox-testing",
    "paddle-subscription-cancel",
    "paddle-subscription-sync",
    "paddle-subscription-update",
    "paddle-webhooks",
)

EXPECTED_SERVING_TOOLS = (
    "crownthrive_paddle_route",
    "crownthrive_paddle_integration_status",
    "crownthrive_paddle_preflight",
)

EXPECTED_SERVING_REWRITES = {
    "/api/mcp": "/api/mcp-paddle",
    "/mcp": "/api/mcp-paddle",
    "/mcp/health": "/api/mcp-paddle",
}

SECRET_PATTERN = re.compile(r"pdl_(?:sdbx|live)_[A-Za-z0-9]{8,}", re.IGNORECASE)


class ContractError(RuntimeError):
    """Raised when the source contract is incomplete or unsafe."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {path}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_secretless(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    require(not SECRET_PATTERN.search(text), f"literal Paddle credential detected in {path}")
    return text


def validate(root: Path) -> dict[str, Any]:
    root = root.resolve()

    mcp_path = root / ".mcp.json"
    marketplace_path = root / ".agents/plugins/marketplace.json"
    registry_path = root / "integrations/paddle/paddle-billing.registry.json"
    skill_path = root / "skills/paddle-billing-governed-routing/SKILL.md"
    runbook_path = root / "integrations/paddle/README.md"
    notice_path = root / "integrations/paddle/THIRD_PARTY_NOTICE.md"
    serving_root = root / "apps/crownthrive-os-control-plane"
    serving_handler_path = serving_root / "api/mcp-paddle.js"
    serving_fabric_path = serving_root / "lib/paddle-fabric.js"
    serving_test_path = serving_root / "tests/paddle-mcp.test.mjs"
    serving_vercel_path = serving_root / "vercel.json"

    mcp = load_json(mcp_path)
    mcp_servers = mcp.get("mcpServers")
    require(isinstance(mcp_servers, dict), ".mcp.json must contain an mcpServers object")

    for server_id, expected in PRESERVED_MCP_SERVERS.items():
        actual = mcp_servers.get(server_id)
        require(
            actual == expected,
            f"pre-existing MCP route {server_id} was removed or changed: expected {expected!r}, got {actual!r}",
        )

    for server_id, expected in EXPECTED_MCP_SERVERS.items():
        actual = mcp_servers.get(server_id)
        require(actual == expected, f"{server_id} contract drift: expected {expected!r}, got {actual!r}")
        require("headers" not in actual, f"{server_id} must not contain inline headers")

    require(not SECRET_PATTERN.search(json.dumps(mcp_servers, sort_keys=True)), "literal Paddle credential detected in .mcp.json")

    marketplace = load_json(marketplace_path)
    require(marketplace.get("name") == "crownthrive-os-plugins", "unexpected marketplace name")
    plugins = marketplace.get("plugins")
    require(isinstance(plugins, list), "marketplace plugins must be a list")
    paddle_plugins = [plugin for plugin in plugins if plugin.get("name") == "paddle"]
    require(len(paddle_plugins) == 1, "marketplace must contain exactly one paddle plugin")
    require(
        paddle_plugins[0].get("source")
        == {
            "source": "git-subdir",
            "url": UPSTREAM_REPOSITORY,
            "path": UPSTREAM_SUBDIR,
            "sha": UPSTREAM_SHA,
        },
        "Paddle marketplace source must remain pinned to the approved exact upstream commit",
    )

    registry = load_json(registry_path)
    require(registry.get("registry_id") == "ct.integration.paddle-billing.v1", "registry_id drift")
    require(registry.get("stable_component_id") == "ct.integration.paddle-billing", "stable component ID drift")
    require(registry.get("lifecycle_state") == "CONTROLLED_TEST", "integration must remain CONTROLLED_TEST")
    require(registry.get("production_state") == "HOLD", "provider production state must remain HOLD")
    provider = registry.get("provider", {})
    require(provider.get("source_commit") == UPSTREAM_SHA, "registry upstream commit does not match marketplace pin")
    require(provider.get("product") == "Paddle Billing", "registry must identify Paddle Billing")
    require(provider.get("excluded_product") == "Paddle Classic", "Paddle Classic exclusion missing")
    registry_skills = tuple(item.get("id") for item in registry.get("skills", []))
    require(registry_skills == EXPECTED_SKILLS, "registry skill inventory is incomplete or out of order")
    verification = registry.get("verification", {})
    require(verification.get("upstream_skill_inventory_count") == len(EXPECTED_SKILLS), "skill count drift")
    require(verification.get("production_certification") == "HOLD", "source cannot claim production certification")

    skill_text = require_secretless(skill_path)
    require("name: paddle-billing-governed-routing" in skill_text, "wrapper skill frontmatter is missing")
    require("Default to `paddle-sandbox`" in skill_text, "sandbox-default invariant is missing")
    require("Never infer `paddle-live`" in skill_text, "live fail-closed invariant is missing")
    for skill_name in EXPECTED_SKILLS:
        require(f"`{skill_name}`" in skill_text, f"wrapper does not route {skill_name}")

    for path in (runbook_path, notice_path, serving_handler_path, serving_fabric_path, serving_test_path):
        require(path.is_file(), f"missing Paddle integration file: {path}")

    handler_text = require_secretless(serving_handler_path)
    fabric_text = require_secretless(serving_fabric_path)
    test_text = require_secretless(serving_test_path)

    require("import legacyMcpHandler from './mcp.js'" in handler_text, "serving wrapper must preserve the existing MCP gateway")
    require("write_tools: 0" in handler_text, "serving wrapper must remain read-only")
    require("requireControlAuthorization(request)" in handler_text, "protected Paddle preflight must require control authorization")
    require("MODERN_PROTOCOL = '2026-07-28'" in handler_text, "serving wrapper lacks modern MCP support")
    for tool_name in EXPECTED_SERVING_TOOLS:
        require(tool_name in handler_text, f"serving wrapper does not expose {tool_name}")
    for skill_name in EXPECTED_SKILLS:
        require(skill_name in fabric_text, f"serving fabric does not route {skill_name}")
    for endpoint in ("https://paddlehq.mcp.kapa.ai", "https://sandbox-mcp.paddle.com/mcp", "https://mcp.paddle.com/mcp"):
        require(endpoint in fabric_text, f"serving fabric does not contain exact endpoint {endpoint}")
    require(UPSTREAM_SHA in fabric_text, "serving fabric is not pinned to the approved upstream commit")
    require("PADDLE_OPERATIONS.length, 10" in test_text, "serving test does not assert all ten Paddle operations")
    require("res.body.tools.length, 12" in test_text, "serving test does not assert additive twelve-tool inventory")

    serving_vercel = load_json(serving_vercel_path)
    rewrites = serving_vercel.get("rewrites")
    require(isinstance(rewrites, list), "serving vercel.json must define rewrites")
    rewrite_map = {item.get("source"): item.get("destination") for item in rewrites if isinstance(item, dict)}
    for source, destination in EXPECTED_SERVING_REWRITES.items():
        require(rewrite_map.get(source) == destination, f"serving rewrite {source} must target {destination}")
    for source in ("/health", "/fabric", "/penta", "/pentafabric/health", "/chlom", "/chlom/health", "/api/chlom/health"):
        require(source in rewrite_map, f"pre-existing serving rewrite {source} was removed")

    checked_paths = (
        mcp_path,
        marketplace_path,
        registry_path,
        skill_path,
        runbook_path,
        notice_path,
        serving_handler_path,
        serving_fabric_path,
        serving_test_path,
        serving_vercel_path,
    )
    return {
        "state": "PASS",
        "validator": "ct.paddle-billing-serving-contract.v2",
        "upstream_commit": UPSTREAM_SHA,
        "mcp_server_count": len(EXPECTED_MCP_SERVERS),
        "preserved_mcp_server_count": len(PRESERVED_MCP_SERVERS),
        "skill_count": len(EXPECTED_SKILLS),
        "serving_existing_tool_count": 9,
        "serving_paddle_tool_count": len(EXPECTED_SERVING_TOOLS),
        "serving_total_tool_count": 12,
        "production_state": "HOLD",
        "files": {str(path.relative_to(root)): sha256_file(path) for path in checked_paths},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args()
    try:
        result = validate(Path(args.root))
    except (ContractError, OSError) as exc:
        print(json.dumps({"state": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
