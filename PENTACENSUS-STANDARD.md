# PentaCensus Continuous Namespace Standard

**Standard ID:** `ct.standard.penta.census.v1`  
**Version:** `1.2.0`  
**System identity:** `PentaCensus` / `penta.census`  
**Primary family:** Intelligence, Research & Impact  
**Pentagonal axis:** Truth  
**Initial maturity:** `implemented` governed extension; not yet production-promoted

## 1. Purpose

PentaCensus is the governed namespace-discovery and reconciliation capability for the CrownThrive Penta architecture. Its job is to keep the institutional Penta census from becoming a stale manual list as code, registries, workflows, runtime modules and governed extensions evolve.

PentaCensus continuously answers:

1. Which Penta identities are already known?
2. Which object-scoped institutional identity declarations appear in governed registry/data sources but are not represented in the current namespace?
3. Which unstructured `Penta*` symbols appear in runtime, scripts or workflows and therefore deserve semantic/topology review without being presumed to be systems?
4. Where is the exact source evidence for each observation?
5. Which canonicalization/governance lane must receive unresolved discoveries?

PentaCensus never decides by itself whether a newly observed name is allowed to execute.

## 2. State invariant

`OBSERVED ≠ DECLARED IDENTITY ≠ CANONICAL ≠ IMPLEMENTED ≠ EXECUTION-ELIGIBLE ≠ AUTHORIZED ≠ CERTIFIED ≠ PRODUCTION`

A repeated name, machine-looking key, documentation page, code class, event name, metric name, passing census scan or inferred family/layer/job assignment never manufactures maturity or authority.

Unknown structured identity declarations enter `CANDIDATE_DISCOVERY` and fail the census gate. Unknown unstructured code/workflow symbols enter `SEMANTIC_REVIEW_PENDING`; they are evidence for PentaScribe/PentaPology review, not automatic Penta identities.

## 3. Pentagonal and operational coordinates

PentaCensus itself is classified as:

- **Pentagonal axis:** Truth — it observes and reconciles identity/state representation.
- **Primary family:** Intelligence, Research & Impact.
- **Primary layers:** Control & Governance; Data, Knowledge & Semantics.
- **Primary jobs:** Analyze & Research; Document; Govern.
- **Lifecycle:** Discover → Govern → Evolve, with verification before any state promotion.
- **Audiences:** agents/Pentas, developers, owners/admins, auditors/governance reviewers.

Those coordinates are routing metadata, not authority.

## 4. Governed discovery planes

Version 1.2 separates discovery into two planes and makes the hard plane object-scoped.

### Hard-gated declaration plane

Structured JSON under:

- `data/penta/**`
- `penta/registry/**`

is parsed semantically. A Penta identity is hard-gated only when one of these institutional declaration forms exists:

1. **Same-object machine identity** — a simple `penta.<key>` value appears in `machine_key` or `canonical_machine_key`; a same-object single-token `PentaName` in `canonical_name` is its display identity.
2. **Root Penta registry identity** — the document root has a registry ID matching the `ct.penta.*.vN` registry family and a single-token `PentaName` canonical name.

A new institutional declaration must already resolve to the current namespace, candidate preservation source or a governed extension. Otherwise PentaCensus fails closed and reports the exact source path.

The declaration grammar deliberately does **not** treat these as automatic Penta identities:

- family/composite display names such as `Penta ... Family`;
- `system_key`-only component bridges;
- event and metric keys;
- catalog IDs;
- dotted workflow/status signals; or
- runtime helper/client/error symbols.

### Advisory reference plane

UTF-8 source under:

- `runtime/**`
- `scripts/**`
- `.github/workflows/**`

is scanned for unknown CamelCase `Penta*` symbols. These observations are advisory because they can legitimately be exception classes, clients, configs, fixtures, helpers, runtime wrappers or compatibility names rather than institutional Pentas.

The first live census proved why this distinction is required: a raw lexical sweep surfaced exception classes such as `PentaContextError`, event/metric-like `penta.*` values, family display names and real missing registry identities together. The corrected contract preserves the evidence while preventing namespace pollution.

Generated high-volume machine corpora are excluded from evidence collection where they would merely repeat existing projections. The scanner uses a bounded file-size ceiling.

Future adapters may include ThriveBase, Drive, Sheets, provider registries, other CrownThrive repositories and approved crawler surfaces, but each adapter requires its own authority, privacy, freshness and evidence contract before it may affect the hard-gated declaration result.

## 5. Known identity set

PentaCensus resolves the known set from:

- `data/penta/namespace-census.v1.json`, the deterministic PentaDocs projection;
- `data/penta/namespace-candidates.v1.json`, the governed candidate/reference preservation source; and
- governed `data/penta/systems*.json` extension records, which may exist outside the frozen canonical Penta OS registry.

The candidate seed is read directly because it can legitimately advance one commit before PentaDocs regenerates the namespace census. That temporal ordering must not create a false drift failure.

Recognizing a candidate or governed extension as known does not make it canonical, execution-eligible, certified or production. It only establishes that the identity has already entered a governed preservation/disposition lane.

## 6. Discovery and canonicalization example

The initial production-oriented census found `PentaProvision` as a root `ct.penta.provision.v1` registry identity while the 406-identity PentaDocs snapshot did not preserve it. Existing merged runtime/registry evidence supports preserving the name, but the current source does not establish an authoritative `penta.provision` machine key.

