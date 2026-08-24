# ThriveEvergreen Product Release Contract v1

**Contract ID:** `ct.contract.thriveevergreen-product-release.v1`  
**Framework:** `ct.framework.thriveevergreen-commerce-mesh.v1`  
**Authority:** `ct-founder-override-checkout-credit-production-20260824-v1`

## Release invariant

A Stripe Product/Price, catalog row, product card, Drive folder, or Crown Credits price is not by itself a sellable release. A customer-facing release must resolve the exact offer to the exact product version, exact deliverable or service scope, exact license terms, entitlement behavior, fulfillment path, support boundary, refund/reversal behavior, analytics identity and audit evidence.

## Required release package

For downloadable goods, the package must contain or reference as applicable:

- canonical master and immutable version;
- customer-facing PDF or primary deliverable;
- additional useful formats supported by the product type;
- preview assets;
- manifest and checksum;
- operative license/terms reference;
- support/update statement;
- protected fulfillment object/path;
- entitlement definition;
- refund, dispute, revocation and replacement behavior;
- provider and Crown Credits bindings;
- route and analytics identifiers.

## Format policy

Multi-format delivery is encouraged when the additional format creates real customer value rather than duplicate clutter.

- Printable toolkit: PDF required; DOCX/ODT/XLSX/CSV/PPTX/PNG/JPG/SVG/EPUB may be added where useful.
- Developer kit: PDF + Markdown required; DOCX/JSON/YAML/CSV/ZIP may be included where useful.
- Digital printable/art: print-ready PDF + PNG required; JPG/SVG/ZIP may be included where appropriate.
- Membership/software access: entitlement/access is primary; do not create meaningless download files merely to satisfy a format count.
- Human-supervised service: exact scope and customer deliverable must be stated before sale.

Editable source is delivered only when the license permits it.

## Quality/value gate

Before release, paired Product Architect and Fulfillment QA agents assess usefulness, completeness, design coherence, legibility/accessibility evidence, format coverage, editability where licensed, support clarity, delivery reliability, discoverability, and economic fit. Packages below the configured quality floor return to production rather than being released to inflate catalog volume.

## Commerce rails

A qualified release may expose both eligible rails:

- direct Stripe Checkout using the exact bound Price;
- Crown Credits purchase using the exact internal credit price.

Both rails must resolve to the same governed release binding, license and entitlement. Crown Credits top-up is a separate funding transaction and never substitutes for release authorization.

## Settlement and fulfillment

Payment-provider success is evidence, not institutional settlement by itself. Provider state must be read back and reconciled. Entitlement is issued only for the exact verified release binding. Instant downloads use short-lived protected delivery links or equivalent controlled delivery. Refunds/disputes trigger the appropriate entitlement reversal or review path.

## Founder override interaction

The Founder production override supersedes ordinary governance HOLDs that merely delayed authorized checkout activation. It does not manufacture product bodies, rights, tax determinations, license acceptance, provider success, delivery success, or customer assent. Missing evidence stays explicit and is routed for completion.

## Persistent desired state

Once a release is qualified and activated under this authority, `ENABLED` is its desired commerce state. A temporary fail-closed condition must record the defect, preserve rollback evidence and route remediation toward restoration instead of silently retiring the offer.
