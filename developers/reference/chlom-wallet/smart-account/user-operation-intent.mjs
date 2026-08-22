import { createHash } from 'node:crypto';

const MASK_64 = (1n << 64n) - 1n;
const ROTATION = [
  [0, 36, 3, 41, 18],
  [1, 44, 10, 45, 2],
  [62, 6, 43, 15, 61],
  [28, 55, 25, 21, 56],
  [27, 20, 39, 8, 14],
];
const ROUND_CONSTANTS = [
  0x0000000000000001n, 0x0000000000008082n, 0x800000000000808an, 0x8000000080008000n,
  0x000000000000808bn, 0x0000000080000001n, 0x8000000080008081n, 0x8000000000008009n,
  0x000000000000008an, 0x0000000000000088n, 0x0000000080008009n, 0x000000008000000an,
  0x000000008000808bn, 0x800000000000008bn, 0x8000000000008089n, 0x8000000000008003n,
  0x8000000000008002n, 0x8000000000000080n, 0x000000000000800an, 0x800000008000000an,
  0x8000000080008081n, 0x8000000000008080n, 0x0000000080000001n, 0x8000000080008008n,
];
const encoder = new TextEncoder();

function rotl64(value, shift) {
  if (shift === 0) return value & MASK_64;
  const s = BigInt(shift);
  return ((value << s) | (value >> (64n - s))) & MASK_64;
}

function keccakF(state) {
  for (const rc of ROUND_CONSTANTS) {
    const c = new Array(5).fill(0n);
    const d = new Array(5).fill(0n);
    for (let x = 0; x < 5; x++) {
      c[x] = state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20];
    }
    for (let x = 0; x < 5; x++) d[x] = c[(x + 4) % 5] ^ rotl64(c[(x + 1) % 5], 1);
    for (let x = 0; x < 5; x++) for (let y = 0; y < 5; y++) state[x + 5 * y] = (state[x + 5 * y] ^ d[x]) & MASK_64;
    const b = new Array(25).fill(0n);
    for (let x = 0; x < 5; x++) {
      for (let y = 0; y < 5; y++) {
        b[y + 5 * ((2 * x + 3 * y) % 5)] = rotl64(state[x + 5 * y], ROTATION[x][y]);
      }
    }
    for (let x = 0; x < 5; x++) {
      for (let y = 0; y < 5; y++) {
        state[x + 5 * y] = (b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y])) & MASK_64;
      }
    }
    state[0] = (state[0] ^ rc) & MASK_64;
  }
}

export function keccak256Bytes(input) {
  const bytes = input instanceof Uint8Array ? input : encoder.encode(input);
  const rate = 136;
  const paddedLength = Math.ceil((bytes.length + 1) / rate) * rate;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] ^= 0x01;
  padded[paddedLength - 1] ^= 0x80;
  const state = new Array(25).fill(0n);
  for (let offset = 0; offset < padded.length; offset += rate) {
    for (let i = 0; i < rate; i++) {
      const lane = Math.floor(i / 8);
      const shift = BigInt((i % 8) * 8);
      state[lane] ^= BigInt(padded[offset + i]) << shift;
    }
    keccakF(state);
  }
  const out = new Uint8Array(32);
  for (let i = 0; i < out.length; i++) out[i] = Number((state[Math.floor(i / 8)] >> BigInt((i % 8) * 8)) & 0xffn);
  return out;
}

export const bytesToHex = (bytes) => `0x${[...bytes].map((b) => b.toString(16).padStart(2, '0')).join('')}`;
export const keccak256 = (input) => bytesToHex(keccak256Bytes(input));

export function hexToBytes(value, { length, allowEmpty = true } = {}) {
  if (typeof value !== 'string' || !/^0x[0-9a-fA-F]*$/.test(value) || value.length % 2 !== 0) throw new Error('hex_invalid');
  const body = value.slice(2);
  if (!allowEmpty && body.length === 0) throw new Error('hex_empty');
  const out = Uint8Array.from(body.match(/.{2}/g)?.map((part) => parseInt(part, 16)) ?? []);
  if (length != null && out.length !== length) throw new Error('hex_length_invalid');
  return out;
}

function concat(...parts) {
  const out = new Uint8Array(parts.reduce((total, part) => total + part.length, 0));
  let offset = 0;
  for (const part of parts) { out.set(part, offset); offset += part.length; }
  return out;
}

function uintBytes(value, size = 32) {
  const n = typeof value === 'bigint' ? value : BigInt(value);
  if (n < 0n || n >= 1n << BigInt(size * 8)) throw new Error('uint_out_of_range');
  const out = new Uint8Array(size);
  let remaining = n;
  for (let i = size - 1; i >= 0; i--) { out[i] = Number(remaining & 0xffn); remaining >>= 8n; }
  return out;
}

function addressWord(address) {
  const bytes = hexToBytes(address, { length: 20, allowEmpty: false });
  return concat(new Uint8Array(12), bytes);
}

