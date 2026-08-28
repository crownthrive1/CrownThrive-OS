# PentaCensus Continuous Namespace Standard

**Standard ID:** `ct.standard.penta.census.v1`  
**Version:** `1.0.0`  
**System identity:** `PentaCensus` / `penta.census`  
**Primary family:** Intelligence, Research & Impact  
**Pentagonal axis:** Truth  
**Initial maturity:** `implemented` governed extension; not yet production-promoted

## 1. Purpose

PentaCensus is the governed namespace-discovery and reconciliation capability for the CrownThrive Penta architecture. Its job is to keep the institutional Penta census from becoming a stale manual list as code, registries, workflows, runtime modules and governed extensions evolve.

PentaCensus answers four questions continuously:

1. Which Penta identities are already known?
2. Which explicit Penta symbols or machine keys appear in governed source but are not represented in the current namespace?
3. Where is the exact source evidence for each new observation?
4. Which canonicalization/governance lane must receive the unresolved discovery?

PentaCensus never answers a fifth question by itself: **whether the new name is allowed to execute.**

## 2. State invariant

`DISCOVERED ≠ CANONICAL ≠ IMPLEMENTED ≠ EXECUTION-ELIGIBLE ≠ AUTHORIZED ≠ CERTIFIED ≠ PRODUCTION`

A repeated name, a machine key, a documentation page, a code reference, a passing census scan or an inferred family/layer/job assignment never manufactures maturity or authority.

Unknown identities enter `CANDIDATE_DISCOVERY` and remain fail-closed until external canonicalization determines whether the observation is a distinct Penta, alias, primitive, subcomponent, compatibility name, typo, superseded name or other governed disposition.

## 3. Pentagonal and operational coordinates

PentaCensus itself is classified as:

- **Pentagonal axis:** Truth — it observes and reconciles identity/state representation.
- **Primary family:** Intelligence, Research & Impact.
- **Primary layers:** Control & Governance; Data, Knowledge & Semantics.
- **Primary jobs:** Analyze & Research; Document; Govern.
- **Lifecycle:** Discover → Govern → Evolve, with verification before any state promotion.
- **Audiences:** agents/Pentas, developers, owners/admins, auditors/governance reviewers.

Those coordinates are routing metadata, not authority.

## 4. Governed discovery sources

Version 1 scans explicit Penta identity references in these repository source classes:

- `data/penta/**`
- `penta/registry/**`
- `runtime/**`
- `scripts/**`
- `.github/workflows/**`

Generated high-volume machine corpora are excluded from evidence collection where they would merely repeat existing projections. The scanner limits itself to UTF-8 JSON, Python, Markdown/MDX and YAML source within a bounded file-size ceiling.

Future source adapters may include ThriveBase, Drive, Sheets, provider registries, other CrownThrive repositories and approved crawler surfaces, but each adapter must have its own authority, privacy, freshness and evidence contract before it can affect census results.

## 5. Discovery grammar

PentaCensus currently recognizes two explicit identity forms:

1. **Display symbols:** CamelCase names matching `Penta*`, such as `PentaRoute` or `PentaCensus`.
2. **Machine keys:** governed keys beginning `penta.`, such as `penta.route` or `penta.census`.

The scanner deliberately does not treat arbitrary natural-language phrases containing the word "Penta" as new systems. Ambiguous prose remains a PentaScribe/PentaPology semantic-discovery problem rather than being silently institutionalized.

## 6. Known identity set

PentaCensus resolves the known set from:

- `data/penta/namespace-census.v1.json`, including canonical, alias, extension and candidate identities already preserved by PentaDocs; and
- governed `data/penta/systems*.json` extension records, which may exist outside the frozen canonical Penta OS registry.

Recognizing a governed extension as "known" does not make it canonical. It only prevents the same extension from being rediscovered as an unknown string every scan.

## 7. Discovery result

Each census run produces a deterministic report with:

- known namespace identity count;
- known machine-key count;
- scanned-file count;
- unknown display-symbol count;
- unknown machine-key count;
- exact evidence paths for each unknown observation;
- a SHA-256 digest of the scanned source set;
- the fail-closed handoff route; and
- explicit non-authority declarations.

