# Penta Observability Suite™

**Status:** Production runtime substrate  
**Canonical systems:** PentaError™, PentaLogger™, PentaTrace™, PentaMetric™  
**Doctrine:** Discover → Govern → Execute → Verify → Preserve

Penta Observability Suite is the shared error, logging, trace-correlation, metric, retry-evidence, and dead-letter substrate for CrownThrive PENTA runtimes. It is intentionally provider-neutral and stdlib-only so that any registered runtime can emit consistent evidence before a provider-specific telemetry route exists.

## Systems

### PentaError™
PentaError defines canonical typed failures, safe public envelopes, severity, retryability, status mapping, bounded context, cause lineage, and dead-letter evidence. Internal messages are never required to cross a public boundary.

Schema: `ct.penta.error.v1`

### PentaLogger™
PentaLogger emits deterministic JSON-line operational evidence with service/member identity, severity, event name, UTC timestamp, trace context, bounded contextual fields, normalized exception evidence, and mandatory redaction.

Schema: `ct.penta.log.v1`

### PentaTrace™
PentaTrace supplies `trace_id`, `correlation_id`, `span_id`, and `parent_span_id`, with context-scoped propagation and child-span creation. Correlation is lineage, not permission.

### PentaMetric™
PentaMetric records thread-safe local counters, gauges, duration observations, and deterministic snapshots. External export remains a separate provider capability.

Schema: `ct.penta.metrics.v1`

## Supporting runtime contracts

- `RetryPolicy` evaluates a canonical PentaError against bounded attempt and error-code policy.
- `guard_call` wraps one operation with start/success/failure logs, normalized errors, trace continuity, and success/failure/duration metrics.
- `dead_letter_payload` emits a redacted `ct.penta.dead-letter.v1` payload suitable for a separately authorized queue/archive route.
- The built-in self-test emits `ct.penta.observability.self-test.v1` and validates structured logging, redaction, trace propagation, guarded execution, error envelopes, retry semantics, dead-letter redaction, and metrics.

## Redaction rules

Redaction is mandatory before serialization. The runtime recursively redacts common credential and secret fields including authorization data, cookies, passwords, secrets, tokens, API keys, private keys, stream keys, and webhook secrets. It also scrubs common bearer/API/token-shaped values from free-form strings.

PentaLogger and PentaError must not be used as secret stores. A secret reference or provider alias may be logged when policy allows; secret material may not.

## Authority boundary

Observability creates evidence. It does **not** create authority.

PentaError may classify a failure as retryable, but the retry still requires the workflow/provider policy that owns retry authority. PentaLogger may produce an alert-worthy event, but sending an email, page, webhook, or provider write still requires a certified route. PentaMetric may expose degradation, but remediation, rollback, scaling, or provider mutation remains governed by CHLOM and the accountable runtime/provider controls.

## Production wiring

Repository-native surfaces:

- `runtime/penta_observability.py` — shared implementation
- `runtime/penta_error.py` — PentaError import surface
- `runtime/penta_logger.py` — PentaLogger import surface
- `runtime/penta_trace.py` — PentaTrace import surface
- `runtime/penta_metric.py` — PentaMetric import surface
- `data/penta/systems.extensions.observability.json` — institutional registry and maturity state
- `tests/test_penta_observability.py` — runtime behavioral certification
- `.github/workflows/penta-observability-production.yml` — PR/main certification and production readback gate

The existing Penta Runtime Suite discovers implementation signals by canonical machine-key filename and therefore recognizes these runtime surfaces without a separate hard-coded promotion path. Registry maturity plus implementation evidence are both required; downstream provider/authority/readback gates still apply.

## Production verification

The production workflow must prove all of the following before the suite is treated as healthy:

1. Penta observability unit tests pass.
2. Existing Penta Runtime Suite tests still pass.
3. The observability self-test returns `status: pass`.
4. Runtime Suite gates pass for `penta.error`, `penta.logger`, `penta.trace`, and `penta.metric`.
5. Runtime modules compile under the production Python baseline.
6. After merge, the same workflow executes against `main` to provide repository readback of the production state.

A post-registration certification PR is used when the workflow is introduced for the first time, ensuring the now-default-branch workflow validates the exact production runtime before final certification readback. A follow-up synchronization commit may be used to force a fresh PR event after GitHub has registered the new default-branch workflow.

## Integration pattern

```python
from penta_observability import MetricRegistry, PentaError, PentaLogger, guard_call

logger = PentaLogger(service="my-runtime", penta_member="penta.example")
metrics = MetricRegistry()


def work():
    # bounded operation
    return {"status": "ok"}

result = guard_call(logger, "example.work", work, metrics=metrics)
```

Provider-facing adapters should translate provider exceptions into stable PentaError codes at their boundary, then log the normalized error with PentaLogger. Never expose raw provider payloads by default.

## Operational rule

Every consequential PENTA runtime should converge toward the same invariant:

**One operation → one correlation lineage → structured evidence → safe failure semantics → measurable outcome → preserved verification.**
