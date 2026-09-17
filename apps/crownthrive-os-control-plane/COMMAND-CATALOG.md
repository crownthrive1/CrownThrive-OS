# Command catalog, books, commerce and Drive

Component version: **1.1.0**. Work: `ct.command.catalog-expansion.20260916`.
Institutional generation: **Phase 3 — Execute**. Audience: authorized CrownThrive operators.
Source state: release candidate until exact-source checks, merge and production readback succeed.

## Open the working inventory

Use the existing Command account and operator grant. This release does not create accounts or change access rights.

- All connected catalogs: `/estate?source=all-catalog-records#operating-suite`
- Go Flipbooks library: `/estate?source=storefront-library#operating-suite`
- Canonical book works: `/estate?source=book-works#operating-suite`
- Book editions: `/estate?source=book-editions#operating-suite`
- Drive file and folder census: `/estate?source=drive-source-census#operating-suite`
- Drive continuation and failures: `/estate?source=drive-census-queue#operating-suite`
- Drive readback receipts: `/estate?source=drive-census-receipts#operating-suite`

A source deep link may include `q`, limited to 120 characters. Searches are literal text. Existing authentication, record authorization, private API caching, request logging and readback boundaries remain unchanged.

## What the unified catalog means

The catalog is a source-backed projection, not a new product factory and not a declaration that every record is for sale. Each row preserves its source key and original record key. Works, editions, deliverable files, offers, prices, provider products and crosswalk records can describe the same underlying product. Do not add those source counts together or label the result unique inventory.

Current registered rows appear automatically through the existing source adapters. Adding a new relation requires an explicit field allowlist and source validation. The private unified view must then be rebuilt against the approved source list. Discovery alone does not expose arbitrary tables.

The coverage expansion connects book works and editions, the Go Flipbooks library and publication registries, paid editions and delivery packages, Virality services and credits, Penta services, COS offers, Stripe catalogs and crosswalks, Locticians and Gretna product sources, API Marketplace products, Sermon Toolkit memberships and partner products, and Drive source/custody inventories. The public overview provides the current adapter count; it is not a whole-account completeness certificate.

## Reading a row

The table shows its readable title, original recorded state, price or offer when recorded, and the source observation time. Inspect exposes the allowlisted fields and safe provider references. Open source follows an existing source or reader reference; it does not copy or publish the underlying file.

Rights and fulfillment states remain visible alongside publication state. An internally visible record may still need a real rights, payment, source-file, tax, entitlement, capacity or delivery repair before customer release. Those defects are work to resolve; hiding them or changing their labels is not a repair.

USD amounts explicitly stored in minor units are formatted as dollars. Missing prices are not displayed as free. Other currencies retain their original minor-unit value for verification. Explicit billing descriptions take precedence. No discount, price change, checkout creation, subscription or payment is performed by the catalog.

Links reject credentials, signed or tokenized query parameters and non-HTTPS schemes. Only recognized Drive identity fields become Drive links. An arbitrary provider object ID is not assumed to be a Google Drive file.

## Drive reconciliation

Drive metadata intake resumes the existing census rather than recreating its history. It upserts by run, provider and exact Drive file ID, retains distinct editions, records parent-scoped evidence and stores continuation per provider page. A folder-only page is not proof that all files were discovered. Partial or capped listings remain incomplete until the provider actually supplies the remaining page or a complete bounded listing.

The current owner-connected route reads metadata through the existing authorized Google Drive connection and writes sanitized census records through a service-only ingest contract. The unattended service-account route has a separate access mismatch for the book root. Do not broaden permissions, replace credentials or treat an inaccessible root as an empty folder. The owner-connected route can progress without claiming that service-account access has been repaired.

Metadata discovery is separate from reading file bodies, verifying binary hashes, assigning rights, selecting a canonical edition, publishing, selling and fulfillment. An item is not licensed or customer-ready simply because its filename resembles a book.

Use the existing documentation-reconciliation owner for continuation. Preserve retired tasks and existing production workers. No new polling loop is added by this UI. The suite follows Command's existing refresh cadence and identifies stale data; it does not claim instantaneous streaming.

## Management boundary

The existing Inspect and Reconcile buttons check the selected source schema and a bounded metadata row through the existing governed worker. They are not a general provider editor, publisher, mail sender, financial operator or full-Drive crawler. Native actions remain with their verified owner adapters and separate acceptance records. Full native-management coverage and whole-Drive completeness remain tracked independently of this release.

## Tests and acceptance

The new `tests/command-catalog.test.mjs` includes 21 focused display, source-link, query, currency, state, privacy and refresh tests. Run:

```sh
node scripts/validate-source.mjs
```

Existing tests must also pass. Runtime acceptance separately requires every new adapter to bind, bounded record reads and search to work, compound-key continuation without repeated identities, the deployed overview to report the expanded source set, protected record requests to reject unauthenticated access, and existing Storage Command to remain available. A local mock test is not a real operator browser session or provider write test.

## Release and rollback

Publish only through the existing reviewed source and connected production deployment route. Record the accepted source commit, production deployment, served script hash, API readbacks and unchanged access boundaries in the private operating manual and reconciliation ledger.

The frontend rollback is a reviewed revert of this component's UI changes to the prior accepted script. Existing catalog rows, provider identities, Drive evidence, source files, rights and receipts must not be deleted as a rollback shortcut. Backend definitions and adapter prestate are preserved separately in the private recovery package. Provider access, scheduler, financial and permission changes require their own verified owner action.

See [the original Operating Suite contract](COMMAND-OPERATING-SUITE.md). Do not close remaining native-action, operator-session or complete-Drive work merely because this display release merges or publishes.
