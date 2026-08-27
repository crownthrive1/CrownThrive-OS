#!/usr/bin/env python3
import copy
import datetime as dt
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chlom_wallet_protocol", ROOT / "bin" / "chlom_wallet_protocol.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
POLICY = json.loads((ROOT / "config" / "policy.base-usdc.json").read_text())
USDC = POLICY["primary_asset"]


def now_pair():
    now = dt.datetime.now(dt.timezone.utc)
    return now.isoformat().replace("+00:00", "Z"), (now + dt.timedelta(minutes=15)).isoformat().replace("+00:00", "Z")


def intent(operation="OBSERVE", amount=0, destination=None, risk="D0", key="idem:test:001"):
    created, expires = now_pair()
    return {
        "schema": mod.INTENT_SCHEMA,
        "intent_id": "intent:test:001",
        "idempotency_key": key,
        "operation": operation,
        "risk_class": risk,
        "chain": {"namespace": "eip155", "chain_id": 8453},
        "asset": {"symbol": "USDC", "contract": USDC["contract"], "decimals": 6},
        "amount_minor": amount,
        "destination": destination,
        "requested_by": {"principal": "PentaCertify", "kind": "penta"},
        "purpose": "protocol certification canary",
        "compensation_ref": "ct.compensation.test.v1" if operation != "OBSERVE" else None,
        "created_at": created,
        "expires_at": expires,
    }


class ProtocolTests(unittest.TestCase):
    def test_current_policy_is_valid_and_fail_closed(self):
        self.assertEqual(mod.validate_policy(POLICY), [])
        self.assertFalse(POLICY["capabilities"]["money_movement"])
        self.assertFalse(POLICY["capabilities"]["chain_broadcast"])
        self.assertEqual(POLICY["execution"]["max_unattended_value_minor"], 0)

    def test_policy_cannot_exceed_certified_boundary(self):
        unsafe = copy.deepcopy(POLICY)
        unsafe["capabilities"]["money_movement"] = True
        reasons = mod.validate_policy(unsafe)
        self.assertIn("POLICY_EXCEEDS_CERTIFIED_MONEY_BOUNDARY", reasons)

    def test_legacy_preflight_holds_value_movement(self):
        result = mod.legacy_preflight(POLICY, "base", "USDC", 1, "0x" + "1" * 40)
        self.assertEqual(result["decision"], "HOLD")
        self.assertIn("UNATTENDED_LIMIT_EXCEEDED", result["reasons"])
        self.assertIn("POLICY_MONEY_MOVEMENT_DISABLED", result["reasons"])
        self.assertIn("POLICY_CHAIN_BROADCAST_DISABLED", result["reasons"])

    def test_exact_ecac_cannot_override_closed_policy(self):
        p = copy.deepcopy(POLICY)
        p["allowlists"]["destination_addresses"] = ["0x" + "1" * 40]
        i = intent("TRANSFER_ERC20", 1_000_000, "0x" + "1" * 40, "D2")
        created, expires = now_pair()
        a = {
            "schema": mod.AUTH_SCHEMA,
            "authorization_id": "auth:test:001",
            "decision": "ECAC",
            "intent_sha256": mod.digest(i),
            "policy_sha256": mod.digest(p),
            "scope": {"money_movement": True, "chain_broadcast": True, "settlement_write": False, "signer_key_material_release": False},
            "issued_at": created,
            "expires_at": expires,
            "evidence_refs": ["canary:test"],
        }
        result = mod.evaluate(p, i, a)
        self.assertEqual(result["decision"], "HOLD")
        self.assertIn("POLICY_MONEY_MOVEMENT_DISABLED", result["reasons"])
        self.assertIn("POLICY_CHAIN_BROADCAST_DISABLED", result["reasons"])

    def test_observe_receipt_is_idempotent_and_event_chained(self):
        i = intent()
        with tempfile.TemporaryDirectory() as td:
            state = pathlib.Path(td) / "state"
            evidence = pathlib.Path(td) / "evidence"
            first, code1 = mod.execute(POLICY, i, None, state, evidence, None)
            second, code2 = mod.execute(POLICY, i, None, state, evidence, None)
            self.assertEqual(code1, 0)
            self.assertEqual(code2, 0)
            self.assertEqual(first["status"], "OBSERVED")
            self.assertTrue(second["idempotent_replay"])
            lines = (state / "outbox" / "events.ndjson").read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            event = json.loads(lines[0])
            self.assertEqual(event["previous_event_sha256"], "0" * 64)
            self.assertFalse(event["delivery"]["remote_delivery_claimed"])
            self.assertTrue(event["delivery"]["dail_eligible"])

    def test_transfer_hold_never_invokes_adapter(self):
        p = copy.deepcopy(POLICY)
        p["allowlists"]["destination_addresses"] = ["0x" + "2" * 40]
        i = intent("TRANSFER_ERC20", 100, "0x" + "2" * 40, "D2", "idem:test:transfer")
        with tempfile.TemporaryDirectory() as td:
            receipt, code = mod.execute(p, i, None, pathlib.Path(td) / "state", pathlib.Path(td) / "evidence", "/definitely/not/an/adapter")
            self.assertEqual(code, 3)
            self.assertEqual(receipt["status"], "HOLD")
            self.assertFalse(receipt["execution"]["adapter_invoked"])
            self.assertIn("EXACT_ECAC_AUTHORIZATION_REQUIRED", receipt["decision"]["reasons"])


if __name__ == "__main__":
    unittest.main()
