#!/usr/bin/env python3
"""CHLOM Wallet commercialization intent validator and public-safe handoff builder.

The bridge does not hold secrets or broadcast transactions. It validates the
commercial intent and creates an exact, idempotent execution envelope for the
existing trusted CHLOM Agent Wallet runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

FORBIDDEN_KEYS = {
    "private_key",
    "mnemonic",
    "wallet_password",
    "api_secret",
    "access_token",
    "client_secret",
}


class WalletBridgeError(RuntimeError):
    """Raised when an intent violates the CHLOM wallet contract."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WalletBridgeError(f"cannot read {path}: {exc}") from exc


def find_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if (
                str(key).lower() in FORBIDDEN_KEYS
                and isinstance(child, str)
                and child not in ("", "${REDACTED}", "REDACTED", "***")
                and not child.startswith("${")
            ):
                findings.append(child_path)
            findings.extend(find_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_forbidden(child, f"{path}[{index}]"))
    return findings


@dataclass(frozen=True)
class WalletPolicy:
    chain_id: int
    asset_symbol: str
    currency: str
    max_unattended_value_minor: int
    exact_ecac_required: bool
    idempotency_required: bool
    read_after_write_required: bool

    @classmethod
    def from_documents(
        cls,
        agent_policy: Mapping[str, Any],
        bridge_contract: Mapping[str, Any],
    ) -> "WalletPolicy":
        return cls(
            chain_id=int(agent_policy["primary_chain"]["chain_id"]),
            asset_symbol=str(agent_policy["primary_asset"]["symbol"]),
            currency=str(agent_policy["primary_asset"]["symbol"]),
            max_unattended_value_minor=int(
                agent_policy["execution"]["max_unattended_value_minor"]
            ),
            exact_ecac_required=bool(bridge_contract["authority"]["exact_ecac_required"]),
            idempotency_required=bool(agent_policy["execution"]["idempotency_required"]),
            read_after_write_required=bool(
                agent_policy["execution"]["read_after_write_required"]
            ),
        )


REQUIRED_INTENT_FIELDS = {
    "intent_id",
    "idempotency_key",
    "principal_did",
    "component_id",
    "component_version",
    "offer_id",
    "license_id",
    "amount_minor",
    "currency",
    "purpose",
    "source_sha",
    "quote_fingerprint",
    "requested_at",
}


def validate_intent(
    intent: Mapping[str, Any],
    policy: WalletPolicy,
    *,
    human_authorized: bool = False,
) -> None:
    forbidden = find_forbidden(intent)
    if forbidden:
        raise WalletBridgeError(f"forbidden secret-bearing fields: {', '.join(forbidden)}")

    missing = sorted(key for key in REQUIRED_INTENT_FIELDS if intent.get(key) in (None, ""))
    # A free intent may use the explicit no-quote sentinel.
    if intent.get("amount_minor") == 0 and "quote_fingerprint" in missing:
        missing.remove("quote_fingerprint")
    if missing:
        raise WalletBridgeError(f"missing required intent fields: {', '.join(missing)}")

    amount = intent.get("amount_minor")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
        raise WalletBridgeError("amount_minor must be a non-negative integer")
    if intent.get("currency") not in {"USD", policy.currency}:
        raise WalletBridgeError("currency is outside the Base/native-USDC policy")
    if not str(intent.get("source_sha", "")).strip():
        raise WalletBridgeError("exact source_sha is required")
    if policy.idempotency_required and not str(intent.get("idempotency_key", "")).strip():
        raise WalletBridgeError("idempotency_key is required")

    if amount > policy.max_unattended_value_minor and not human_authorized:
        raise WalletBridgeError(
            "paid wallet execution exceeds the certified unattended ceiling; "
            "exact human authorization is required"
        )

    if amount > 0:
        if policy.exact_ecac_required and normalized(intent.get("ecac_state")) != "PASS":
            raise WalletBridgeError("paid intent requires exact ECAC PASS authorization")
        if not str(intent.get("quote_fingerprint", "")).strip():
            raise WalletBridgeError("paid intent requires an exact quote fingerprint")
        if normalized(intent.get("license_acceptance_state")) != "PASS":
            raise WalletBridgeError("paid intent requires accepted license evidence")
    else:
        if intent.get("wallet_route") not in (None, "NONE"):
            raise WalletBridgeError("free intent must not route money movement")


def normalized(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def build_execution_envelope(
    intent: Mapping[str, Any],
    policy: WalletPolicy,
    *,
    human_authorized: bool = False,
) -> dict[str, Any]:
    validate_intent(intent, policy, human_authorized=human_authorized)
    amount = int(intent["amount_minor"])
    mode = "FREE_NO_TRANSFER" if amount == 0 else "AUTHORIZED_PROVIDER_HANDOFF"
    public_intent = {
        key: value
        for key, value in intent.items()
        if str(key).lower() not in FORBIDDEN_KEYS
    }
    envelope = {
        "schema_version": "1.0.0",
        "envelope_id": f"ct.wallet-envelope.{intent['intent_id']}",
        "intent_id": intent["intent_id"],
        "idempotency_key": intent["idempotency_key"],
        "principal_did": intent["principal_did"],
        "component_id": intent["component_id"],
        "component_version": intent["component_version"],
        "offer_id": intent["offer_id"],
        "license_id": intent["license_id"],
        "amount_minor": amount,
        "currency": intent["currency"],
        "chain_id": policy.chain_id,
        "asset_symbol": policy.asset_symbol,
        "source_sha": intent["source_sha"],
        "quote_fingerprint": intent.get("quote_fingerprint"),
        "execution_mode": mode,
        "human_authorized": bool(human_authorized),
        "read_after_write_required": policy.read_after_write_required,
        "settlement_creates_entitlement": False,
        "license_creates_provider_authority": False,
        "state": "AUTHORIZED" if amount > 0 else "ENTITLEMENT_PENDING",
        "intent_fingerprint": fingerprint(public_intent),
    }
    envelope["receipt_fingerprint"] = fingerprint(envelope)
    return envelope


def assert_transition(
    contract: Mapping[str, Any], current_state: str, next_state: str
) -> None:
    machine = contract.get("state_machine")
    if not isinstance(machine, Mapping):
        raise WalletBridgeError("wallet contract has no state_machine")
    current = normalized(current_state)
    target = normalized(next_state)
    allowed = {normalized(value) for value in machine.get(current, [])}
    if target not in allowed:
        raise WalletBridgeError(f"invalid wallet transition {current} -> {target}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intent", type=Path, required=True)
    parser.add_argument("--agent-policy", type=Path, required=True)
    parser.add_argument("--bridge-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--human-authorized", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        intent = load_json(args.intent)
        agent_policy = load_json(args.agent_policy)
        bridge_contract = load_json(args.bridge_contract)
        if not all(isinstance(item, Mapping) for item in (intent, agent_policy, bridge_contract)):
            raise WalletBridgeError("intent and policies must be JSON objects")
        policy = WalletPolicy.from_documents(agent_policy, bridge_contract)
        envelope = build_execution_envelope(
            intent, policy, human_authorized=args.human_authorized
        )
        write_json(args.output, envelope)
    except WalletBridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(envelope["receipt_fingerprint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