Accordingly, PentaCensus routes `PentaProvision` into the candidate preservation source with its evidence note instead of inventing a machine key or silently modifying the frozen Penta OS V1.5 canonical registry.

By contrast, `PentaMarketer Persona Execution Bridge` is a component record with a `system_key`, not an independent Penta identity declaration under this grammar. Family names are likewise taxonomy objects rather than child Penta identities.

This distinction is the core purpose of PentaCensus: preserve what is real, classify what is ambiguous, and invent nothing.

## 7. Discovery result

Each census run produces a deterministic report with:

- known namespace identity count;
- known machine-key count;
- scanned-file count;
- unknown structured display-identity declarations;
- unknown structured machine-identity declarations;
- advisory unstructured symbol references;
- exact evidence paths;
- the active identity grammar;
- a SHA-256 digest of the scanned source set;
- fail-closed/advisory handoff states; and
- explicit non-authority declarations.

No wall-clock timestamp is included in the deterministic core report. Runtime wrappers may attach observation time separately without changing the source-derived result.

## 8. Handoff and canonicalization

Unknown observations route to:

1. **PentaScribe** — terminology, spelling, alias and semantic continuity.
2. **PentaPology** — topology and system/subcomponent/primitive disposition.
3. **PentaDocs** — candidate preservation and human/machine documentation.
4. **PentaAssure / PentaCertify** — independent evidence and maturity checks when implementation is proposed.

A structured declaration that lacks namespace resolution is a hard HOLD. An advisory reference is not a HOLD by itself, but it remains visible for semantic/topology disposition.

PentaCensus has no self-registration, self-certification, self-promotion, merge, release or provider-write authority.

## 9. CI enforcement

The PentaCensus workflow runs deterministic unit tests and then performs the repository census.

The CI job fails only when an **object-scoped institutional identity declaration** is unresolved. It does not fail merely because runtime source contains an unknown `Penta*` class/helper symbol. Advisory references are printed and retained as review evidence.

The correct repair for an unresolved declaration is to classify/preserve the identity, bind it to an established identity, or remove an unintended declaration—not to suppress the observation.

This makes institutional Penta creation visible at source-introduction time while avoiding false canonicalization.

## 10. Agent ingestion

Agents should use PentaCensus for **discovery and reconciliation**, not execution routing by itself.

Agent procedure:

1. read the current Pentagonal reference/agent-knowledge corpus;
2. consult PentaCensus when namespace drift or an unknown `Penta*` reference is encountered;
3. if the identity is known, continue through the canonical machine record and current readiness/authority path;
4. if it is an unresolved structured declaration (`CANDIDATE_DISCOVERY`), stop independent execution;
5. if it is only an advisory reference (`SEMANTIC_REVIEW_PENDING`), do not assume it is a Penta; route semantic/topology review when material;
6. if the identity is candidate-preserved, use that record only for discovery/canonicalization and do not infer execution eligibility;
7. resume execution only through a canonical or independently authorized governed-extension disposition; and
8. re-check readiness, authority, dependencies and provider bindings before material action.

An agent must never infer authority from census confidence, frequency of observation or semantic similarity.

## 11. Inputs and outputs

### Inputs

- repository structured registry/data source classes;
- runtime/script/workflow reference source classes;
- generated namespace census;
- candidate preservation seed;
- governed Penta extension registries.

### Outputs

- deterministic discovery report;
- process exit status (`0` = no unresolved institutional declarations; `2` = unresolved institutional declaration drift);
- advisory semantic-reference queue;
- evidence paths and source-set SHA-256 digest.

PentaCensus v1.2 itself does not mutate the canonical registry. Canonicalization/preservation remains an explicit governed source change reviewed through the normal repository lifecycle.

## 12. Reliability and failure handling

PentaCensus fails closed on malformed required namespace/candidate JSON. Unreadable/non-UTF-8 optional reference files are skipped rather than treated as identities. Oversized generated corpora are excluded by policy.

A hard census failure means institutional namespace declaration convergence is not proven clean. It must not be reinterpreted as zero new Pentas.

Advisory reference observations may be numerous and require semantic disposition; their existence does not independently invalidate canonical registry integrity.

The scanner is deterministic for the same source tree. Source changes intentionally change the source digest and may change observations.

## 13. Security and privacy

The v1.2 implementation reads repository-local public-safe source only. It does not read environment secrets, provider credentials, Vault plaintext, private customer data or unrestricted external targets.

Future private-source adapters require explicit credential references, least privilege, redaction/sanitization, evidence retention, and CHLOM/privacy controls. Raw secrets may never be emitted in a census report.

## 14. Production promotion gate

PentaCensus starts as `implemented`, not `production`.

Promotion requires all of the following on the exact candidate/current-main boundary:

- focused PentaCensus tests pass;
- strict object-scoped declaration census is clean;
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

- cross-repository declaration census adapters;
- machine-readable semantic-review disposition records;
- PentaCensus handoff envelopes to PentaScribe/PentaPology;
- historical alias/supersession analytics;
- census delta reports between exact release SHAs;
- family/layer/job/lifecycle/audience coverage metrics;
- orphaned machine-key detection;
- stale documentation/runtime identity reconciliation; and
- approved PentaCrawler integration for broader discovery without unbounded external scanning.

Every expansion preserves the central invariant: **discovery increases awareness, not authority.**
