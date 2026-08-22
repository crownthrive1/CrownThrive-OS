import { createHash } from 'node:crypto';

// CONTROLLED-TEST REFERENCE UTILITY.
// Deterministic JSON and SHA-256 helpers only. No signing, custody, network I/O, or value movement.

const FORBIDDEN_METADATA_KEY = /(password|passphrase|secret|token|api[_-]?key|private[_-]?key|mnemonic|seed[_-]?phrase|provider[_-]?ref|credential[_-]?raw)/i;
const SECRET_SHAPE = /(sk_live_[A-Za-z0-9]{16,}|rk_live_[A-Za-z0-9]{16,}|whsec_[A-Za-z0-9]{16,}|sb_secret_[A-Za-z0-9._-]{16,}|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----)/;

export function canonicalize(value) {
  if (value === null) return 'null';
  if (typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new Error('canonical_number_must_be_finite');
    if (Object.is(value, -0)) return '0';
    return JSON.stringify(value);
  }
  if (typeof value === 'bigint') throw new Error('canonical_bigint_not_supported');
  if (Array.isArray(value)) return `[${value.map((entry) => canonicalize(entry)).join(',')}]`;
  if (typeof value === 'object') {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) throw new Error('canonical_plain_object_required');
    const keys = Object.keys(value).sort();
    return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(',')}}`;
  }
  throw new Error('canonical_value_type_unsupported');
}

export function sha256Hex(value) {
  const bytes = Buffer.isBuffer(value) || value instanceof Uint8Array
    ? value
    : Buffer.from(String(value), 'utf8');
  return createHash('sha256').update(bytes).digest('hex');
}

export function assertHex64(value, code = 'digest_invalid') {
  if (typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value)) throw new Error(code);
  return value;
}

export function assertAsciiIdentifier(value, code, maxLength = 128) {
  if (typeof value !== 'string' || value.length < 1 || value.length > maxLength || !/^[A-Za-z0-9._:@/-]+$/.test(value)) {
    throw new Error(code);
  }
  return value;
}

export function assertIsoTimestamp(value, code = 'timestamp_invalid') {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) throw new Error(code);
  if (!Number.isFinite(Date.parse(value))) throw new Error(code);
  return value;
}

export function assertSanitizedMetadata(value, { maxBytes = 2048 } = {}) {
  if (value === undefined) return {};
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new Error('public_metadata_object_required');
  const walk = (entry, path = '') => {
    if (entry === null || typeof entry === 'boolean' || typeof entry === 'number') return;
    if (typeof entry === 'string') {
      if (SECRET_SHAPE.test(entry)) throw new Error('public_metadata_secret_shape_detected');
      return;
    }
    if (Array.isArray(entry)) {
      if (entry.length > 64) throw new Error('public_metadata_array_too_large');
      entry.forEach((child, index) => walk(child, `${path}[${index}]`));
      return;
    }
    if (typeof entry === 'object') {
      const prototype = Object.getPrototypeOf(entry);
      if (prototype !== Object.prototype && prototype !== null) throw new Error('public_metadata_plain_object_required');
      for (const [key, child] of Object.entries(entry)) {
        if (FORBIDDEN_METADATA_KEY.test(key)) throw new Error('public_metadata_forbidden_key');
        walk(child, path ? `${path}.${key}` : key);
      }
      return;
    }
    throw new Error('public_metadata_value_type_unsupported');
  };
  walk(value);
  const canonical = canonicalize(value);
  if (Buffer.byteLength(canonical, 'utf8') > maxBytes) throw new Error('public_metadata_too_large');
  return value;
}

export function frameAscii(parts) {
  if (!Array.isArray(parts) || parts.length === 0) throw new Error('frame_parts_required');
  return parts.map((part) => {
    const value = String(part);
    if (!/^[\x20-\x7E]*$/.test(value)) throw new Error('frame_ascii_required');
    return `${Buffer.byteLength(value, 'ascii')}:${value}`;
  }).join('|');
}

export function secretShapePresent(value) {
  return SECRET_SHAPE.test(typeof value === 'string' ? value : canonicalize(value));
}
