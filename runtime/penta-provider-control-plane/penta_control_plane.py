#!/usr/bin/env python3
"""CrownThrive Phase 3 software-provider control plane."""
from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sys
from typing import Any
import urllib.error
import urllib.request

UTC = dt.timezone.utc
SOFTWARE_PRIORITY = "software"
SCHEMA_VERSION = "ct.penta.provider-control-plane.v1"


def now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def secret_fingerprint(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def safe_env_present(name: str) -> bool:
    value = os.environ.get(name)
    return bool(value and value.strip())


def redact(text: str) -> str:
    out = text
    for name, value in os.environ.items():
        if value and len(value) >= 8 and any(token in name.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            out = out.replace(value, "[REDACTED]")
    return out[:500]


@dataclasses.dataclass(frozen=True)
class CredentialBinding:
    provider_id: str
    bound: bool
    matched_set: list[str]
    fingerprints: dict[str, str]
    checked_at: str
    reason: str


@dataclasses.dataclass(frozen=True)
class BuildReceipt:
    provider_id: str
    adapter_id: str
    adapter_version: str
    artifact_path: str
    artifact_sha256: str
    build_id: str
    built_at: str
    state: str = "BUILT_PENDING_INDEPENDENT_VERIFICATION"


@dataclasses.dataclass(frozen=True)
class CertificationReceipt:
    provider_id: str
    adapter_id: str
    adapter_version: str
    artifact_sha256: str
    certification_id: str
    certified_operations: list[str]
    contract_tests: list[str]
    live_evidence: list[dict[str, Any]]
    certified_at: str
    expires_at: str
    state: str


@dataclasses.dataclass(frozen=True)
class NurtureObservation:
    provider_id: str
    priority: str
    health: str
    observed_at: str
    reason: str
    drift: list[str]
    cookie_value: str | None


class Registry:
    def __init__(self, path: Path):
        raw = read_json(path, {})
        if raw.get("schema") != SCHEMA_VERSION:
            raise ValueError(f"unexpected registry schema: {raw.get('schema')!r}")
        self.raw = raw
        self.path = path
        self.providers = {p["provider_id"]: p for p in raw.get("providers", [])}

    def provider(self, provider_id: str) -> dict[str, Any]:
        try:
            return self.providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"unknown provider_id: {provider_id}") from exc


class PentaCredentials:
    """Resolve credentials without persisting raw values."""

    def __init__(self, registry: Registry, state_dir: Path):
        self.registry = registry
        self.state_dir = state_dir

    def bind(self, provider_id: str) -> CredentialBinding:
        provider = self.registry.provider(provider_id)
        credential_sets = provider.get("credential_sets", [])
        if not credential_sets:
            binding = CredentialBinding(provider_id, True, [], {}, now(), "no credential required")
        else:
            matched: list[str] = []
            fingerprints: dict[str, str] = {}
            for credential_set in credential_sets:
                names = credential_set.get("all_of", [])
                if names and all(safe_env_present(name) for name in names):
                    matched = list(names)
                    fingerprints = {name: secret_fingerprint(os.environ[name]) for name in names}
                    break
            if matched:
                binding = CredentialBinding(provider_id, True, matched, fingerprints, now(), "credential set bound")
            else:
                missing_sets = [[name for name in cs.get("all_of", []) if not safe_env_present(name)] for cs in credential_sets]
                binding = CredentialBinding(provider_id, False, [], {}, now(), "HOLD_UNBOUND: no complete credential set; missing=" + canonical_json(missing_sets))
        write_json(self.state_dir / "credentials" / f"{provider_id}.json", dataclasses.asdict(binding))
        return binding

    def bind_all(self) -> list[CredentialBinding]:
        return [self.bind(pid) for pid in sorted(self.registry.providers)]


class PentaBuild:
    """Build deterministic adapter/plugin assets and build receipts."""

    FORBIDDEN_SECRET_PATTERNS = (
        re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^$<{\s][^'\"]{7,}"),
        re.compile(r"\bsk_live_[A-Za-z0-9]{8,}\b"),
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{16,}\b"),
    )

    ADAPTER_TEMPLATE = """# generated by PentaBuild; do not hand-edit
schema = {schema!r}
provider_id = {provider_id!r}
adapter_id = {adapter_id!r}
adapter_version = {adapter_version!r}
provider_class = {provider_class!r}
priority = \"software\"
operations = {operations!r}
auth_model = {auth_model!r}

def capabilities():
    return {{
        \"schema\": schema,
        \"provider_id\": provider_id,
        \"adapter_id\": adapter_id,
        \"adapter_version\": adapter_version,
        \"provider_class\": provider_class,
        \"priority\": priority,
        \"operations\": operations,
        \"auth_model\": auth_model,
    }}
"""

    def __init__(self, registry: Registry, state_dir: Path):
        self.registry = registry
        self.state_dir = state_dir

    def build(self, provider_id: str) -> BuildReceipt:
        provider = self.registry.provider(provider_id)
        adapter = provider["adapter"]
        operations = sorted([
            {
                "operation": op["operation"],
                "side_effect": bool(op.get("side_effect", False)),
                "authority_class": op.get("authority_class", "D0"),
                "requires_readback": bool(op.get("requires_readback", False)),
            }
            for op in adapter.get("operations", [])
        ], key=lambda item: item["operation"])
        body = self.ADAPTER_TEMPLATE.format(
            schema="ct.penta.provider-adapter.v1",
            provider_id=provider_id,
            adapter_id=adapter["adapter_id"],
            adapter_version=adapter["version"],
            provider_class=provider.get("provider_class", "vendor"),
            operations=operations,
            auth_model=provider.get("auth_model", "unknown"),
        )
        self.assert_no_embedded_secret(body)
        short_name = adapter["adapter_id"].removeprefix("ct.adapter.").removesuffix(".v1")
        rel = Path("generated/adapters") / provider_id / f"{short_name}-{adapter['version']}.py"
        target = self.state_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        digest = sha256_bytes(body.encode("utf-8"))
        receipt = BuildReceipt(
            provider_id=provider_id,
            adapter_id=adapter["adapter_id"],
            adapter_version=adapter["version"],
            artifact_path=str(rel),
            artifact_sha256=digest,
            build_id=f"build-{provider_id}-{digest[:12]}",
            built_at=now(),
        )
        write_json(self.state_dir / "build" / f"{provider_id}.json", dataclasses.asdict(receipt))
        return receipt

    def build_all(self) -> list[BuildReceipt]:
        return [self.build(pid) for pid in sorted(self.registry.providers)]

    @classmethod
    def assert_no_embedded_secret(cls, text: str) -> None:
        for pattern in cls.FORBIDDEN_SECRET_PATTERNS:
            if pattern.search(text):
                raise ValueError("generated adapter failed secret-leak guard")


class PentaCertify:
    """Independently certify artifacts and exact provider operations using live readback."""

    def __init__(self, registry: Registry, state_dir: Path, ttl_hours: int = 24):
        self.registry = registry
        self.state_dir = state_dir
        self.ttl_hours = ttl_hours

    @staticmethod
    def _expand_template(template: str) -> str:
        names = re.findall(r"\{([A-Z][A-Z0-9_]*)\}", template)
        value = template
        for name in names:
            if not safe_env_present(name):
                raise ValueError(f"missing probe environment: {name}")
            value = value.replace("{" + name + "}", os.environ[name].rstrip("/"))
        return value

    @staticmethod
    def _auth_headers(auth: dict[str, Any]) -> dict[str, str]:
        kind = auth.get("type")
        if kind == "bearer":
            return {"Authorization": "Bearer " + os.environ[auth["env"]]}
        if kind == "header":
            return {auth["header"]: os.environ[auth["env"]]}
        if kind == "supabase":
            key = os.environ[auth["env"]]
            return {"apikey": key, "Authorization": "Bearer " + key}
        if kind == "basic_env_username":
            raw = (os.environ[auth["username_env"]] + ":" + auth.get("password", "")).encode("utf-8")
            return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}
        if kind == "basic_literal_username":
            raw = (auth["username"] + ":" + os.environ[auth["password_env"]]).encode("utf-8")
            return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}
        if kind in (None, "none"):
            return {}
        raise ValueError(f"unsupported auth type: {kind}")

    def _probe(self, provider_id: str, provider: dict[str, Any]) -> dict[str, Any]:
        probe = provider.get("certification_probe")
        if not probe:
            return {"operation": None, "result": "SKIP", "readback": False, "reason": "no certification probe registered", "observed_at": now()}
        operation = probe["operation"]
        if os.environ.get("PENTA_DISABLE_NETWORK_PROBES") == "1":
            return {"operation": operation, "result": "SKIP", "readback": False, "reason": "network probes disabled", "observed_at": now()}
        missing = [name for name in probe.get("required_env", []) if not safe_env_present(name)]
        if missing:
            return {"operation": operation, "result": "HOLD", "readback": False, "reason": "missing non-secret probe environment: " + ",".join(missing), "observed_at": now()}
        try:
            url = self._expand_template(probe["url_template"])
            headers = {"User-Agent": "CrownThrive-PentaCertify/1.1"}
            headers.update(probe.get("headers", {}))
            headers.update(self._auth_headers(probe.get("auth", {})))
            body_value = probe.get("body")
            body = body_value.encode("utf-8") if body_value is not None else None
            request = urllib.request.Request(url, data=body, headers=headers, method=probe.get("method", "GET"))
            with urllib.request.urlopen(request, timeout=12) as response:
                status = int(response.status)
                payload = response.read(1024 * 1024)
            semantic_ok = True
            expected_fields = probe.get("json_field_equals")
            if expected_fields:
                parsed = json.loads(payload.decode("utf-8"))
                semantic_ok = all(parsed.get(key) == expected for key, expected in expected_fields.items())
            passed = status in probe.get("success_http", [200]) and semantic_ok
            return {
                "operation": operation,
                "result": "PASS" if passed else "FAIL",
                "readback": bool(passed),
                "http_status": status,
                "semantic_check": bool(semantic_ok),
                "observed_at": now(),
            }
        except urllib.error.HTTPError as exc:
            return {"operation": operation, "result": "FAIL", "readback": False, "http_status": int(exc.code), "reason": redact(str(exc.reason)), "observed_at": now()}
        except Exception as exc:
            return {"operation": operation, "result": "FAIL", "readback": False, "reason": redact(f"{type(exc).__name__}: {exc}"), "observed_at": now()}

    def certify(self, provider_id: str, live_evidence: list[dict[str, Any]] | None = None) -> CertificationReceipt:
        provider = self.registry.provider(provider_id)
        adapter = provider["adapter"]
        build = read_json(self.state_dir / "build" / f"{provider_id}.json", None)
        if not build:
            raise RuntimeError(f"{provider_id}: missing PentaBuild receipt")
        artifact_path = self.state_dir / build["artifact_path"]
        if not artifact_path.exists():
            raise RuntimeError(f"{provider_id}: built artifact missing")
        data = artifact_path.read_bytes()
        digest = sha256_bytes(data)
        tests: list[str] = []
        if digest != build["artifact_sha256"]:
            raise RuntimeError(f"{provider_id}: artifact digest mismatch")
        tests.append("artifact_digest_matches_build_receipt")
        source = data.decode("utf-8")
        compile(source, str(artifact_path), "exec")
        tests.append("python_compile")
        PentaBuild.assert_no_embedded_secret(source)
        tests.append("no_embedded_secret")
        ns: dict[str, Any] = {}
        exec(compile(source, str(artifact_path), "exec"), ns, ns)
        caps = ns["capabilities"]()
        expected_ops = sorted(op["operation"] for op in adapter.get("operations", []))
        got_ops = sorted(op["operation"] for op in caps["operations"])
        if got_ops != expected_ops:
            raise RuntimeError(f"{provider_id}: operation contract mismatch")
        tests.append("operation_contract_matches_registry")
        binding = read_json(self.state_dir / "credentials" / f"{provider_id}.json", None)
        bound = bool(binding and binding.get("bound"))
        if bound:
            tests.append("credential_binding_present")
        evidence = list(live_evidence or [])
        if bound and provider.get("certification_probe"):
            evidence.append(self._probe(provider_id, provider))
        certified_operations = sorted({
            item["operation"] for item in evidence
            if item.get("operation") in expected_ops and item.get("result") == "PASS" and item.get("readback") is True
        })
        probe_operation = (provider.get("certification_probe") or {}).get("operation")
        probe_passed = bool(probe_operation and probe_operation in certified_operations)
        side_effect_ops = {op["operation"] for op in adapter.get("operations", []) if op.get("side_effect")}
        if not bound:
            state = "HOLD_UNBOUND"
        elif not probe_passed:
            state = "AUTH_BOUND_PENDING_READBACK"
        else:
            state = "CERTIFIED"
        if probe_passed and side_effect_ops and side_effect_ops.issubset(set(certified_operations)):
            state = "WRITE_VERIFIED"
        stamped = dt.datetime.now(UTC).replace(microsecond=0)
        expires = stamped + dt.timedelta(hours=self.ttl_hours)
        material = {
            "provider_id": provider_id,
            "adapter_id": adapter["adapter_id"],
            "adapter_version": adapter["version"],
            "artifact_sha256": digest,
            "certified_operations": certified_operations,
            "tests": tests,
            "live_evidence": evidence,
            "certified_at": stamped.isoformat().replace("+00:00", "Z"),
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
            "state": state,
        }
        cert_id = "cert-" + sha256_bytes(canonical_json(material).encode())[:16]
        receipt = CertificationReceipt(
            provider_id=provider_id,
            adapter_id=adapter["adapter_id"],
            adapter_version=adapter["version"],
            artifact_sha256=digest,
            certification_id=cert_id,
            certified_operations=certified_operations,
            contract_tests=tests,
            live_evidence=evidence,
            certified_at=material["certified_at"],
            expires_at=material["expires_at"],
            state=state,
        )
        write_json(self.state_dir / "certification" / f"{provider_id}.json", dataclasses.asdict(receipt))
        return receipt

    def certify_all(self) -> list[CertificationReceipt]:
        return [self.certify(pid) for pid in sorted(self.registry.providers)]


