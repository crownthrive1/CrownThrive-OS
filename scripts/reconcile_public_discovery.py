#!/usr/bin/env python3
"""Reconcile CrownThrive's public discovery, founder, licensing and SEO surfaces.

This script is intentionally deterministic and stdlib-only. It preserves the full
institutional navigation taxonomy while adding compact public entry points and
keeps source acceptance separate from Mintlify/public projection availability.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ABOUT_PATH = ROOT / "about/kavonte-jones-sr.mdx"
LICENSE_OVERVIEW_PATH = ROOT / "support/licensing-and-ip-overview.mdx"
DOCS_PATH = ROOT / "docs.json"
INDEX_PATH = ROOT / "index.mdx"
CHLOM_PATH = ROOT / "chlom/overview.mdx"
DEV_PATH = ROOT / "developers/overview.mdx"
STANDARD_PATH = ROOT / "standards/documentation-source-of-truth-and-autonomous-governance.mdx"

ABOUT_BODY = '''---
title: "Kavonte Jones Sr. — Founding Member"
sidebarTitle: "About the Founder"
description: "Meet Kavonte Jones Sr., Founding Member of CrownThrive, LLC and architect of CrownThrive's Convergent Ecosystem, CHLOM, Cultural Imprint Engine, Thrive Flywheel, MM Suites, and interoperable platform strategy."
icon: "crown"
keywords: ["Kavonte Jones Sr", "CrownThrive founder", "CrownThrive LLC", "CHLOM", "Cultural Imprint Engine", "Thrive Flywheel", "MM Suites", "Convergent Ecosystem", "ecosystem architecture", "entrepreneur"]
---

# Kavonte Jones Sr. — Founding Member of CrownThrive, LLC

Kavonte Jones Sr. is the Founding Member of **CrownThrive, LLC**, where he leads the architecture of a convergent ecosystem designed to connect culture, technology, intellectual property, commerce, media, education, community, licensing, data, and automation without collapsing their distinct responsibilities.

His work centers on building **interoperable institutions rather than isolated products**. CrownThrive's operating model connects platforms and brands through shared identity, governance, evidence, rights, distribution, analytics, economic activation, and institutional memory.

## What he is building

The CrownThrive architecture includes several foundational frameworks and control layers:

- **Convergent Ecosystem** — coordinates platforms, brands, intellectual property, audiences, data, capital, community, and distribution.
- **CHLOM** — CrownThrive's governed metaprotocol for Rights, Rules, Roles, Revenue, Records, Remedies, licensing, evidence, lifecycle, and machine-readable authority.
- **Cultural Imprint Engine** — cultural and contextual governance for identity, narrative, aesthetics, canon, representation, and cross-platform alignment.
- **Thrive Flywheel** — value recirculation linking creation, participation, distribution, measurement, commerce, rewards, reinvestment, and renewed creation.
- **MM Suites** — physical/digital infrastructure for localized, repeatable, culturally aligned business and community operations.
- **ThriveBase** — the institutional state/control-plane layer that preserves governed machine-readable state separately from public documentation.
- **ThriveEvergreen** — the governed commerce and economic-activation authority for products, SKUs, rights, prices, payments, fulfillment, entitlements, advertising, settlement, and reconciliation.

## Ecosystem focus

CrownThrive spans connected lanes including beauty and wellness, culture and media, music and publishing, community and events, education and talent, advertising and distribution, developer infrastructure, analytics, support, commerce, licensing, and place-based experiences.

Selected public-facing platforms and initiatives include **Locticians, Virality Music, CrownThrive IO, CrownLytics, CrownPulse, ThrivePush, CrownThriveU, CrownRewards, CrownFluence, Crown Affiliates, Crown Ambassadors, AdLuxe Network, CrownThrive Studios, Melanin Magic, The Mane Experience, ThriveTickets, ThriveGather, ThrivePeer, ThriveTools, and CrownThrive Support**. Their implementation, release, commercial, legal, rights, and evidence states remain independently governed.

## Operating philosophy

> Platforms perform the work. Corridors organize the work. CHLOM governs the work. ThriveBase preserves institutional state. The institutional record proves what happened.

CrownThrive favors stable institutional identity over vendor lock-in, evidence over appearance, cultural alignment as operating infrastructure, reusable capabilities over duplicated one-off systems, governed automation over unbounded autonomy, explicit rights and consent, and long-term continuity and generational value.

## Build, partner, license, or contribute

Developers and integration partners can begin with the [CrownThrive Developer Platform](/developers/overview). Organizations interested in CHLOM can begin with the [CHLOM Overview](/chlom/overview). Licensing and intellectual-property boundaries are summarized in the [Licensing & IP Overview](/support/licensing-and-ip-overview).

For business, licensing, ecosystem, partnership, or institutional inquiries, contact **contact@crownthrive.com** or visit **crownthrive.com**.

## Public-source boundary

This page is a public-safe professional profile and architectural overview. It does not disclose private contracts, restricted evidence, credentials, unpublished intellectual property, protected algorithms, private economic schedules, customer data, or other confidential CrownThrive material. A public description of a platform or framework does not independently establish production, legal, rights, commercial, or certification status.
'''

LICENSE_OVERVIEW_BODY = '''---
title: "CrownThrive Licensing & Intellectual Property"
sidebarTitle: "Licensing & IP"
description: "Public-safe overview of CrownThrive licensing, copyright, trademarks, patents, trade secrets, AI/model-use restrictions, developer/API permissions, third-party materials, and commercial licensing boundaries."
icon: "copyright"
keywords: ["CrownThrive licensing", "CrownThrive intellectual property", "CHLOM licensing", "API license", "MCP license", "AI training rights", "copyright", "trademark", "trade secrets", "commercial licensing"]
---

# CrownThrive Licensing & Intellectual Property

CrownThrive publishes selected institutional documentation so people can understand, evaluate, integrate with, support, and build relationships around the ecosystem. **Public visibility is not a blanket license.**

The controlling repository notice is the root `LICENSE`. This page explains the public-facing licensing posture in plain language; it does not replace a signed agreement or qualified legal review.

## What CrownThrive protects

CrownThrive's protected estate can include, where applicable, original documentation, software, schemas, registries, taxonomies, architecture, workflows, policies, research, training materials, media, music, books, visual assets, characters, universes, brands, marks, product systems, licensing models, platform designs, CHLOM materials, Cultural Imprint Engine materials, Thrive Flywheel materials, MM Suites architecture, ThriveBase public-safe contracts, ThriveEvergreen specifications, AI/ML/agent systems, prompts, evaluation designs, algorithms, datasets, compilations, and confidential methods.

The exact rights attached to an item depend on authorship, chain of title, applicable law, third-party licenses, contracts, registrations, effective versions, and the item's public/private classification.

## Public access does not automatically authorize reuse

Viewing, indexing, linking to, forking, cloning, downloading, searching, citing, embedding, calling a documented API/MCP surface, submitting a contribution, or making a voluntary payment does not by itself grant permission to republish or commercialize CrownThrive material; create derivative products or competing replicas; train, fine-tune, distill, benchmark, or build datasets/models from protected CrownThrive material beyond rights available under applicable law or an express license; extract proprietary taxonomies, knowledge graphs, prompts, evaluation corpora, algorithms, scoring logic, trade-secret methods, or restricted implementation details; use CrownThrive marks or branded assets as though endorsed or affiliated; exceed the exact authorization of an API/MCP/interface; or infer ownership, license, certification, entitlement, partnership, exclusivity, or production status from public documentation.

## APIs, MCP, SDKs, agents, and machine-readable interfaces

Documentation of an API, MCP tool, schema, event, SDK, agent contract, or interoperability surface describes an interface. It does not automatically grant a license to the underlying CrownThrive intellectual property, private implementation, data, model, business logic, content, or marks. Access remains bounded by credential, role, policy, agreement, rate/cost limit, data class, environment, purpose, and revocation rules.

## AI, machine learning, retrieval, and automated extraction

Unless separately authorized or independently permitted by applicable law, public repository access does not grant permission to use CrownThrive Material for commercial model training, fine-tuning, distillation, embedding corpora, synthetic-data generation, competitive evaluation datasets, bulk knowledge extraction, or reconstruction of protected methods. Public search indexing and ordinary discovery do not create a commercial corpus or model-use license.

## Brands, media, patents, inventions, and confidential methods

CrownThrive names, platform identities, claimed marks, logos, trade dress, universes, characters, stories, recordings, compositions, artwork, photographs, video, curriculum, and other expressive assets remain subject to their applicable rights records. Repository access grants no patent license, invention assignment, or permission to practice protected claims unless an authorized written instrument expressly says so. Confidential algorithms, security controls, private economic models, calibration, restricted prompts, source assets, credentials, evidence, and other trade-secret or confidential material remain protected.

## Commercial licensing

Commercial permission must come from an authorized CrownThrive agreement or governed rights record defining the relevant asset, scope, use, territory, term, channel, attribution, restrictions, economics, sublicensing rights, approval requirements, termination/remedies, and effective version. CHLOM governs rights/evidence relationships; ThriveEvergreen governs economic activation where applicable. A checkout, payment, provider receipt, product page, API call, or technical delivery does not independently substitute for those records.

## Third-party material and contributions

Third-party software, templates, libraries, icons, specifications, services, and dependencies remain governed by their own licenses and terms. A contribution does not automatically establish ownership, joint authorship, compensation, equity, royalty rights, confidentiality, acceptance, or permission to use unrelated CrownThrive material.

## Professional-review boundary

Rights are subject to applicable law, non-waivable statutory exceptions, valid third-party rights, and controlling written agreements. The repository notice is intended to preserve CrownThrive's rights and communicate use boundaries; it is not a substitute for jurisdiction-specific legal advice, registrations, chain-of-title work, or negotiated contracts.

For licensing, permissions, rights, partnership, data/model use, or commercial-use inquiries, contact **contact@crownthrive.com**.
'''

EXPLORE_BLOCK = '''## Explore CrownThrive

<CardGroup cols={2}>
  <Card title="About Kavonte Jones Sr." icon="crown" href="/about/kavonte-jones-sr">
    Meet CrownThrive's Founding Member and explore the institutional design philosophy behind the Convergent Ecosystem, CHLOM, CIE, Thrive Flywheel, MM Suites and interoperable platform strategy.
  </Card>

  <Card title="CHLOM" icon="network-wired" href="/chlom/overview">
    Rights, licensing, evidence, governance, DLA/DAIL/LEX, lifecycle, machine contracts and interoperable institutional authority.
  </Card>

  <Card title="Developer Platform" icon="code" href="/developers/overview">
    APIs, MCP, SDKs, webhooks, identity, adapters, Sites Mesh, sandboxes and governed integration contracts.
  </Card>

  <Card title="Licensing & IP" icon="copyright" href="/support/licensing-and-ip-overview">
    Public-use boundaries for CrownThrive intellectual property, software, documentation, brands, AI/model use, APIs/MCP and commercial licensing.
  </Card>
</CardGroup>

<Note>
  **Source promotion and projection availability are separate gates.** A CrownThrive repository change that satisfies its exact-head documentation, security, governance, authority and applicable specialist gates may be merged even when Mintlify is login-gated, a custom documentation domain is not configured, anonymous indexing is unavailable, or a projection deployment has not yet propagated. Those conditions can block a claim that the documentation is publicly deployed or indexed; they do not, by themselves, block an otherwise governed source merge.
</Note>
'''

PROJECTION_BLOCK = '''<!-- HOMEPAGE_PROJECTION:START -->
## Governed automated projection

This bounded region is generated from the current readiness gate and the homepage projection policy. Hourly no-op runs are heartbeats and do not churn documentation.

```yaml
projection_version: 2.0.0
phase_3_entry: blocked_pending_phase_2_99_hard_exit
source_acceptance: exact_head_required_gates
projection_availability: separate_state_dimension
mintlify_public_access_is_merge_blocker: false
custom_domain_is_merge_blocker: false
indexing_is_merge_blocker: false
projection_claims_require_separate_evidence: true
homepage_refresh: hourly_on_change
candidate_diff: index.mdx_only
automatic_promotion: exact_head_documentation_security_and_governed_merge_gates_only
direct_main_write: false
```

<Note>
  Source acceptance and documentation reachability are independent. A login-gated or temporarily unavailable Mintlify projection can block a public-deployment or indexing claim, but it cannot by itself manufacture a source-governance HOLD after the exact-head required gates pass.
</Note>
<!-- HOMEPAGE_PROJECTION:END -->
'''

STANDARD_BLOCK = '''## Source promotion versus documentation projection availability

Repository acceptance and documentation deployment are related but independent state dimensions.

A source change that satisfies the exact-head documentation, security, governance, authority and applicable specialist gates **must not be held solely because the Mintlify projection is login-gated, anonymously unreachable, not yet indexed, missing a custom domain, awaiting propagation, or otherwise not publicly accessible at that moment**. Those conditions are deployment, distribution, indexing, or availability evidence. They may block a claim that the documentation is publicly deployed, anonymously available, indexed, or canonical at a specific host; they do not manufacture a source-governance failure.

The required sequence is:

```text
governed source candidate
        ↓
exact-head required gates
        ↓
merge/source acceptance when eligible
        ↓
projection deployment/readback
        ↓
public-access/indexing/canonical-host claims only when evidenced
```

Agents must therefore distinguish `source_merge_eligible` from `projection_publicly_available`. A failed or unavailable Mintlify readback never upgrades an unsafe source candidate, but Mintlify availability alone may not downgrade a governance-passed source candidate into a merge HOLD. If deployment is unavailable after merge, record the projection state accurately, preserve rollback/recovery, and continue the separately governed deployment-reconciliation lane.
'''


def replace_frontmatter_field(text: str, field: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(field)}:.*$"
    replacement = f'{field}: {value}'
    if not re.search(pattern, text):
        raise ValueError(f"missing frontmatter field {field}")
    return re.sub(pattern, replacement, text, count=1)


def ensure_after(items: list[str], anchor: str, value: str) -> None:
    if value in items:
        return
    if anchor not in items:
        items.append(value)
        return
    items.insert(items.index(anchor) + 1, value)


def main() -> None:
    ABOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ABOUT_PATH.write_text(ABOUT_BODY, encoding="utf-8")
    LICENSE_OVERVIEW_PATH.write_text(LICENSE_OVERVIEW_BODY, encoding="utf-8")

    docs = json.loads(DOCS_PATH.read_text(encoding="utf-8"))
    docs["description"] = (
        "CrownThrive Operating System: public-safe documentation for CrownThrive, CHLOM, "
        "developer APIs and MCP, licensing, governance, automation, ecosystem platforms, "
        "commerce, support, cultural infrastructure, and institutional architecture."
    )
    groups = docs.setdefault("navigation", {}).setdefault("groups", [])
    for group in groups:
        if group.get("group") == "Start Here":
            ensure_after(group.setdefault("pages", []), "start-here/operating-principles", "about/kavonte-jones-sr")
        if group.get("group") == "Support, Legal & Knowledge":
            ensure_after(group.setdefault("pages", []), "support/legal-depot-and-policy-register", "support/licensing-and-ip-overview")
    docs["navbar"] = {
        "links": [
            {"href": "/about/kavonte-jones-sr", "label": "About"},
            {"href": "/chlom/overview", "label": "CHLOM"},
            {"href": "/developers/overview", "label": "Developers"},
            {"href": "/support/help-center-architecture", "label": "Support"},
            {"href": "https://portal.crownthrive.com", "label": "Collab Portal"},
        ],
        "primary": {"type": "button", "label": "CrownThrive", "href": "https://crownthrive.com"},
    }
    DOCS_PATH.write_text(json.dumps(docs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    index = INDEX_PATH.read_text(encoding="utf-8")
    index = replace_frontmatter_field(
        index,
        "description",
        '"Explore CrownThrive\'s public-safe operating system: CHLOM governance and licensing, developer APIs/MCP, ecosystem architecture, automation, commerce, support, evidence, and Phase 2.99 institutional state."',
    )
    index = replace_frontmatter_field(
        index,
        "keywords",
        '["CrownThrive", "CrownThrive Operating System", "CHLOM", "CrownThrive API", "MCP", "developer platform", "licensing", "intellectual property", "ecosystem architecture", "AI agents", "automation", "Cultural Imprint Engine", "Thrive Flywheel", "MM Suites", "ThriveBase", "ThriveEvergreen"]',
    )
    if "## Explore CrownThrive" not in index:
        index = index.replace("## Live institutional pulse", EXPLORE_BLOCK + "\n## Live institutional pulse", 1)
    if "HOMEPAGE_PROJECTION:START" not in index:
        index = index.replace("## How truth moves", PROJECTION_BLOCK + "\n## How truth moves", 1)
    INDEX_PATH.write_text(index, encoding="utf-8")

    chlom = CHLOM_PATH.read_text(encoding="utf-8")
    chlom = replace_frontmatter_field(
        chlom,
        "description",
        '"Understand CHLOM, CrownThrive\'s governed metaprotocol for rights, licensing, rules, roles, evidence, revenue, records, remedies, lifecycle, APIs/MCP, and interoperable institutional authority."',
    )
    if not re.search(r"(?m)^keywords:", chlom):
        chlom = chlom.replace(
            'icon: "shield"\n',
            'icon: "shield"\nkeywords: ["CHLOM", "CHLOM metaprotocol", "licensing infrastructure", "rights management", "digital licensing", "evidence ledger", "governance", "API", "MCP", "CrownThrive", "DAIL", "DLA", "LEX", "institutional architecture"]\n',
            1,
        )
    CHLOM_PATH.write_text(chlom, encoding="utf-8")

    dev = DEV_PATH.read_text(encoding="utf-8")
    dev = replace_frontmatter_field(
        dev,
        "description",
        '"Build with CrownThrive through governed APIs, MCP tools, SDKs, webhooks, sandboxes, identity, CHLOM capabilities, platform adapters, Sites Mesh, and partner integration contracts."',
    )
    if not re.search(r"(?m)^keywords:", dev):
        dev = dev.replace(
            'icon: "code"\n',
            'icon: "code"\nkeywords: ["CrownThrive developer platform", "CrownThrive API", "CrownThrive MCP", "CHLOM API", "MCP server", "SDK", "webhooks", "developer documentation", "platform integration", "AI agents", "Sites Mesh", "CrownThrive IO"]\n',
            1,
        )
    DEV_PATH.write_text(dev, encoding="utf-8")

    standard = STANDARD_PATH.read_text(encoding="utf-8")
    if "## Source promotion versus documentation projection availability" not in standard:
        standard = standard.replace(
            "## Governance-as-code enforcement tiers",
            STANDARD_BLOCK + "\n## Governance-as-code enforcement tiers",
            1,
        )
    STANDARD_PATH.write_text(standard, encoding="utf-8")

    print("Public discovery, SEO, founder, licensing and source-promotion surfaces reconciled.")


if __name__ == "__main__":
    main()
