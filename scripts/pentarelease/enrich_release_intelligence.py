#!/usr/bin/env python3
"""Enrich PentaRelease artifacts and managed surfaces with canonical release intelligence.

Consumes the canonical post-release economic/CIE projection returned by the governed
OIDC evidence bridge. It never converts internal Penta execution units into currency,
and it preserves a distinction between observed provider cost, recognized exposure,
and certified direct-usage calculation status.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

START = "<!-- pentarelease:managed-release-surface:start -->"
END = "<!-- pentarelease:managed-release-surface:end -->"
RELEASE_START = "{/* pentarelease:comprehensive-release:start */}"
RELEASE_END = "{/* pentarelease:comprehensive-release:end */}"


def load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd_json(*args: str) -> dict[str, Any]:
    p = subprocess.run(args, text=True, capture_output=True)
    if p.returncode:
        return {}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {}


def nested(value: Any, *keys: str, default: Any = None) -> Any:
    cur = value
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def money(value: Any) -> str:
    try:
        return f"${float(value):,.2f} USD"
    except (TypeError, ValueError):
        return "not available"


def dimension_summary(value: Any) -> str:
    """Render CIE dimensions as deterministic MDX-safe inline text."""
    if not isinstance(value, dict) or not value:
        return "not available"
    return ", ".join(f"{key}={value[key]}" for key in sorted(value))


def strip_block(text: str, start: str, end: str) -> str:
    return re.sub(re.escape(start) + r".*?" + re.escape(end) + r"\n?", "", text, flags=re.S).rstrip()


def upsert(text: str, body: str, start: str = START, end: str = END) -> str:
    base = strip_block(text, start, end)
    block = f"{start}\n{body.rstrip()}\n{end}"
    return base + ("\n\n" if base else "") + block + "\n"


def release_intelligence(record: dict[str, Any], runtime: dict[str, Any], provider: dict[str, Any]) -> dict[str, Any]:
    result = runtime.get("result") if isinstance(runtime.get("result"), dict) else runtime
    projected = result.get("projected") if isinstance(result.get("projected"), dict) else result
    footer = projected.get("footer") if isinstance(projected.get("footer"), dict) else result.get("footer", {})
    evaluation = result.get("evaluation") if isinstance(result.get("evaluation"), dict) else projected.get("evaluation", {})
    if not evaluation and isinstance(result.get("resolved"), dict):
        evaluation = result["resolved"].get("evaluation") or {}

    cie = footer.get("cie") if isinstance(footer.get("cie"), dict) else {}
    cie_evidence = cie.get("evidence") if isinstance(cie.get("evidence"), dict) else {}
    penta_costs = footer.get("penta_costs") if isinstance(footer.get("penta_costs"), dict) else {}
    penta_pay = footer.get("penta_pay") if isinstance(footer.get("penta_pay"), dict) else {}
    usd = footer.get("usd_summary") if isinstance(footer.get("usd_summary"), dict) else {}
    direct = evaluation.get("cost") if isinstance(evaluation.get("cost"), dict) else {}

    changed = record.get("what_changed") or []
    assets = provider.get("assets") or []
    author = nested(provider, "author", "login", default=None) or record.get("publisher") or "PentaRelease"
    target = provider.get("target_commitish") or nested(record, "provenance", "release_target")
    tag = record.get("tag") or provider.get("tag_name")

    dimensions = cie_evidence.get("dimension_scores") if isinstance(cie_evidence.get("dimension_scores"), dict) else {}
    intel = {
        "schema": "ct.pentarelease.release-intelligence.v3",
        "identity": {
            "release": tag,
            "title": record.get("title") or provider.get("name"),
            "publisher": record.get("publisher") or "PentaRelease",
            "provider_actor": author,
            "repository": nested(record, "provenance", "repository"),
            "target_ref": target,
            "official_release_url": record.get("official_release_url") or provider.get("html_url"),
        },
        "who": {
            "publisher": record.get("publisher") or "PentaRelease",
            "provider_actor": author,
            "penta_components": record.get("penta_components") or ["PentaRelease"],
        },
        "what": {
            "changed_paths": changed,
            "changed_path_count": len(changed),
            "ecosystem_lanes": record.get("ecosystem_lanes") or [],
            "release_assets_observed": len(assets),
        },
        "when": {
            "created_at": provider.get("created_at") or nested(record, "provenance", "created_at"),
            "published_at": provider.get("published_at") or nested(record, "provenance", "published_at"),
            "intelligence_generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        "where": {
            "repository": nested(record, "provenance", "repository"),
            "release_url": record.get("official_release_url") or provider.get("html_url"),
            "target_ref": target,
            "repository_surfaces": ["README.md", "ABOUT_ME.md", "LICENSE", "CODE_OF_CONDUCT.md", "PARTNERS.md", "FAQ.md", "CHANGELOG.md"],
            "pentadocs_group": "CrownThrive OS / PentaRelease",
        },
        "why": record.get("why"),
        "what_to_expect": {
            "release_behavior": "The published release, release assets, repository managed surfaces, and PentaDocs must converge on the same release intelligence record.",
            "evidence_behavior": "Provider readback, cost methodology, CIE evidence, hashes, and any HOLD/unknown state remain explicit; missing evidence is never converted into PASS.",
            "authority_behavior": "Versioning and publication do not manufacture D3, provider, rights, settlement, or certification authority.",
        },
        "costs": {
            "currency": "USD",
            "provider_actual_usd": penta_costs.get("provider_actual_usd"),
            "provider_estimated_usd": penta_costs.get("provider_estimated_usd"),
            "penta_pay_gross_usd": penta_pay.get("gross_usd"),
            "penta_pay_settled_usd": penta_pay.get("settled_usd"),
            "recognized_release_exposure_usd": usd.get("recognized_release_exposure_usd"),
            "internal_reserved_units": penta_costs.get("internal_reserved_units"),
            "internal_accounted_units": penta_costs.get("internal_accounted_units"),
            "direct_usage_calculation": direct,
            "methodology": {
                "recognized_release_exposure": "provider actual USD + gross PentaPay obligations",
                "provider_actual": "sum of release-linked actual provider usage events recorded by the governed runtime",
                "provider_estimate": "sum of release-linked provider cost reservations",
                "direct_usage": "certified release_provider_usage units multiplied by matching certified provider rate cards; unavailable when bindings/rates are absent or uncertified",
                "internal_units": "displayed separately as execution accounting units and never converted or relabeled as currency",
                "sunk_costs": "fixed subscription/compute sunk costs are excluded from direct usage calculation unless explicitly release-bound",
            },
            "sources": [
                "penta_os20.calculate_release_cost",
                "public.penta_release_economic_envelope_v2",
                "public.penta_release_footer_v1",
            ],
        },
        "cie": {
            "status": cie.get("status"),
            "score": cie.get("score"),
            "dimension_scores": dimensions,
            "source": cie.get("source"),
            "evidence_hash": cie.get("evidence_hash"),
            "algorithm_id": cie_evidence.get("algorithm_id"),
            "algorithm_version": cie_evidence.get("algorithm_version"),
            "human_review_required": cie_evidence.get("human_review_required"),
            "hard_blocks": cie_evidence.get("hard_blocks") or [],
            "reasons": cie_evidence.get("reasons") or [],
        },
        "verification": {
            "provider_release_readback": True,
            "release_asset_count": len(assets),
            "evidence_sha256": footer.get("evidence_sha256"),
            "settlement_finality": footer.get("settlement_finality"),
            "separation_invariant": footer.get("separation_invariant"),
        },
    }
    return intel


def render_markdown(record: dict[str, Any], intel: dict[str, Any]) -> str:
    ident, costs, cie = intel["identity"], intel["costs"], intel["cie"]
    what, when, where = intel["what"], intel["when"], intel["where"]
    changed = what.get("changed_paths") or []
    dimensions = cie.get("dimension_scores") or {}
    direct = costs.get("direct_usage_calculation") or {}
    direct_value = direct.get("direct_usd_cost")
    direct_text = money(direct_value) if direct_value is not None else f"not available ({direct.get('reason') or 'no certified release-specific direct-usage calculation'})"
    changed_lines = "\n".join(f"- `{p}`" for p in changed[:50]) or "- No changed-path list supplied."
    if len(changed) > 50:
        changed_lines += f"\n- … plus {len(changed)-50} additional paths"
    dim_lines = "\n".join(f"| {k.replace('_',' ').title()} | {v} |" for k, v in dimensions.items()) or "| Evidence dimensions | not available |"
    return f"""# {ident.get('title') or ident.get('release')}

