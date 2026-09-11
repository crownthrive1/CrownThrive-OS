#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';

const API_VERSION = '1';
const DEFAULT_API_BASE = 'https://api.paddle.com';

function parseArgs(argv) {
  const args = { apply: false, manifest: null, receipt: null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--apply') args.apply = true;
    else if (arg === '--manifest') args.manifest = argv[++i];
    else if (arg === '--receipt') args.receipt = argv[++i];
    else if (arg === '--help' || arg === '-h') args.help = true;
    else throw new Error(`unknown_argument:${arg}`);
  }
  return args;
}

function usage() {
  return [
    'Usage: node tools/paddle/sync-catalog.mjs --manifest <path> [--apply] [--receipt <path>]',
    '',
    'Dry-run is the default and requires no credential.',
    'Apply mode requires PADDLE_API_KEY in the server environment.',
    'Optional: PADDLE_API_BASE_URL (defaults to https://api.paddle.com).'
  ].join('\n');
}

function assertManifest(manifest) {
  if (manifest?.contract !== 'ct.paddle.catalog-wave.v1') throw new Error('invalid_contract');
  if (!manifest.wave_id || !Array.isArray(manifest.products) || manifest.products.length === 0) throw new Error('invalid_manifest');
  if (manifest.policy?.destructive_changes !== false) throw new Error('destructive_policy_not_false');

  const stableIds = new Set();
  const priceKeys = new Set();
  for (const product of manifest.products) {
    if (!product.stable_id || !product.name || !product.tax_category) throw new Error('invalid_product');
    if (stableIds.has(product.stable_id)) throw new Error(`duplicate_stable_id:${product.stable_id}`);
    stableIds.add(product.stable_id);
    if (!Array.isArray(product.prices) || product.prices.length === 0) throw new Error(`missing_prices:${product.stable_id}`);
    for (const price of product.prices) {
      const composite = `${product.stable_id}:${price.key}`;
      if (!price.key || !/^\d+$/.test(price.amount_minor || '')) throw new Error(`invalid_price:${composite}`);
      if (priceKeys.has(composite)) throw new Error(`duplicate_price:${composite}`);
      priceKeys.add(composite);
      if (price.billing_cycle !== null) {
        const { interval, frequency } = price.billing_cycle || {};
        if (!['day', 'week', 'month', 'year'].includes(interval) || !Number.isInteger(frequency) || frequency < 1) {
          throw new Error(`invalid_billing_cycle:${composite}`);
        }
      }
    }
  }
}

function sha256(text) {
  return createHash('sha256').update(text).digest('hex');
}

function ctStableId(entity) {
  return entity?.custom_data?.ct_stable_id ?? null;
}

function ctPriceKey(entity) {
  return entity?.custom_data?.ct_price_key ?? null;
}

async function requestJson(url, { method = 'GET', token, body } = {}) {
  const headers = { Accept: 'application/json', 'Paddle-Version': API_VERSION };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = new Error(`paddle_http_${response.status}:${payload?.error?.code || 'unknown_error'}`);
    err.status = response.status;
    err.payload = payload;
    throw err;
  }
  return payload;
}

async function listAll(apiBase, path, token) {
  let nextUrl = new URL(path, apiBase).toString();
  const rows = [];
  while (nextUrl) {
    const payload = await requestJson(nextUrl, { token });
    rows.push(...(payload.data || []));
    const next = payload?.meta?.pagination?.next || null;
    nextUrl = next ? new URL(next, apiBase).toString() : null;
  }
  return rows;
}

async function getEntity(apiBase, type, id, token) {
  return (await requestJson(`${apiBase}/${type}/${id}`, { token })).data;
}

function productPayload(product, waveId) {
  return {
    name: product.name,
    description: product.description ?? null,
    type: 'standard',
    tax_category: product.tax_category,
    custom_data: {
      ...(product.custom_data || {}),
      ct_stable_id: product.stable_id,
      ct_catalog_wave: waveId
    }
  };
}

function pricePayload(productId, product, price, manifest) {
  return {
    product_id: productId,
    description: price.description,
    name: price.name ?? null,
    type: 'standard',
    billing_cycle: price.billing_cycle,
    trial_period: null,
    tax_mode: manifest.policy?.tax_mode || 'account_setting',
    unit_price: { amount: price.amount_minor, currency_code: manifest.currency },
    custom_data: {
      ...(price.custom_data || {}),
      ct_stable_id: product.stable_id,
      ct_price_key: price.key,
      ct_catalog_wave: manifest.wave_id
    }
  };
}