No wall-clock timestamp is included in the deterministic core report. Runtime wrappers may attach observation time separately without changing the source-derived result.

## 8. Handoff and canonicalization

Unknown observations route to:

1. **PentaScribe** — terminology, spelling, alias and semantic continuity.
2. **PentaPology** — topology and system/subcomponent/primitive disposition.
3. **PentaDocs** — candidate preservation and human/machine documentation.
4. **PentaAssure / PentaCertify** — independent evidence and maturity checks when implementation is proposed.

PentaCensus has no self-registration, self-certification, self-promotion, merge, release or provider-write authority.

## 9. CI enforcement

The PentaCensus workflow is a namespace drift gate. It runs the deterministic unit tests and then performs a repository census.

If an explicit new Penta symbol or machine key appears in governed sources without a corresponding known namespace or extension record, the census returns non-zero and prints the exact unknown identity and evidence paths. The correct repair is to classify/preserve the name or remove the unintended reference—not to weaken the scanner.

This makes new Penta creation visible at source-introduction time.

## 10. Agent ingestion

Agents should use PentaCensus for **discovery and reconciliation**, not execution routing by itself.

Agent procedure:

1. read the current Pentagonal reference/agent-knowledge corpus;
2. invoke/read PentaCensus when namespace drift or an unknown `Penta*` reference is encountered;
3. if the identity is known, continue through the canonical machine record and current readiness/authority path;
4. if the identity is `CANDIDATE_DISCOVERY`, stop independent execution;
5. route the observation to semantic/topology/documentation governance;
6. resume only after a canonical or governed-extension disposition exists; and
7. still re-check readiness, authority, dependencies and provider bindings before any material action.

An agent must never infer authority from census confidence or frequency of observation.

## 11. Inputs and outputs

### Inputs

- repository filesystem source classes listed above;
- namespace census;
- governed Penta extension registries.

### Outputs

- deterministic discovery report;
- process exit status (`0` = no unknown observations, `2` = unresolved namespace drift);
- evidence paths and source-set SHA-256 digest.

PentaCensus does not mutate the canonical registry or candidate seed in v1.

## 12. Reliability and failure handling

PentaCensus fails closed on malformed required namespace JSON. Unreadable/non-UTF-8 optional scan files are skipped rather than treated as identities. Oversized generated corpora are excluded by policy.

A census failure means the namespace state is not proven clean. It must not be reinterpreted as "zero new Pentas."

The scanner is deterministic for the same source tree. Source changes intentionally change the source digest and may change observations.

## 13. Security and privacy

The v1 implementation reads repository-local public-safe source only. It does not read environment secrets, provider credentials, Vault plaintext, private customer data or unrestricted external targets.

Future private-source adapters require explicit credential references, least privilege, redaction/sanitization, evidence retention, and CHLOM/privacy controls. Raw secrets may never be emitted in a census report.

## 14. Production promotion gate

PentaCensus starts as `implemented`, not `production`.

Promotion requires all of the following on the exact candidate/current-main boundary:

- PentaCensus focused tests pass;
- Penta Portal Docs deterministic generation converges;
- registry, family, interoperability, security and governance gates pass;
- governed PR merge reaches current `main`;
- a main-branch PentaCensus workflow completes successfully;
- PentaAssure/PentaCertify evidence independently confirms the bounded discovery contract; and
- the extension record is updated with exact production evidence rather than a prose assertion.

## 15. Public projection drift

PentaCensus may identify that a public surface refers to stale Penta terminology or state, but it does not edit third-party/public CMS content unless a separately certified provider adapter grants that write capability.

Public projection reconciliation remains downstream of CrownThrive OS truth. A stale website is a projection defect; it does not redefine OS state.

## 16. Evolution roadmap

Planned bounded evolution includes:

- cross-repository census adapters;
- PentaCensus handoff envelopes to PentaScribe/PentaPology;
- machine-readable candidate queue receipts;
- historical alias/supersession analytics;
- census delta reports between exact release SHAs;
- family/layer/job/lifecycle/audience coverage metrics;
- orphaned machine-key detection;
- stale documentation/runtime identity reconciliation; and
- approved PentaCrawler integration for broader discovery without unbounded external scanning.

Every expansion preserves the central invariant: **discovery increases awareness, not authority.**
