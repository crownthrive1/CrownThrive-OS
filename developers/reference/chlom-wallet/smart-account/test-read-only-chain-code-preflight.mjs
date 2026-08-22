import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { hexToBytes, keccak256 } from './user-operation-intent.mjs';
import {
  jsonRpcRead,
  runReadOnlyCodePreflight,
  validateRpcUrl,
} from './read-only-chain-code-preflight.mjs';

const runtimeCode = '0x60016000556002600055';
const runtimeCodehash = keccak256(hexToBytes(runtimeCode)).toLowerCase();
const address = '0x433709009B8330FDa32311DF1C2AFA402eD8D009';
const calls = [];

const server = createServer(async (request, response) => {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  calls.push(body.method);
  let result;
  if (body.method === 'eth_chainId') result = '0xaa36a7';
  else if (body.method === 'eth_getCode') result = runtimeCode;
  else {
    response.writeHead(200, { 'content-type': 'application/json' });
    response.end(JSON.stringify({ jsonrpc: '2.0', id: body.id, error: { code: -32601, message: 'method not found' } }));
    return;
  }
  response.writeHead(200, { 'content-type': 'application/json' });
  response.end(JSON.stringify({ jsonrpc: '2.0', id: body.id, result }));
});
server.listen(0, '127.0.0.1');
await once(server, 'listening');
const port = server.address().port;
const rpcUrl = `http://127.0.0.1:${port}/`;

try {
  assert.throws(() => validateRpcUrl(rpcUrl), /rpc_url_must_use_https/);
  assert.equal(validateRpcUrl(rpcUrl, { allowLocalhost: true }), rpcUrl);
  await assert.rejects(
    () => jsonRpcRead(rpcUrl, 'eth_sendRawTransaction', ['0x00'], { allowLocalhost: true }),
    /rpc_write_method_forbidden/,
  );

  const unapprovedHash = await runReadOnlyCodePreflight({
    rpcUrl,
    expectedChainIdHex: '0xaa36a7',
    address,
    allowLocalhost: true,
  });
  assert.equal(unapprovedHash.ok, false);
  assert.equal(unapprovedHash.disposition, 'HOLD_CODEHASH_APPROVAL_REQUIRED');
  assert.equal(unapprovedHash.observed_runtime_codehash, runtimeCodehash);
  assert.deepEqual(unapprovedHash.rpc_methods_used, ['eth_chainId', 'eth_getCode']);
  assert.equal(unapprovedHash.broadcast, false);

  const pass = await runReadOnlyCodePreflight({
    rpcUrl,
    expectedChainIdHex: '0xaa36a7',
    address,
    expectedRuntimeCodehash: runtimeCodehash,
    allowLocalhost: true,
  });
  assert.equal(pass.ok, true);
  assert.equal(pass.disposition, 'PASS_READ_ONLY_CODEHASH_PREFLIGHT');
  assert.equal(pass.money_movement, false);

  const mismatch = await runReadOnlyCodePreflight({
    rpcUrl,
    expectedChainIdHex: '0xaa36a7',
    address,
    expectedRuntimeCodehash: `0x${'00'.repeat(32)}`,
    allowLocalhost: true,
  });
  assert.equal(mismatch.ok, false);
  assert.equal(mismatch.disposition, 'HOLD_RUNTIME_CODEHASH_MISMATCH');

  const wrongChain = await runReadOnlyCodePreflight({
    rpcUrl,
    expectedChainIdHex: '0x1',
    address,
    expectedRuntimeCodehash: runtimeCodehash,
    allowLocalhost: true,
  });
  assert.equal(wrongChain.ok, false);
  assert.equal(wrongChain.disposition, 'HOLD_CHAIN_ID_MISMATCH');
  assert.deepEqual(wrongChain.rpc_methods_used, ['eth_chainId']);

  assert.equal(calls.includes('eth_sendRawTransaction'), false);
  assert.ok(calls.filter((method) => method === 'eth_chainId').length >= 4);
  assert.ok(calls.filter((method) => method === 'eth_getCode').length >= 3);

  console.log(JSON.stringify({
    result: 'PASS_READ_ONLY_CHAIN_CODE_PREFLIGHT_CONTRACT',
    chain_id_bound: true,
    runtime_codehash_bound: true,
    missing_codehash_holds: true,
    mismatch_holds: true,
    rpc_write_methods_sent: false,
    external_rpc_used: false,
    testnet_broadcast: false,
    money_movement: false,
  }));
} finally {
  server.close();
  await once(server, 'close');
}