{RELEASE_START}
## Release intelligence

| Question | Answer |
| --- | --- |
| **Who** | Publisher: **{intel['who']['publisher']}**; provider actor: **{intel['who']['provider_actor']}** |
| **What** | {what.get('changed_path_count',0)} changed path(s); Penta components: {', '.join(intel['who'].get('penta_components') or [])} |
| **When** | Created `{when.get('created_at') or 'not available'}`; published `{when.get('published_at') or 'not available'}` |
| **Where** | `{where.get('repository')}` → `{where.get('target_ref')}`; canonical release: {where.get('release_url')} |
| **Why** | {intel.get('why') or 'See governed release notes and changed paths.'} |
| **What to expect** | Release/assets/README/PentaDocs converge on this same record; unknown/HOLD evidence remains explicit. |

## What changed

{changed_lines}

## Operational expectations

- {intel['what_to_expect']['release_behavior']}
- {intel['what_to_expect']['evidence_behavior']}
- {intel['what_to_expect']['authority_behavior']}

## Cost calculation and methodology

| Measure | Value | Meaning |
| --- | ---: | --- |
| Provider actual | **{money(costs.get('provider_actual_usd'))}** | Observed release-linked provider usage |
| Provider estimate | **{money(costs.get('provider_estimated_usd'))}** | Release-linked reservations |
| PentaPay gross | **{money(costs.get('penta_pay_gross_usd'))}** | Explicit release-linked obligations |
| PentaPay settled | **{money(costs.get('penta_pay_settled_usd'))}** | Readback-confirmed settlements |
| Recognized release exposure | **{money(costs.get('recognized_release_exposure_usd'))}** | Provider actual + gross PentaPay obligations |
| Certified direct-usage calculation | **{direct_text}** | Usage × certified rate card; fails closed if release-specific bindings are absent |
| Internal execution units | reserved `{costs.get('internal_reserved_units')}` / accounted `{costs.get('internal_accounted_units')}` | Accounting units only — **not currency** |

