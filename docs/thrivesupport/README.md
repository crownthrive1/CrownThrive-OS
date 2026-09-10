# CrownThrive ThriveSupport Documentation Estate

ThriveSupport is the governed support and operational knowledge estate for the CrownThrive ecosystem. This directory is the source package reconciled through PentaDocs for the public projection `ct.projection.support.thrivesupport-public` and protected operator documentation.

## Canonical scope

- Public support domain: `crownthrivesupport.com`
- Provider account: `thrivesupport`
- Governed document root: `/home/thrivesupport/public_html`
- Public projection: `ct.projection.support.thrivesupport-public`
- Documentation consumer: PentaDocs
- Canonical ecosystem term: **Cultural Imprint Engine™**. “Cultural Impact Engine” is deprecated terminology drift.

## Publication lifecycle

Every article moves through:

`draft -> review -> ready_for_publish -> provider_write_receipt -> provider_readback -> published`

Repository presence alone does **not** mean an article is live. Until the scoped cPanel deployment actuator produces a successful provider-write receipt and provider readback, articles remain `ready_for_publish`.

## Access-control rule

Every article must declare a `visibility` and `required_permission`. Public routes must never expose credentials, vault material, case data, internal deployment mechanics, private tokens, API keys, financial credentials, or protected architecture. Protected documents are denied unless the caller has the required role/permission defined in `rbac.yaml`.

## Release controls

Production publication requires:

1. RBAC authorization.
2. Pre-change backup.
3. Checksum manifest.
4. Scoped write restricted to the `thrivesupport` provider account and governed document root.
5. Provider write receipt.
6. Provider readback and route validation.
7. Audit receipt.
8. Rollback point retained for recovery.

No documentation deployment path may bypass CrownThrive OS governance by directly modifying production outside the registered provider adapter.

## Content standard

Articles must be useful support documentation, not marketing filler. Each user-facing article should identify the problem, give safe actions in order, explain what evidence to collect, state what not to disclose, and point to the next relevant support lane. Internal material must minimize personal data and follow least-privilege principles.

The recovery estate of roughly 795 titles across about 150 subcategories is an inventory baseline, not a publishing ceiling. Articles may be added as CrownThrive brands, services, policies, and common support journeys evolve.
