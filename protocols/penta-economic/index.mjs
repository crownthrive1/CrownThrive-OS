import crypto from 'node:crypto';

const stable = (v) => JSON.stringify(v, Object.keys(v).sort());
const hash = (v) => crypto.createHash('sha256').update(typeof v === 'string' ? v : stable(v)).digest('hex');

export class PentaEconomicProtocol {
  constructor({ rates = {}, budgets = {}, oracleSecret = 'test-only' } = {}) {
    this.rates = new Map(Object.entries(rates));
    this.budgets = new Map(Object.entries(budgets));
    this.spent = new Map();
    this.receipts = new Map();
    this.oracleSecret = oracleSecret;
    this.sequence = 0;
    this.head = 'GENESIS';
  }

  issueOracleCookie(subject, ttlMs = 60_000) {
    const payload = { subject, exp: Date.now() + ttlMs };
    const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
    const sig = crypto.createHmac('sha256', this.oracleSecret).update(body).digest('hex');
    return `${body}.${sig}`;
  }

  verifyOracleCookie(cookie) {
    if (!cookie || !cookie.includes('.')) return false;
    const [body, sig] = cookie.split('.');
    const expected = crypto.createHmac('sha256', this.oracleSecret).update(body).digest('hex');
    if (sig.length !== expected.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) return false;
    const payload = JSON.parse(Buffer.from(body, 'base64url').toString());
    return payload.exp >= Date.now() ? payload : false;
  }

  quote({ operation, units = 1 }) {
    const rate = Number(this.rates.get(operation));
    if (!Number.isFinite(rate) || rate < 0) throw new Error('RATE_UNAVAILABLE');
    if (!Number.isSafeInteger(units) || units < 1) throw new Error('INVALID_UNITS');
    return { operation, units, rate, total: rate * units, currency: 'execution_unit' };
  }

  execute({ idempotencyKey, penta, operation, units = 1, oracleCookie, releaseId }) {
    if (!idempotencyKey) throw new Error('IDEMPOTENCY_REQUIRED');
    if (this.receipts.has(idempotencyKey)) return this.receipts.get(idempotencyKey);
    const oracle = this.verifyOracleCookie(oracleCookie);
    if (!oracle) throw new Error('ORACLE_COOKIE_INVALID');
    const quote = this.quote({ operation, units });
    const budget = Number(this.budgets.get(penta) ?? 0);
    const spent = Number(this.spent.get(penta) ?? 0);
    if (spent + quote.total > budget) throw new Error('BUDGET_EXCEEDED');
    this.spent.set(penta, spent + quote.total);
    const record = { sequence: ++this.sequence, idempotencyKey, penta, releaseId, oracleSubject: oracle.subject, quote, previousHash: this.head };
    record.hash = hash(record);
    this.head = record.hash;
    const receipt = Object.freeze({ ...record, status: 'settled' });
    this.receipts.set(idempotencyKey, receipt);
    return receipt;
  }

  verifyLedger() {
    let previous = 'GENESIS';
    for (const receipt of this.receipts.values()) {
      if (receipt.previousHash !== previous) return false;
      const { status, hash: receiptHash, ...record } = receipt;
      if (hash(record) !== receiptHash) return false;
      previous = receiptHash;
    }
    return previous === this.head;
  }

  releaseEconomics(releaseId) {
    const rows = [...this.receipts.values()].filter(r => r.releaseId === releaseId);
    return { releaseId, transactions: rows.length, total: rows.reduce((n, r) => n + r.quote.total, 0), currency: 'execution_unit', ledgerHead: this.head };
  }
}