function bytes32Word(value) {
  return hexToBytes(value, { length: 32, allowEmpty: false });
}

export function packHighLow128(high, low) {
  return bytesToHex(concat(uintBytes(high, 16), uintBytes(low, 16)));
}

const PACKED_USEROP_TYPE = 'PackedUserOperation(address sender,uint256 nonce,bytes initCode,bytes callData,bytes32 accountGasLimits,uint256 preVerificationGas,bytes32 gasFees,bytes paymasterAndData)';
const DOMAIN_TYPE = 'EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)';
export const PACKED_USEROP_TYPEHASH = keccak256(PACKED_USEROP_TYPE);
export const DOMAIN_TYPEHASH = keccak256(DOMAIN_TYPE);
const EMPTY_HASH = keccak256(new Uint8Array());

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  if (typeof value === 'bigint') return JSON.stringify(value.toString());
  return JSON.stringify(value);
}

function sha256Hex(value) {
  return `0x${createHash('sha256').update(value).digest('hex')}`;
}

export function buildUserOperationIntent(input) {
  const chainId = BigInt(input.chainId);
  const sender = String(input.sender);
  const entryPoint = String(input.entryPoint);
  if (chainId <= 0n) throw new Error('chain_id_invalid');
  addressWord(sender);
  addressWord(entryPoint);
  if (sender.toLowerCase() === '0x0000000000000000000000000000000000000000') throw new Error('sender_zero_address');
  if (entryPoint.toLowerCase() === '0x0000000000000000000000000000000000000000') throw new Error('entrypoint_zero_address');
  const initCode = hexToBytes(input.initCode ?? '0x');
  const callData = hexToBytes(input.callData ?? '0x');
  const paymasterAndData = hexToBytes(input.paymasterAndData ?? '0x');
  const signature = hexToBytes(input.signature ?? '0x');
  if (initCode.length !== 0) throw new Error('init_code_disabled_until_factory_selection');
  if (paymasterAndData.length !== 0) throw new Error('paymaster_disabled_controlled_test');
  if (signature.length !== 0) throw new Error('signature_must_be_empty_for_intent');
  const accountGasLimits = packHighLow128(input.verificationGasLimit, input.callGasLimit);
  const gasFees = packHighLow128(input.maxPriorityFeePerGas, input.maxFeePerGas);
  const encodedUserOp = concat(
    bytes32Word(PACKED_USEROP_TYPEHASH),
    addressWord(sender),
    uintBytes(input.nonce),
    bytes32Word(keccak256(initCode)),
    bytes32Word(keccak256(callData)),
    bytes32Word(accountGasLimits),
    uintBytes(input.preVerificationGas),
    bytes32Word(gasFees),
    bytes32Word(EMPTY_HASH),
  );
  const structHash = keccak256(encodedUserOp);
  const domainEncoded = concat(
    bytes32Word(DOMAIN_TYPEHASH),
    bytes32Word(keccak256('ERC4337')),
    bytes32Word(keccak256('1')),
    uintBytes(chainId),
    addressWord(entryPoint),
  );
  const domainSeparator = keccak256(domainEncoded);
  const userOpHash = keccak256(concat(Uint8Array.from([0x19, 0x01]), bytes32Word(domainSeparator), bytes32Word(structHash)));
  const operation = {
    sender: sender.toLowerCase(),
    nonce: BigInt(input.nonce).toString(),
    initCode: bytesToHex(initCode),
    callData: bytesToHex(callData),
    accountGasLimits,
    preVerificationGas: BigInt(input.preVerificationGas).toString(),
    gasFees,
    paymasterAndData: '0x',
    signature: '0x',
  };
  const envelope = {
    schema_version: '1.0.0',
    intent_id: String(input.intentId),
    chain: { caip2: `eip155:${chainId}`, chain_id: chainId.toString() },
    entry_point: { release: 'v0.9.0', address: entryPoint.toLowerCase(), domain_name: 'ERC4337', domain_version: '1' },
    packed_user_operation: operation,
    hashes: { packed_userop_typehash: PACKED_USEROP_TYPEHASH, domain_typehash: DOMAIN_TYPEHASH, struct_hash: structHash, domain_separator: domainSeparator, user_operation_hash: userOpHash },
    gates: {
      simulation_state: 'NOT_RUN',
      signature_state: 'UNSIGNED',
      factory_state: 'UNSELECTED',
      eip7702_state: 'NOT_SUPPORTED',
      paymaster_state: 'DISABLED',
      entrypoint_codehash_state: 'UNVERIFIED',
      call_data_semantic_review: callData.length === 0 ? 'EMPTY_NO_ACTION' : 'HOLD_OPAQUE_CALLDATA',
      broadcast: false,
      deploy: false,
      money_movement: false,
    },
  };
  return { ...envelope, intent_sha256: sha256Hex(canonicalJson(envelope)) };
}
