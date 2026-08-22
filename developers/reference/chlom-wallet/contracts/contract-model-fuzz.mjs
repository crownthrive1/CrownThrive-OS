import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(fileURLToPath(import.meta.url));
const source = (name) => readFileSync(join(ROOT, name), 'utf8');

// This is a deterministic source-aligned state-machine fuzz model, not EVM execution.
// The separate solc gate proves compilation. A later testnet/EVM suite remains required.

let seed = 0x5eedc0de;
const next = () => {
  seed ^= seed << 13; seed >>>= 0;
  seed ^= seed >>> 17; seed >>>= 0;
  seed ^= seed << 5; seed >>>= 0;
  return seed >>> 0;
};
const pick = (n) => next() % n;
const id = (prefix, i) => `${prefix}:${i}`;
const nonzero = (value) => value !== '' && value !== '0x0' && value !== null && value !== undefined;

class AnchorModel {
  constructor() { this.paused = false; this.anchors = new Map(); }
  anchor(batchId, rootDigest, policyDigest) {
    if (this.paused) throw new Error('Paused');
    if (![batchId, rootDigest, policyDigest].every(nonzero)) throw new Error('ZeroValue');
    if (this.anchors.has(batchId)) throw new Error('AlreadyAnchored');
    this.anchors.set(batchId, { rootDigest, policyDigest });
  }
}

class EntitlementModel {
  constructor() { this.paused = false; this.records = new Map(); }
  record(entitlementId, subjectDigest, assetDigest, termsDigest, validFrom, validUntil) {
    if (this.paused) throw new Error('Paused');
    if (![entitlementId, subjectDigest, assetDigest, termsDigest].every(nonzero)) throw new Error('ZeroValue');
    if (validUntil !== 0 && validUntil <= validFrom) throw new Error('ZeroValue');
    if (this.records.has(entitlementId)) throw new Error('Exists');
    this.records.set(entitlementId, { validFrom, validUntil, state: 'Active' });
  }
  revoke(entitlementId, reasonDigest) {
    const row = this.records.get(entitlementId);
    if (!row) throw new Error('Missing');
    if (row.state !== 'Active') throw new Error('InvalidState');
    if (!nonzero(reasonDigest)) throw new Error('ZeroValue');
    row.state = 'Revoked';
  }
  isActive(entitlementId, atTime) {
    const row = this.records.get(entitlementId);
    return Boolean(row && row.state === 'Active' && atTime >= row.validFrom && (row.validUntil === 0 || atTime < row.validUntil));
  }
}

const validateBps = (bps) => Array.isArray(bps) && bps.length > 0 && bps.length <= 64 && bps.every((v) => Number.isInteger(v) && v >= 0 && v <= 10000) && bps.reduce((a, b) => a + b, 0) === 10000;
class SplitModel {
  constructor() { this.paused = false; this.policies = new Map(); }
  record(policyId, scheduleDigest, bps) {
    if (this.paused) throw new Error('Paused');
    if (![policyId, scheduleDigest].every(nonzero)) throw new Error('ZeroValue');
    if (!validateBps(bps)) throw new Error('InvalidBps');
    if (this.policies.has(policyId)) throw new Error('Exists');
    this.policies.set(policyId, { scheduleDigest, legCount: bps.length, superseded: false });
  }
  supersede(policyId, replacementPolicyId) {
    if (!nonzero(replacementPolicyId)) throw new Error('ZeroValue');
    if (policyId === replacementPolicyId) throw new Error('SelfReplacement');
    if (!this.policies.has(policyId) || !this.policies.has(replacementPolicyId)) throw new Error('Missing');
    this.policies.get(policyId).superseded = true;
  }
}

class ThriveFundModel {
  constructor() { this.paused = false; this.obligations = new Map(); }
  record(obligationId, sourceDigest, programDigest, assetDigest, amountMinor) {
    if (this.paused) throw new Error('Paused');
    if (![obligationId, sourceDigest, programDigest, assetDigest].every(nonzero) || !Number.isSafeInteger(amountMinor) || amountMinor <= 0) throw new Error('ZeroValue');
    if (this.obligations.has(obligationId)) throw new Error('Exists');
    this.obligations.set(obligationId, { amountMinor, state: 'Recorded' });
  }
  settle(obligationId, evidenceDigest) {
    const row = this.obligations.get(obligationId);
    if (!row) throw new Error('Missing');
    if (row.state !== 'Recorded') throw new Error('InvalidState');
    if (!nonzero(evidenceDigest)) throw new Error('ZeroValue');
    row.state = 'SettledExternally';
  }
  reverse(obligationId, evidenceDigest) {
    const row = this.obligations.get(obligationId);
    if (!row) throw new Error('Missing');
    if (row.state === 'Reversed') throw new Error('InvalidState');
    if (!nonzero(evidenceDigest)) throw new Error('ZeroValue');
    row.state = 'Reversed';
  }
}