async function sync(manifest, rawManifest, { apply, receiptPath }) {
  const apiBase = (process.env.PADDLE_API_BASE_URL || DEFAULT_API_BASE).replace(/\/$/, '');
  const token = process.env.PADDLE_API_KEY || null;
  if (apply && !token) throw new Error('PADDLE_API_KEY_required_for_apply');

  const receipt = {
    contract: 'ct.paddle.catalog-sync-receipt.v1',
    wave_id: manifest.wave_id,
    mode: apply ? 'apply' : 'dry_run',
    manifest_sha256: sha256(rawManifest),
    provider: 'paddle',
    environment: manifest.environment,
    provider_write: false,
    credential_exposed: false,
    secret_value_returned: false,
    products: [],
    summary: {
      desired_products: manifest.products.length,
      desired_prices: manifest.products.reduce((sum, p) => sum + p.prices.length, 0),
      created_products: 0,
      existing_products: 0,
      created_prices: 0,
      existing_prices: 0,
      holds: 0
    },
    observed_at: new Date().toISOString()
  };

  if (!apply) {
    receipt.state = 'DRY_RUN_PASS';
    receipt.products = manifest.products.map(product => ({
      stable_id: product.stable_id,
      action: 'WOULD_RECONCILE',
      prices: product.prices.map(price => ({ key: price.key, action: 'WOULD_RECONCILE' }))
    }));
    if (receiptPath) await writeFile(resolve(receiptPath), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
    return receipt;
  }

  const currentProducts = await listAll(apiBase, '/products?status=active&per_page=200', token);

  for (const product of manifest.products) {
    const sameStableId = currentProducts.filter(row => ctStableId(row) === product.stable_id);
    const sameNameOtherId = currentProducts.filter(row => row.name === product.name && ctStableId(row) !== product.stable_id);
    const productResult = { stable_id: product.stable_id, name: product.name, prices: [] };

    if (sameStableId.length > 1 || (sameStableId.length === 0 && sameNameOtherId.length > 0)) {
      productResult.action = 'HOLD_CONFLICT';
      productResult.reason = sameStableId.length > 1 ? 'multiple_products_with_stable_id' : 'name_exists_without_matching_stable_id';
      receipt.summary.holds += 1;
      receipt.products.push(productResult);
      continue;
    }

    let providerProduct;
    if (sameStableId.length === 1) {
      providerProduct = sameStableId[0];
      productResult.action = 'EXISTING';
      receipt.summary.existing_products += 1;
    } else {
      const created = await requestJson(`${apiBase}/products`, {
        method: 'POST', token, body: productPayload(product, manifest.wave_id)
      });
      providerProduct = created.data;
      productResult.action = 'CREATED';
      receipt.summary.created_products += 1;
      receipt.provider_write = true;
      currentProducts.push(providerProduct);
    }

    const productReadback = await getEntity(apiBase, 'products', providerProduct.id, token);
    productResult.provider_product_id = productReadback.id;
    productResult.readback = { status: productReadback.status, stable_id: ctStableId(productReadback), name: productReadback.name };

    const currentPrices = await listAll(apiBase, `/prices?status=active&product_id=${encodeURIComponent(providerProduct.id)}&per_page=200`, token);
    for (const price of product.prices) {
      const matches = currentPrices.filter(row => ctPriceKey(row) === price.key && ctStableId(row) === product.stable_id);
      const priceResult = { key: price.key };
      if (matches.length > 1) {
        priceResult.action = 'HOLD_CONFLICT';
        priceResult.reason = 'multiple_prices_with_stable_key';
        receipt.summary.holds += 1;
        productResult.prices.push(priceResult);
        continue;
      }

      let providerPrice;
      if (matches.length === 1) {
        providerPrice = matches[0];
        priceResult.action = 'EXISTING';
        receipt.summary.existing_prices += 1;
      } else {
        const created = await requestJson(`${apiBase}/prices`, {
          method: 'POST', token, body: pricePayload(providerProduct.id, product, price, manifest)
        });
        providerPrice = created.data;
        currentPrices.push(providerPrice);
        priceResult.action = 'CREATED';
        receipt.summary.created_prices += 1;
        receipt.provider_write = true;
      }

      const priceReadback = await getEntity(apiBase, 'prices', providerPrice.id, token);
      priceResult.provider_price_id = priceReadback.id;
      priceResult.readback = {
        status: priceReadback.status,
        stable_id: ctStableId(priceReadback),
        price_key: ctPriceKey(priceReadback),
        amount_minor: priceReadback?.unit_price?.amount,
        currency_code: priceReadback?.unit_price?.currency_code,
        billing_cycle: priceReadback.billing_cycle
      };
      productResult.prices.push(priceResult);
    }

    receipt.products.push(productResult);
  }

  const realizedProducts = receipt.summary.created_products + receipt.summary.existing_products;
  const realizedPrices = receipt.summary.created_prices + receipt.summary.existing_prices;
  receipt.state = receipt.summary.holds === 0 && realizedProducts === receipt.summary.desired_products && realizedPrices === receipt.summary.desired_prices ? 'PASS' : 'HOLD';
  receipt.observed_at = new Date().toISOString();

  if (receiptPath) await writeFile(resolve(receiptPath), `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  return receipt;
}

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  console.log(usage());
  process.exit(0);
}
if (!args.manifest) {
  console.error(usage());
  process.exit(2);
}

try {
  const manifestPath = resolve(args.manifest);
  const rawManifest = await readFile(manifestPath, 'utf8');
  const manifest = JSON.parse(rawManifest);
  assertManifest(manifest);
  const receipt = await sync(manifest, rawManifest, { apply: args.apply, receiptPath: args.receipt });
  console.log(JSON.stringify(receipt, null, 2));
  process.exit(receipt.state === 'HOLD' ? 3 : 0);
} catch (error) {
  const failure = {
    contract: 'ct.paddle.catalog-sync-receipt.v1',
    state: 'FAIL',
    provider: 'paddle',
    provider_write: false,
    credential_exposed: false,
    secret_value_returned: false,
    error: error.message,
    http_status: error.status || null,
    provider_error_code: error?.payload?.error?.code || null,
    provider_request_id: error?.payload?.meta?.request_id || null,
    observed_at: new Date().toISOString()
  };
  console.error(JSON.stringify(failure, null, 2));
  process.exit(1);
}