**Method:** recognized exposure = provider actual USD + gross PentaPay obligations. Direct usage cost is independently calculated only when certified release-specific usage bindings and certified rate cards exist. A missing direct-usage binding is reported as unavailable, not silently treated as a $0 direct cost. Fixed subscription/compute sunk costs are excluded unless explicitly release-bound.

## Cultural Imprint Engine (CIE)

**Verdict:** **{cie.get('status') or 'not available'}**  
**Overall score:** **{cie.get('score') if cie.get('score') is not None else 'not available'}/100**  
**Algorithm:** `{cie.get('algorithm_id') or 'not available'}` `{cie.get('algorithm_version') or ''}`  
**Human review required:** `{cie.get('human_review_required')}`

| CIE dimension | Score |
| --- | ---: |
{dim_lines}

Evidence hash: `{cie.get('evidence_hash') or 'not available'}`

## Verification and provenance

- Provider release readback: **verified**
- Release assets observed before enrichment: **{intel['verification']['release_asset_count']}**
- Release evidence SHA-256: `{intel['verification'].get('evidence_sha256') or 'not available'}`
- Repository target: `{ident.get('target_ref') or 'not available'}`
- Generated: `{when.get('intelligence_generated_at')}`
- Cost sources: {', '.join(costs.get('sources') or [])}

## Governance boundary

