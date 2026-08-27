import assert from 'node:assert/strict';
import { PentaEconomicProtocol } from './index.mjs';

const N = Number(process.env.PENTA_STRESS_N || 25000);
const protocol = new PentaEconomicProtocol({
  rates: { route: 2, release: 5 },
  budgets: { PentaRoute: N * 2 + 100, PentaRelease: N * 5 + 100 },
  oracleSecret: 'ci-stress-secret'
});
const cookie = protocol.issueOracleCookie('CHLOM:stress');
const start = performance.now();
for (let i = 0; i < N; i++) protocol.execute({ idempotencyKey: `route:${i}`, penta: 'PentaRoute', operation: 'route', oracleCookie: cookie, releaseId: 'stress-release' });
for (let i = 0; i < Math.min(N, 5000); i++) {
  const a = protocol.execute({ idempotencyKey: `route:${i}`, penta: 'PentaRoute', operation: 'route', oracleCookie: cookie, releaseId: 'stress-release' });
  const b = protocol.execute({ idempotencyKey: `route:${i}`, penta: 'PentaRoute', operation: 'route', oracleCookie: cookie, releaseId: 'stress-release' });
  assert.equal(a.hash, b.hash);
}
assert.throws(() => protocol.execute({ idempotencyKey: 'bad-cookie', penta: 'PentaRoute', operation: 'route', oracleCookie: `${cookie}x`, releaseId: 'stress-release' }), /ORACLE_COOKIE_INVALID/);
assert.throws(() => protocol.execute({ idempotencyKey: 'no-rate', penta: 'PentaRoute', operation: 'unknown', oracleCookie: cookie, releaseId: 'stress-release' }), /RATE_UNAVAILABLE/);
assert.throws(() => protocol.execute({ idempotencyKey: 'over-budget', penta: 'UnknownPenta', operation: 'route', oracleCookie: cookie, releaseId: 'stress-release' }), /BUDGET_EXCEEDED/);
assert.equal(protocol.verifyLedger(), true);
const economics = protocol.releaseEconomics('stress-release');
assert.equal(economics.transactions, N);
assert.equal(economics.total, N * 2);
const elapsedMs = performance.now() - start;
console.log(JSON.stringify({ status: 'PASS', transactions: N, duplicateReplays: Math.min(N,5000), ledgerVerified: true, economics, elapsedMs, txPerSecond: Math.round(N / (elapsedMs / 1000)) }, null, 2));
