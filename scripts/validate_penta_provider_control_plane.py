#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "runtime" / "penta-provider-control-plane" / "penta_control_plane.py"
REGISTRY = ROOT / "runtime" / "penta-provider-control-plane" / "providers.json"

spec = importlib.util.spec_from_file_location("penta_control_plane", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

registry = mod.Registry(REGISTRY)
errors = mod.validate_registry(registry)
if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(2)

registry_text = REGISTRY.read_text(encoding="utf-8")
source = MODULE.read_text(encoding="utf-8")
assert '"credential_values_in_cookies": false' in registry_text.lower()
assert '"certification_requires_live_provider_readback": true' in registry_text.lower()
assert "Cookies are NOT credential storage" in source

# Structural validation must be deterministic and must never make provider calls.
# Live authentication/readback runs in the following workflow step through `all`.
prior_disable = os.environ.get("PENTA_DISABLE_NETWORK_PROBES")
os.environ["PENTA_DISABLE_NETWORK_PROBES"] = "1"
try:
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        builds = mod.PentaBuild(registry, state).build_all()
        assert len(builds) == len(registry.providers)
        mod.PentaCredentials(registry, state).bind_all()
        certs = mod.PentaCertify(registry, state).certify_all()
        assert len(certs) == len(registry.providers)
        for cert in certs:
            assert cert.state in {
                "HOLD_UNBOUND",
                "AUTH_BOUND_PENDING_READBACK",
                "CERTIFIED",
                "WRITE_VERIFIED",
            }
            artifact = state / next(
                b.artifact_path for b in builds if b.provider_id == cert.provider_id
            )
            assert artifact.exists()
            assert mod.sha256_bytes(artifact.read_bytes()) == cert.artifact_sha256
finally:
    if prior_disable is None:
        os.environ.pop("PENTA_DISABLE_NETWORK_PROBES", None)
    else:
        os.environ["PENTA_DISABLE_NETWORK_PROBES"] = prior_disable

print(f"PASS: {len(registry.providers)} provider adapter contracts validated")