// Source guards ensure the fuzz model does not drift away from the hardened source invariants.
const splitSource = source('ChlomSplitPolicyRegistry.sol');
assert.match(splitSource, /error Missing\(bytes32 policyId\)/);
assert.match(splitSource, /replacementPolicyId == policyId/);
assert.match(splitSource, /_policies\[replacementPolicyId\]\.createdAt == 0/);
const entitlementSource = source('ChlomEntitlementRegistry.sol');
assert.match(entitlementSource, /reasonDigest == bytes32\(0\)/);
assert.match(entitlementSource, /e\.state != State\.Active/);
const thriveSource = source('ThriveFundObligationRegistry.sol');
assert.match(thriveSource, /amountMinor == 0/);
assert.match(thriveSource, /evidenceDigest == bytes32\(0\)/);
assert.match(thriveSource, /o\.state == State\.Reversed/);
const anchorSource = source('ChlomAnchorRegistry.sol');
assert.match(anchorSource, /AlreadyAnchored/);
assert.doesNotMatch(anchorSource + splitSource + entitlementSource + thriveSource, /call\s*\{\s*value|\.transfer\(|\.send\(|delegatecall|selfdestruct/);

const anchor = new AnchorModel();
const entitlement = new EntitlementModel();
const split = new SplitModel();
const thrive = new ThriveFundModel();
let expectedRejects = 0;
let operations = 0;

for (let i = 0; i < 25_000; i++) {
  operations++;
  const family = pick(4);
  try {
    if (family === 0) {
      const n = pick(4000);
      const batch = id('batch', n);
      if (pick(7) === 0 && anchor.anchors.has(batch)) anchor.anchor(batch, id('root', n), id('policy', n));
      else anchor.anchor(batch, id('root', n), id('policy', n));
    } else if (family === 1) {
      const n = pick(3000);
      const entitlementId = id('ent', n);
      if (!entitlement.records.has(entitlementId)) {
        const start = pick(10_000);
        const perpetual = pick(4) === 0;
        entitlement.record(entitlementId, id('subject', n), id('asset', n), id('terms', n), start, perpetual ? 0 : start + 1 + pick(1000));
        assert.equal(entitlement.isActive(entitlementId, start), true);
      } else if (entitlement.records.get(entitlementId).state === 'Active') {
        entitlement.revoke(entitlementId, id('reason', n));
        assert.equal(entitlement.isActive(entitlementId, Number.MAX_SAFE_INTEGER), false);
      } else {
        entitlement.revoke(entitlementId, id('reason', n));
      }
    } else if (family === 2) {
      const n = pick(2500);
      const policyId = id('policy', n);
      if (!split.policies.has(policyId)) {
        const a = pick(10001);
        split.record(policyId, id('schedule', n), [a, 10000 - a]);
      } else if (split.policies.size > 1) {
        const keys = [...split.policies.keys()];
        let replacement = keys[pick(keys.length)];
        if (replacement === policyId) replacement = keys[(keys.indexOf(replacement) + 1) % keys.length];
        split.supersede(policyId, replacement);
      }
    } else {
      const n = pick(2500);
      const obligationId = id('obligation', n);
      if (!thrive.obligations.has(obligationId)) thrive.record(obligationId, id('source', n), id('program', n), id('asset', n), 1 + pick(1_000_000));
      else {
        const row = thrive.obligations.get(obligationId);
        if (row.state === 'Recorded' && pick(2) === 0) thrive.settle(obligationId, id('evidence', n));
        else if (row.state !== 'Reversed') thrive.reverse(obligationId, id('evidence', n));
        else thrive.reverse(obligationId, id('evidence', n));
      }
    }
  } catch (error) {
    const expected = ['AlreadyAnchored','Exists','InvalidState'].includes(error?.message);
    if (!expected) throw error;
    expectedRejects++;
  }
}

// Directed negative cases.
assert.throws(() => split.record('bad-bps', 'schedule', [9999]), /InvalidBps/);
assert.throws(() => split.supersede('missing', 'also-missing'), /Missing/);
const splitKeys = [...split.policies.keys()];
if (splitKeys.length) assert.throws(() => split.supersede(splitKeys[0], splitKeys[0]), /SelfReplacement/);
assert.throws(() => thrive.record('zero-obligation', 'source', 'program', 'asset', 0), /ZeroValue/);
const freshObligation = 'directed-obligation';
thrive.record(freshObligation, 'source', 'program', 'asset', 1);
assert.throws(() => thrive.settle(freshObligation, '0x0'), /ZeroValue/);
const freshEntitlement = 'directed-entitlement';
entitlement.record(freshEntitlement, 'subject', 'asset', 'terms', 1, 2);
assert.throws(() => entitlement.revoke(freshEntitlement, '0x0'), /ZeroValue/);

for (const [_, row] of split.policies) assert.ok(row.legCount >= 1 && row.legCount <= 64);
for (const [_, row] of thrive.obligations) assert.ok(row.amountMinor > 0);
for (const [_, row] of entitlement.records) assert.ok(['Active','Revoked'].includes(row.state));

console.log(JSON.stringify({
  result: 'PASS_CONTRACT_MODEL_FUZZ',
  operations,
  expected_rejections: expectedRejects,
  anchors: anchor.anchors.size,
  entitlements: entitlement.records.size,
  split_policies: split.policies.size,
  thrivefund_obligations: thrive.obligations.size,
  no_value_movement_primitives: true,
  evm_execution: false,
  audit_claimed: false,
}));