Publication is evidence of a release, not a manufacture of authority. D3/breaking authority, provider mutation rights, money movement authority, rights/licensing, and certification remain independently governed. HOLD is never silently promoted to PASS.
{RELEASE_END}
"""


def concise_surface(record: dict[str, Any], intel: dict[str, Any]) -> str:
    costs, cie = intel["costs"], intel["cie"]
    return f"""## Latest PentaRelease — {record.get('tag')}

- **Official release:** {record.get('official_release_url')}
- **Release title:** {record.get('title')}
- **Who:** {intel['who']['publisher']} / provider actor {intel['who']['provider_actor']}
- **Why:** {record.get('why')}
- **Changed paths:** {len(record.get('what_changed') or [])}
- **Provider actual cost:** {money(costs.get('provider_actual_usd'))}
- **Recognized release exposure:** {money(costs.get('recognized_release_exposure_usd'))}
- **Direct usage calculation:** `{nested(costs,'direct_usage_calculation','cost_status',default='not_available')}`
- **CIE:** **{cie.get('status') or 'not available'} — {cie.get('score') if cie.get('score') is not None else 'not available'}/100**
- **CIE dimensions:** {', '.join(f"{k}={v}" for k,v in (cie.get('dimension_scores') or {}).items()) or 'not available'}
- **Evidence:** `{intel['verification'].get('evidence_sha256') or 'not available'}`

PentaRelease maintains this bounded block. Content outside the markers remains under its existing ownership and editorial authority.
"""


def mdx(title: str, description: str, body: str) -> str:
    return f'---\ntitle: "{title}"\ndescription: "{description}"\n---\n\n{body.rstrip()}\n'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repository", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--runtime-evidence", required=True)
    ap.add_argument("--dist", default="dist/pentarelease-surface")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    dist = Path(args.dist).resolve()
    record_path = dist / "PENTARELEASE_RELEASE_RECORD.json"
    record = load(record_path, {}) or {}
    runtime = load(Path(args.runtime_evidence), {}) or {}
    provider = cmd_json("gh", "api", f"/repos/{args.repository}/releases/tags/{args.tag}")
    intel = release_intelligence(record, runtime, provider)
    record["schema"] = "ct.pentarelease.comprehensive-release.v2"
    record["release_intelligence"] = intel
    record["payload_costs"] = intel["costs"]
    record["cie_score"] = intel["cie"]
    record.setdefault("evidence", {})["release_intelligence_evidence_sha256"] = intel["verification"].get("evidence_sha256")
    write_json(record_path, record)

    comprehensive = render_markdown(record, intel)
    (dist / "PENTARELEASE_COMPREHENSIVE_RELEASE.md").write_text(comprehensive, encoding="utf-8")
    write_json(dist / "PENTARELEASE_COSTS.json", intel["costs"])
    write_json(dist / "PENTARELEASE_CIE_SCORE.json", intel["cie"])

    ev = load(dist / "PENTARELEASE_EVIDENCE.json", {}) or {}
    ev["release_intelligence"] = intel
    ev["provider_release"] = {
        "id": provider.get("id"), "tag_name": provider.get("tag_name"), "target_commitish": provider.get("target_commitish"),
        "created_at": provider.get("created_at"), "published_at": provider.get("published_at"), "html_url": provider.get("html_url")
    }
    write_json(dist / "PENTARELEASE_EVIDENCE.json", ev)

    cie_dimensions = dimension_summary(intel["cie"].get("dimension_scores"))
    faq = f"""# Release FAQ — {record.get('tag')}

## Who released it?
{intel['who']['publisher']} published the release through the governed PentaRelease lane; GitHub provider actor: {intel['who']['provider_actor']}.

## What changed and why?
{len(record.get('what_changed') or [])} changed path(s). {record.get('why')}

## What did it cost?
Provider actual: {money(intel['costs'].get('provider_actual_usd'))}. Recognized release exposure: {money(intel['costs'].get('recognized_release_exposure_usd'))}. Direct usage calculation status: `{nested(intel,'costs','direct_usage_calculation','cost_status',default='not_available')}`. The direct calculation only exists when certified usage bindings and rate cards exist.

