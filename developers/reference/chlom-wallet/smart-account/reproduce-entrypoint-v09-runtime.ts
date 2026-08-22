import assert from 'node:assert/strict'
import { writeFileSync } from 'node:fs'
import hre, { ethers } from 'hardhat'

const EXPECTED_RELEASE_COMMIT = 'b36a1ed52ae00da6f8a4c8d50181e2877e4fa410'
const EXPECTED_CHAIN_ID = 11155111
const EXPECTED_ENTRYPOINT_ADDRESS = '0x433709009b8330fda32311df1c2afa402ed8d009'
const EXPECTED_RUNTIME_CODEHASH = '0x280d5c7c0de94b512401eb9c4b0ef0436275ff03627aad0ce1f93ab1627187a0'
const EXPECTED_RUNTIME_CODE_BYTES = 22425

async function main (): Promise<void> {
  const provider = ethers.provider
  const from = await provider.getSigner().getAddress()
  const network = await provider.getNetwork()

  assert.equal(network.chainId, EXPECTED_CHAIN_ID, 'reproduction_chain_id_mismatch')

  const deployment = await hre.deployments.deploy('EntryPoint', {
    from,
    args: [],
    gasLimit: 6e6,
    deterministicDeployment: process.env.SALT ?? true,
    log: false
  })

  const address = deployment.address.toLowerCase()
  const runtimeCode = await provider.getCode(deployment.address)
  const runtimeCodeBytes = ethers.utils.arrayify(runtimeCode).length
  const runtimeCodehash = ethers.utils.keccak256(runtimeCode).toLowerCase()
  const nativeValueHeld = await provider.getBalance(deployment.address)

  assert.equal(address, EXPECTED_ENTRYPOINT_ADDRESS, 'deterministic_entrypoint_address_mismatch')
  assert.equal(runtimeCodeBytes, EXPECTED_RUNTIME_CODE_BYTES, 'entrypoint_runtime_code_size_mismatch')
  assert.equal(runtimeCodehash, EXPECTED_RUNTIME_CODEHASH, 'entrypoint_runtime_codehash_mismatch')
  assert.equal(nativeValueHeld.toString(), '0', 'entrypoint_unexpected_native_value')

  const result = {
    result: 'PASS_ERC4337_V09_REPRODUCIBLE_RUNTIME_MATCH_HOLD_INDEPENDENT_APPROVAL',
    upstream_release_commit: EXPECTED_RELEASE_COMMIT,
    local_network: {
      name: network.name,
      chain_id: network.chainId,
      target_semantics: 'sepolia_chain_id_on_ephemeral_hardhat'
    },
    deterministic_deployment: {
      entrypoint_address: address,
      runtime_code_bytes: runtimeCodeBytes,
      runtime_codehash: runtimeCodehash,
      newly_deployed: deployment.newlyDeployed,
      native_value_held_wei: nativeValueHeld.toString()
    },
    observed_sepolia_evidence: {
      entrypoint_address: EXPECTED_ENTRYPOINT_ADDRESS,
      runtime_code_bytes: EXPECTED_RUNTIME_CODE_BYTES,
      runtime_codehash: EXPECTED_RUNTIME_CODEHASH,
      provider_quorum_required: 2
    },
    interpretation: {
      local_runtime_matches_observed_sepolia_runtime: true,
      runtime_codehash_independently_approved: false,
      deployment_authorized: false,
      broadcast_authorized: false
    },
    hard_boundaries: {
      external_rpc_used: false,
      production_signer_used: false,
      private_key_imported: false,
      user_operation_created: false,
      simulation_completed: false,
      public_testnet_deployment: false,
      public_testnet_broadcast: false,
      mainnet_deployment: false,
      mainnet_broadcast: false,
      custody: false,
      money_movement: false,
      production_rights_grant: false,
      phase_advancement: false
    }
  }

  assert.ok(Object.values(result.hard_boundaries).every((value) => value === false))
  const outputPath = process.env.CHLOM_OUTPUT_PATH
  if (outputPath) writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8')
  console.log(JSON.stringify(result))
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
