#!/usr/bin/env python3
"""Validate CrownThrive CIE Wave 2 core documentation and public-safe manifests."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "doctrine/cultural-imprint-engine.mdx",
    "doctrine/cie-public-internal-usage.mdx",
    "doctrine/cie-chlom-interoperability.mdx",
    "chlom/ecosystem-integrations.mdx",
    "developers/manifests/cie-usage-profiles.v1.json",
    "developers/manifests/cie-chlom-interoperability.v1.json",
    "changelog/cie-institutionalization-wave-2-2026-08-23.mdx",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        fail(f"missing Wave 2 artifact: {rel}")
    return path.read_text(encoding="utf-8")


def load_json(rel: str) -> dict:
    value = json.loads(read(rel))
    if not isinstance(value, dict):
        fail(f"JSON object required: {rel}")
    return value


def main() -> int:
    for rel in REQUIRED_FILES:
        read(rel)

    doctrine = read("doctrine/cultural-imprint-engine.mdx")
    usage_doc = read("doctrine/cie-public-internal-usage.mdx")
    interop_doc = read("doctrine/cie-chlom-interoperability.mdx")
    chlom_doc = read("chlom/ecosystem-integrations.mdx")
    changelog = read("changelog/cie-institutionalization-wave-2-2026-08-23.mdx")

    if "canonical_name: Cultural Imprint Engine" not in doctrine:
        fail("canonical Cultural Imprint Engine identity missing from doctrine")
    if "The canonical expansion of `CIE` is **Cultural Imprint Engine**" not in doctrine:
        fail("CIE canonical expansion rule missing")

    for text in (usage_doc, interop_doc, chlom_doc, changelog):
        if "Cultural Imprint Engine" not in text:
            fail("Wave 2 doc missing canonical Cultural Imprint Engine name")

    if "canonical_name_only: true" not in usage_doc:
        fail("single-engine name lock missing")
    if "rejected for new records" not in usage_doc:
        fail("stale Cultural Impact Engine alias rejection missing")
    if "ct.cie.profile.public.v1" not in usage_doc or "ct.cie.profile.internal.v1" not in usage_doc:
        fail("public/internal usage profile IDs missing")
    if "profiles of the same engine" not in usage_doc:
        fail("public/internal profile non-fork rule missing")
    if "D2" not in usage_doc or "D3" not in usage_doc:
        fail("usage authority boundary missing")

    if "ct.contract.cie-chlom.interop.v1" not in interop_doc:
        fail("CIE CHLOM contract ID missing")
    if "bidirectional_typed_fail_closed" not in interop_doc:
        fail("typed fail-closed interoperability mode missing")
    for state in (
        "DENY_CULTURAL",
        "HOLD_CIE",
        "DENY_RIGHTS",
        "HOLD_CHLOM",
        "HOLD_CHLOM_RIGHTS",
        "HOLD_CHLOM_LICENSE",
        "HOLD_EVIDENCE",
        "COMPOSED_READY_NON_EXECUTING",
    ):
        if state not in interop_doc:
            fail(f"interoperability composition state missing: {state}")
    if "CIE PASS == CHLOM ALLOW" not in interop_doc or "CHLOM ALLOW == CIE PASS" not in interop_doc:
        fail("non-collapse invariants missing")

    if "Cultural Imprint Engine interoperability" not in chlom_doc:
        fail("CHLOM-side CIE interoperability section missing")
    if "A CIE `PASS` or `CONDITIONAL_PASS` never becomes CHLOM `ALLOW` by inheritance" not in chlom_doc:
        fail("CHLOM-side authority inheritance boundary missing")
    if "CHLOM `ALLOW` never becomes CIE `PASS` by inheritance" not in chlom_doc:
        fail("CIE-side authority inheritance boundary missing")

    usage_manifest = load_json("developers/manifests/cie-usage-profiles.v1.json")
    if usage_manifest.get("framework_id") != "ct.framework.cultural-imprint-engine":
        fail("usage manifest framework identity drift")
    if usage_manifest.get("canonical_name") != "Cultural Imprint Engine" or usage_manifest.get("canonical_name_only") is not True:
        fail("usage manifest canonical name lock drift")
    profiles = usage_manifest.get("profiles", {})
    if set(profiles) != {"public_safe", "internal_governed"}:
        fail("usage manifest profile set drift")
    if profiles["internal_governed"].get("authority_ceiling") != "D2":
        fail("internal profile authority expansion")

    interop_manifest = load_json("developers/manifests/cie-chlom-interoperability.v1.json")
    if interop_manifest.get("contract_id") != "ct.contract.cie-chlom.interop.v1":
        fail("interop manifest contract ID drift")
    if interop_manifest.get("mode") != "bidirectional_typed_fail_closed":
        fail("interop manifest mode drift")
    if interop_manifest.get("public_engine_mutation") is not False or interop_manifest.get("authority_inheritance") is not False:
        fail("interop manifest illegally creates mutation or authority inheritance")
    effects = interop_manifest.get("positive_state_effects", {})
    for key in (
        "execution_authorized",
        "economic_activation_authorized",
        "provider_write_authorized",
        "d3_authorized",
        "sovereign_vote_effect",
    ):
        if effects.get(key) is not False:
            fail(f"positive composed state authority drift: {key}")

    joined = "\n".join(read(rel) for rel in REQUIRED_FILES)
    credential_patterns = (
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bsb_secret_[A-Za-z0-9_-]{16,}\b",
        r"\bsk-[A-Za-z0-9]{20,}\b",
        r"\bmint_[A-Za-z0-9_-]{16,}\b",
    )
    for pattern in credential_patterns:
        if re.search(pattern, joined):
            fail("credential-shaped value detected in public Wave 2 docs")

    print(
        "CIE Wave 2 core docs validation PASS: Cultural Imprint Engine is canonical-only; "
        "public/internal profiles are one engine; CHLOM interoperability is typed, bidirectional, "
        "fail-closed and non-executing. Mintlify navigation is a separate post-merge gate."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