## What is the CIE result?
{intel['cie'].get('status')} — {intel['cie'].get('score')}/100. Dimension scores: `{cie_dimensions}`.

## What should I expect?
The GitHub Release, attached evidence assets, README-managed block, Google Drive mirror, and PentaDocs release pages should all converge on the same release version and evidence hash.
"""
    (dist / "PENTARELEASE_FAQ.md").write_text(faq, encoding="utf-8")
    (dist / "PENTARELEASE_CHANGELOG.md").write_text(
        f"# Changelog — {record.get('tag')}\n\n- Published: {intel['when'].get('published_at')}\n- Changed paths: {len(record.get('what_changed') or [])}\n- Provider actual: {money(intel['costs'].get('provider_actual_usd'))}\n- Recognized exposure: {money(intel['costs'].get('recognized_release_exposure_usd'))}\n- CIE: {intel['cie'].get('status')} — {intel['cie'].get('score')}/100\n- Evidence: `{intel['verification'].get('evidence_sha256')}`\n",
        encoding="utf-8",
    )

    surface = concise_surface(record, intel)
    for rel in ["README.md", "ABOUT_ME.md", "LICENSE", "CODE_OF_CONDUCT.md", "PARTNERS.md", "FAQ.md", "CHANGELOG.md"]:
        p = root / rel
        if p.exists():
            p.write_text(upsert(p.read_text(encoding="utf-8"), surface), encoding="utf-8")

    pages = {
        "pentarelease/latest.mdx": mdx(f"Latest Release — {record.get('tag')}", "Canonical release intelligence: who, what, when, why, where, expectations, costs, CIE, and evidence.", comprehensive),
        "pentarelease/costs.mdx": mdx("Release Costs", "Calculated release economics and methodology.", f"# Release Costs — {record.get('tag')}\n\n```json\n{json.dumps(intel['costs'], indent=2)}\n```"),
        "pentarelease/cie.mdx": mdx("CIE Release Score", "Cultural Imprint Engine release verdict and dimension scores.", f"# CIE — {record.get('tag')}\n\n**{intel['cie'].get('status')} — {intel['cie'].get('score')}/100**\n\n```json\n{json.dumps(intel['cie'], indent=2)}\n```"),
        "pentarelease/evidence.mdx": mdx("Release Evidence", "Provider readback, provenance, hashes, and release intelligence evidence.", f"# Evidence — {record.get('tag')}\n\n```json\n{json.dumps(intel['verification'] | intel['identity'] | intel['when'], indent=2)}\n```"),
        "pentarelease/data.mdx": mdx("Release Data", "Changed paths, release location, and affected ecosystem lanes.", f"# Release Data — {record.get('tag')}\n\n```json\n{json.dumps(intel['what'] | intel['where'], indent=2)}\n```"),
        "pentarelease/faq.mdx": mdx("Release FAQ", "Release FAQ including costs, CIE, expectations, and evidence.", faq),
        "pentarelease/changelog.mdx": mdx("Release Changelog", "Current release chronology and evidence summary.", (dist / "PENTARELEASE_CHANGELOG.md").read_text(encoding="utf-8")),
    }
    for rel, content in pages.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    catalog = load(dist / "PENTARELEASE_DATA_CATALOG.json", {}) or {}
    catalog["release_intelligence"] = {"schema": intel["schema"], "evidence_sha256": intel["verification"].get("evidence_sha256")}
    catalog["generated_assets"] = [
        {"name": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)}
        for p in sorted(dist.iterdir()) if p.is_file()
    ]
    write_json(dist / "PENTARELEASE_DATA_CATALOG.json", catalog)

    print(json.dumps({"status":"enriched","tag":record.get("tag"),"cie":intel['cie'].get('score'),"recognized_exposure_usd":intel['costs'].get('recognized_release_exposure_usd'),"evidence_sha256":intel['verification'].get('evidence_sha256')}, indent=2))


if __name__ == "__main__":
    main()