class CookieLedger:
    """
    Signed non-sensitive state pointer.

    Cookies are NOT credential storage and are NOT the authoritative audit log.
    They carry only routing, software priority, health and an opaque correlation ID.
    """

    COOKIE_NAME = "ct_penta_nurture"

    def __init__(self, signing_key: str | None):
        self.signing_key = signing_key

    def issue(self, provider_id: str, health: str, correlation_id: str) -> str | None:
        if not self.signing_key:
            return None
        payload = {
            "v": 1,
            "provider": provider_id,
            "priority": SOFTWARE_PRIORITY,
            "health": health,
            "cid": correlation_id,
            "exp": int(dt.datetime.now(UTC).timestamp()) + 3600,
        }
        body = base64.urlsafe_b64encode(canonical_json(payload).encode()).rstrip(b"=").decode("ascii")
        sig = hmac.new(self.signing_key.encode(), body.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{body}.{sig}"

    def verify(self, value: str) -> dict[str, Any]:
        if not self.signing_key:
            raise ValueError("cookie signing key unavailable")
        body, sig = value.rsplit(".", 1)
        expected = hmac.new(self.signing_key.encode(), body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("invalid cookie signature")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if payload["exp"] < int(dt.datetime.now(UTC).timestamp()):
            raise ValueError("expired cookie")
        return payload


class PentaNurture:
    """Nurse provider software, track drift, and keep software as the priority lane."""

    def __init__(self, registry: Registry, state_dir: Path):
        self.registry = registry
        self.state_dir = state_dir
        self.cookie = CookieLedger(os.environ.get("PENTA_NURTURE_COOKIE_SIGNING_KEY"))

    @staticmethod
    def _expired(value: str | None) -> bool:
        if not value:
            return True
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")) <= dt.datetime.now(UTC)

    def observe(self, provider_id: str) -> NurtureObservation:
        self.registry.provider(provider_id)
        binding = read_json(self.state_dir / "credentials" / f"{provider_id}.json", None)
        cert = read_json(self.state_dir / "certification" / f"{provider_id}.json", None)
        drift: list[str] = []
        if not binding or not binding.get("bound"):
            drift.append("credential_unbound")
        if not cert:
            drift.append("certification_missing")
        elif cert.get("state") not in {"CERTIFIED", "WRITE_VERIFIED"}:
            drift.append("certification_not_current:" + str(cert.get("state", "UNKNOWN")))
        elif self._expired(cert.get("expires_at")):
            drift.append("certification_expired")
        health = "HEALTHY" if not drift else "DEGRADED"
        reason = "all required software-provider controls current" if not drift else ",".join(drift)
        correlation_id = "nurture-" + secrets.token_hex(8)
        cookie_value = self.cookie.issue(provider_id, health, correlation_id)
        observation = NurtureObservation(provider_id, SOFTWARE_PRIORITY, health, now(), reason, drift, cookie_value)
        event = dataclasses.asdict(observation)
        event["cookie_value"] = None
        event["correlation_id"] = correlation_id
        ledger = self.state_dir / "nurture" / "events.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(canonical_json(event) + "\n")
        write_json(self.state_dir / "nurture" / f"{provider_id}.json", {**event, "latest_cookie_issued": bool(cookie_value)})
        return observation

    def observe_all(self) -> list[NurtureObservation]:
        return [self.observe(pid) for pid in sorted(self.registry.providers)]


class ProductionGate:
    """Fail-closed, operation-level provider eligibility."""

    def __init__(self, registry: Registry, state_dir: Path):
        self.registry = registry
        self.state_dir = state_dir

    def decide(self, provider_id: str, operation: str) -> dict[str, Any]:
        provider = self.registry.provider(provider_id)
        op = next((item for item in provider["adapter"].get("operations", []) if item["operation"] == operation), None)
        reasons: list[str] = []
        if op is None:
            reasons.append("operation_not_registered")
        binding = read_json(self.state_dir / "credentials" / f"{provider_id}.json", None)
        build = read_json(self.state_dir / "build" / f"{provider_id}.json", None)
        cert = read_json(self.state_dir / "certification" / f"{provider_id}.json", None)
        nurture = read_json(self.state_dir / "nurture" / f"{provider_id}.json", None)
        if not binding or not binding.get("bound"):
            reasons.append("credential_not_bound")
        if not build or build.get("state") != "BUILT_PENDING_INDEPENDENT_VERIFICATION":
            reasons.append("build_receipt_missing")
        if not cert or cert.get("state") not in {"CERTIFIED", "WRITE_VERIFIED"}:
            reasons.append("adapter_not_live_certified")
        elif PentaNurture._expired(cert.get("expires_at")):
            reasons.append("certification_expired")
        if not nurture or nurture.get("health") != "HEALTHY":
            reasons.append("nurture_health_not_current")
        if op and op.get("requires_readback") and (not cert or operation not in cert.get("certified_operations", [])):
            reasons.append("exact_operation_not_readback_verified")
        eligible = not reasons
        state = "WRITE_ELIGIBLE" if eligible and op and op.get("side_effect") else ("EXECUTION_ELIGIBLE" if eligible else "HOLD")
        decision = {
            "schema": "ct.penta.production-eligibility.v1",
            "provider_id": provider_id,
            "operation": operation,
            "priority": SOFTWARE_PRIORITY,
            "eligible": eligible,
            "state": state,
            "reasons": reasons,
            "evaluated_at": now(),
        }
        write_json(self.state_dir / "gate" / provider_id / f"{operation}.json", decision)
        return decision


def validate_registry(registry: Registry) -> list[str]:
    errors: list[str] = []
    seen_adapters: set[str] = set()
    for provider_id, provider in sorted(registry.providers.items()):
        if provider.get("priority") != SOFTWARE_PRIORITY:
            errors.append(f"{provider_id}: priority must be software")
        adapter = provider.get("adapter") or {}
        adapter_id = adapter.get("adapter_id")
        if not adapter_id:
            errors.append(f"{provider_id}: adapter_id missing")
        elif adapter_id in seen_adapters:
            errors.append(f"{provider_id}: duplicate adapter_id {adapter_id}")
        else:
            seen_adapters.add(adapter_id)
        if not adapter.get("version"):
            errors.append(f"{provider_id}: adapter version missing")
        operations = adapter.get("operations", [])
        if not operations:
            errors.append(f"{provider_id}: at least one operation required")
        seen_ops: set[str] = set()
        op_map: dict[str, dict[str, Any]] = {}
        for op in operations:
            name = op.get("operation")
            if not name:
                errors.append(f"{provider_id}: operation name missing")
                continue
            if name in seen_ops:
                errors.append(f"{provider_id}: duplicate operation {name}")
            seen_ops.add(name)
            op_map[name] = op
            if op.get("side_effect") and not op.get("requires_readback"):
                errors.append(f"{provider_id}:{name}: side effects require readback")
            if op.get("authority_class") not in {"D0", "D1", "D2", "D3"}:
                errors.append(f"{provider_id}:{name}: invalid authority class")
        probe = provider.get("certification_probe")
        if not probe:
            errors.append(f"{provider_id}: live certification probe missing")
        else:
            probe_op = probe.get("operation")
            if probe_op not in op_map:
                errors.append(f"{provider_id}: certification probe operation not registered")
            elif op_map[probe_op].get("side_effect"):
                errors.append(f"{provider_id}:{probe_op}: certification probe must be read-only")
            if not probe.get("url_template"):
                errors.append(f"{provider_id}: certification probe URL missing")
    return errors


def matrix(registry: Registry, state_dir: Path) -> dict[str, Any]:
    rows = []
    gate = ProductionGate(registry, state_dir)
    for provider_id, provider in sorted(registry.providers.items()):
        credential = read_json(state_dir / "credentials" / f"{provider_id}.json", {})
        cert = read_json(state_dir / "certification" / f"{provider_id}.json", {})
        nurture = read_json(state_dir / "nurture" / f"{provider_id}.json", {})
        row = {
            "provider_id": provider_id,
            "priority": provider.get("priority"),
            "credential": "BOUND" if credential.get("bound") else "HOLD_UNBOUND",
            "certification": cert.get("state", "MISSING"),
            "certified_operations": cert.get("certified_operations", []),
            "health": nurture.get("health", "UNKNOWN"),
            "operations": {},
        }
        for op in provider["adapter"].get("operations", []):
            row["operations"][op["operation"]] = gate.decide(provider_id, op["operation"])
        rows.append(row)
    return {"schema": "ct.penta.provider-readiness-matrix.v1", "generated_at": now(), "priority": SOFTWARE_PRIORITY, "providers": rows}


def run_all(registry: Registry, state_dir: Path) -> int:
    errors = validate_registry(registry)
    if errors:
        for error in errors:
            print("ERROR", error, file=sys.stderr)
        return 2
    PentaCredentials(registry, state_dir).bind_all()
    PentaBuild(registry, state_dir).build_all()
    PentaCertify(registry, state_dir).certify_all()
    PentaNurture(registry, state_dir).observe_all()
    result = matrix(registry, state_dir)
    write_json(state_dir / "readiness-matrix.json", result)
    print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default=str(Path(__file__).with_name("providers.json")))
    parser.add_argument("--state", default=".penta/provider-control-plane")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "credentials", "build", "certify", "nurture", "matrix", "all"):
        sub.add_parser(command)
    gate_parser = sub.add_parser("gate")
    gate_parser.add_argument("provider_id")
    gate_parser.add_argument("operation")
    args = parser.parse_args(argv)
    registry = Registry(Path(args.registry))
    state_dir = Path(args.state)
    if args.command == "validate":
        errors = validate_registry(registry)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 2
        print("Penta provider registry: PASS")
        return 0
    if args.command == "credentials":
        print(json.dumps([dataclasses.asdict(x) for x in PentaCredentials(registry, state_dir).bind_all()], indent=2)); return 0
    if args.command == "build":
        print(json.dumps([dataclasses.asdict(x) for x in PentaBuild(registry, state_dir).build_all()], indent=2)); return 0
    if args.command == "certify":
        print(json.dumps([dataclasses.asdict(x) for x in PentaCertify(registry, state_dir).certify_all()], indent=2)); return 0
    if args.command == "nurture":
        print(json.dumps([dataclasses.asdict(x) for x in PentaNurture(registry, state_dir).observe_all()], indent=2)); return 0
    if args.command == "matrix":
        result = matrix(registry, state_dir); write_json(state_dir / "readiness-matrix.json", result); print(json.dumps(result, indent=2)); return 0
    if args.command == "gate":
        result = ProductionGate(registry, state_dir).decide(args.provider_id, args.operation); print(json.dumps(result, indent=2)); return 0 if result["eligible"] else 3
    if args.command == "all":
        return run_all(registry, state_dir)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
