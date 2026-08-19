# CrownThrive Governed Agent Template Library

This directory contains public-safe source templates used to instantiate CrownThrive governed agents, non-voting subagents, distributable agent packs, CHLOM capability pallets and third-party attribution records.

## Templates

- `agent-role-template.v1.yaml` — complete registered role contract for sovereign-voter, scheduled-specialist or embedded-subagent projections.
- `subagent-role-template.v1.yaml` — narrow non-voting delegation contract.
- `agent-pack-manifest-template.v1.json` — package/release/license/Stripe metadata skeleton for sanitized distributable packs.
- `chlom-capability-pallet-template.v1.yaml` — portable governed capability package; this is not automatically a blockchain/runtime pallet.
- `third-party-attribution-template.v1.yaml` — required rights/notice/distribution intake before external code enters a public or commercial package.

## Construction rule

Do not copy a scheduler prompt and call it an agent. Instantiate a stable role record from the appropriate template, bind it to the current roadmap/gates and authority matrix, define allowed/prohibited actions, evidence sources, tests, rollback and changelog impact, then create the runtime prompt/schedule as a projection of that record.

Material role changes are versioned and archived. Runtime scheduler IDs do not replace stable institutional IDs.

## Safe defaults

The templates intentionally default to:

- non-voting;
- no phase advancement;
- no self-approval;
- no production writes;
- runtime secret references only;
- `UNKNOWN` preserved until evidence resolves it;
- prior versions archived;
- commercial checkout disabled until license and price are authorized.

## Internal versus distributable derivatives

An external/commercial derivative must remove CrownThrive credentials, customer/partner data, restricted evidence, private contracts, proprietary break-glass information and private institutional authority. Generic architecture, schemas, validators, public-safe examples and extension points may be packaged only under an adopted CrownThrive license.

## Third-party/open-source use

Before importing or distributing third-party code, fill the attribution template with the exact upstream repository/version or commit, copyright holder, license/SPDX identifier, attribution/NOTICE obligations, source/copyleft obligations, modification-disclosure requirements, trademark constraints and distribution/SaaS triggers. Preserve every obligation required by the upstream license.

No third-party code is imported merely by the presence of these templates.

## Validation

The current library is indexed by `developers/manifests/agent-template-library.v1.json` and validated by `scripts/validate_agent_template_library.py` in Documentation Governance and the Governed Merge Gate.
