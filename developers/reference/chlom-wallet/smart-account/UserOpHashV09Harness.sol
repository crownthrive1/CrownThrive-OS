// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ERC-4337 v0.9 UserOperation Hash Harness
/// @notice Controlled-test cross-check for CHLOM's unsigned intent builder. It cannot execute or broadcast a UserOperation.
contract UserOpHashV09Harness {
    struct PackedUserOperation {
        address sender;
        uint256 nonce;
        bytes initCode;
        bytes callData;
        bytes32 accountGasLimits;
        uint256 preVerificationGas;
        bytes32 gasFees;
        bytes paymasterAndData;
        bytes signature;
    }

    bytes32 public constant PACKED_USEROP_TYPEHASH = keccak256(
        "PackedUserOperation(address sender,uint256 nonce,bytes initCode,bytes callData,bytes32 accountGasLimits,uint256 preVerificationGas,bytes32 gasFees,bytes paymasterAndData)"
    );
    bytes32 public constant DOMAIN_TYPEHASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    bytes32 public constant DOMAIN_NAME_HASH = keccak256("ERC4337");
    bytes32 public constant DOMAIN_VERSION_HASH = keccak256("1");

    function getStructHash(PackedUserOperation calldata userOp) public pure returns (bytes32) {
        return keccak256(
            abi.encode(
                PACKED_USEROP_TYPEHASH,
                userOp.sender,
                userOp.nonce,
                keccak256(userOp.initCode),
                keccak256(userOp.callData),
                userOp.accountGasLimits,
                userOp.preVerificationGas,
                userOp.gasFees,
                keccak256(userOp.paymasterAndData)
            )
        );
    }

    function getDomainSeparator(uint256 chainId, address entryPoint) public pure returns (bytes32) {
        return keccak256(
            abi.encode(
                DOMAIN_TYPEHASH,
                DOMAIN_NAME_HASH,
                DOMAIN_VERSION_HASH,
                chainId,
                entryPoint
            )
        );
    }

    function getUserOpHash(
        PackedUserOperation calldata userOp,
        uint256 chainId,
        address entryPoint
    ) external pure returns (bytes32) {
        return keccak256(
            abi.encodePacked(
                hex"1901",
                getDomainSeparator(chainId, entryPoint),
                getStructHash(userOp)
            )
        );
    }
}
