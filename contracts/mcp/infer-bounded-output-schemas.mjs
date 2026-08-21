#!/usr/bin/env node
import fs from 'node:fs';

const inputPath = process.argv[2];
if (!inputPath) {
  console.error('usage: node infer-bounded-output-schemas.mjs <captured-results.json>');
  process.exit(2);
}
const captured = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
if (!Array.isArray(captured)) throw new Error('captured results must be an array');

function mergeSchemas(a, b) {
  if (!a) return b;
  if (!b) return a;
  if (JSON.stringify(a) === JSON.stringify(b)) return a;
  const candidates = [];
  const push = (s) => {
    if (s?.anyOf && Array.isArray(s.anyOf)) for (const x of s.anyOf) push(x);
    else if (!candidates.some((x) => JSON.stringify(x) === JSON.stringify(s))) candidates.push(s);
  };
  push(a); push(b);
  return { anyOf: candidates };
}

function infer(value, depth = 0) {
  if (depth > 10) return { type: ['object', 'array', 'string', 'number', 'boolean', 'null'] };
  if (value === null) return { type: 'null' };
  if (Array.isArray(value)) {
    let itemSchema = null;
    for (const item of value.slice(0, 100)) itemSchema = mergeSchemas(itemSchema, infer(item, depth + 1));
    return { type: 'array', maxItems: 500, items: itemSchema || {} };
  }
  if (typeof value === 'object') {
    const properties = {};
    for (const [key, child] of Object.entries(value).slice(0, 256)) properties[key] = infer(child, depth + 1);
    return { type: 'object', properties, additionalProperties: false, maxProperties: 256 };
  }
  if (typeof value === 'string') return { type: 'string', maxLength: 100000 };
  if (typeof value === 'number') return Number.isInteger(value) ? { type: 'integer' } : { type: 'number' };
  if (typeof value === 'boolean') return { type: 'boolean' };
  return {};
}

const out = {};
for (const row of captured) {
  const toolName = row?.tool_name;
  const structured = row?.structuredContent;
  if (typeof toolName !== 'string' || !structured || typeof structured !== 'object') throw new Error('each capture requires tool_name and structuredContent');
  const inferredData = infer(structured.data);
  out[toolName] = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    type: 'object',
    required: ['service', 'operation', 'provider_status', 'ok', 'data', 'evidence'],
    properties: {
      service: { const: structured.service },
      operation: { const: structured.operation },
      provider_status: { type: 'integer', minimum: 100, maximum: 599 },
      ok: { const: true },
      data: inferredData,
      evidence: {
        type: 'object',
        required: ['response_sha256', 'latency_ms', 'retrieved_at', 'timezone'],
        properties: {
          response_sha256: { type: 'string', pattern: '^[0-9a-f]{64}$' },
          latency_ms: { type: 'integer', minimum: 0, maximum: 120000 },
          retrieved_at: { type: 'string' },
          timezone: { const: 'UTC' }
        },
        additionalProperties: false
      }
    },
    additionalProperties: false
  };
}
process.stdout.write(`${JSON.stringify(out, null, 2)}\n`);
