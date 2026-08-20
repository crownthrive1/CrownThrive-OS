# CrownThrive Governed Agent Template Library

This directory contains public-safe source templates used to instantiate CrownThrive governed agents, non-voting subagents, bounded ephemeral children, distributable agent packs, CHLOM capability pallets, future runtime/decentralized adapters and third-party attribution records.

## Templates

- `agent-role-template.v1.yaml` — registered role contract for sovereign-voter, scheduled-specialist or embedded-subagent projections; current source generation 1.1.0 includes delegation/independence controls.
- `subagent-role-template.v1.yaml` — non-voting persistent-or-ephemeral delegation contract with parent/root lineage, authority ceiling, TTL/budget and termination state.
- `agent-pack-manifest-template.v1.json` — package/release/license/Stripe metadata skeleton for sanitized distributable packs.
- `chlom-capability-pallet-template.v1.yaml` — portable governed capability package; this is not automatically a blockchain/runtime pallet.
- `chlom-runtime-adapter-template.v1.yaml` — research-gated Phase-9 template for a future decentralized, cryptographic or protocol-runtime adapter. It does not prove a chain, token, wallet, DAO, smart contract or production network exists.
- `third-party-attribution-template.v1.yaml` — rights/notice/distribution intake before external code enters a public or commercial package.

Machine controls also include:

- `developers/manifests/agent-factory-delegation-policy.v1.json` — role-specific child-spawn matrix, lineage, same-family independence and research-promotion boundary;
- `developers/manifests/agent-rnd-specialist-fabric.v1.json` — permanent non-voting Legal/Regulatory, IP/Rights/Licensing, Finance/Tax/Treasury, Blockchain/Cryptographic Protocol, Accessibility/Consumer Protection and Regional/Global Localization R&D roles.

## Construction rule

Do not copy a scheduler prompt and call it an agent. Instantiate a stable role record from the appropriate template, bind it to current roadmap/gates and authority matrix, define allowed/prohibited actions, delegation boundaries, evidence sources, tests, rollback and changelog impact, then create the runtime prompt/schedule as a projection of that record.

Material role changes are versioned and archived. Runtime scheduler IDs do not replace stable institutional IDs.

## Persistent versus ephemeral rule

A persistent agent requires a stable institutional ID, owner, versioned contract, lifecycle, tools/data classes, evaluation suite, escalation route and lineage record.

An ephemeral child is a bounded runtime specialization. It must carry:

- parent and root agent IDs;
- delegation path and independence family;
- scope/source snapshot;
- allowed tools/data classes;
- inherited authority ceiling;
- budget and TTL;
- output/promotion route;
- termination state.

A parent cannot create permanent CrownThrive authority simply by inventing a new agent name during a run.

## Independence and vote rule

Delegated children are non-voting by default. Child count, model count and confidence do not change the A/B/C/D/S sovereign voter denominator.

Children or siblings of the same governed root do not become independent reviewers merely because they use different prompts, models, tools or runtime IDs. Independent verification must resolve to a distinct governed independence family appropriate to the decision.

## R&D promotion rule

R&D defaults to `RESEARCH_CANDIDATE`.

```text
research
→ model
→ challenge assumptions
→ discover requirements
→ propose architecture
→ identify risks
→ candidate work
```

Research registry growth is expected and is not formal certification drift by count alone. Research enters formal certification only after explicit promotion or material contact with governed scope, such as hard-exit impact, change to an existing governed disposition, canonical/production relevance or authoritative phase-entry evidence.

The routing tags are `CT:RND`, `CT:RESEARCH-CANDIDATE`, `CT:PROMOTION-PENDING` and `CT:CERTIFICATION-SCOPE`. Research candidates and promotion-pending scopes cannot directly become PASS.

## CHLOM two-template rule

CHLOM deliberately separates:

1. **Capability pallet** — business/institutional capability package that can run cloud-first and remain implementation-neutral.
2. **Runtime adapter** — optional future protocol/blockchain/cryptographic adapter behind stable institutional contracts.

A runtime adapter never replaces the cloud/institutional core by default and never inherits production authority from a paper, prototype, public repository or template. Phase 9 activation requires a validated problem/advantage, threat model, legal/privacy/security review, key custody/recovery, rollback, provider exit and explicit governed activation decision.

## Safe defaults

Templates intentionally default to:

- non-voting;
- no phase advancement;
- no self-approval;
- no production writes;
- no child-vote multiplication;
- no same-family manufactured independence;
- runtime secret references only;
- `UNKNOWN` preserved until evidence resolves it;
- R&D as research, not PASS;
- prior versions archived;
- commercial checkout disabled until license and price are authorized;
- no token/wallet/chain dependency for the institutional core.

## Internal versus distributable derivatives

An external/commercial derivative removes CrownThrive credentials, customer/partner data, restricted evidence, private contracts, proprietary break-glass information and private institutional authority. Generic architecture, schemas, validators, public-safe examples and extension points may be packaged only under an adopted CrownThrive license.

## Third-party/open-source use

Before importing or distributing third-party code, fill the attribution template with exact upstream repository/version or commit, copyright holder, license/SPDX identifier, attribution/NOTICE obligations, source/copyleft obligations, modification-disclosure requirements, trademark constraints and distribution/SaaS triggers. Preserve every upstream obligation.

No third-party code is imported merely by the presence of these templates.

## Validation

The library is indexed by `developers/manifests/agent-template-library.v1.json`; lineage is preserved in `developers/manifests/agent-lineage-archive.v1.json`; delegation and R&D are machine-controlled by their dedicated manifests; and `scripts/validate_agent_template_library.py` plus `scripts/scan_reconciliation_tags.py` enforce the current contract in governance workflows.
