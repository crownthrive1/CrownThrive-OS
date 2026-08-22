// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title CHLOM Entitlement Registry (controlled-test reference)
/// @notice Records entitlement commitments. Governing legal/rights meaning remains off-chain in CHLOM.
contract ChlomEntitlementRegistry {
    error Unauthorized();
    error Paused();
    error Exists(bytes32 entitlementId);
    error Missing(bytes32 entitlementId);
    error InvalidState(bytes32 entitlementId);
    error ZeroValue();

    enum State { None, Active, Revoked }

    struct Entitlement {
        bytes32 subjectDigest;
        bytes32 assetDigest;
        bytes32 termsDigest;
        uint64 validFrom;
        uint64 validUntil;
        State state;
    }

    address public admin;
    address public operator;
    bool public paused;
    mapping(bytes32 => Entitlement) private _entitlements;

    event OperatorChanged(address indexed previousOperator, address indexed newOperator);
    event PauseChanged(bool paused);
    event EntitlementRecorded(bytes32 indexed entitlementId, bytes32 indexed subjectDigest, bytes32 indexed assetDigest, bytes32 termsDigest, uint64 validFrom, uint64 validUntil);
    event EntitlementRevoked(bytes32 indexed entitlementId, bytes32 indexed reasonDigest);

    constructor(address initialAdmin) {
        if (initialAdmin == address(0)) revert ZeroValue();
        admin = initialAdmin;
    }

    modifier onlyAdmin() {
        if (msg.sender != admin) revert Unauthorized();
        _;
    }

    modifier onlyOperator() {
        if (msg.sender != admin && msg.sender != operator) revert Unauthorized();
        _;
    }

    function setOperator(address newOperator) external onlyAdmin {
        emit OperatorChanged(operator, newOperator);
        operator = newOperator;
    }

    function setPaused(bool value) external onlyAdmin {
        paused = value;
        emit PauseChanged(value);
    }

    function record(
        bytes32 entitlementId,
        bytes32 subjectDigest,
        bytes32 assetDigest,
        bytes32 termsDigest,
        uint64 validFrom,
        uint64 validUntil
    ) external onlyOperator {
        if (paused) revert Paused();
        if (entitlementId == bytes32(0) || subjectDigest == bytes32(0) || assetDigest == bytes32(0) || termsDigest == bytes32(0)) revert ZeroValue();
        if (validUntil != 0 && validUntil <= validFrom) revert ZeroValue();
        if (_entitlements[entitlementId].state != State.None) revert Exists(entitlementId);
        _entitlements[entitlementId] = Entitlement(subjectDigest, assetDigest, termsDigest, validFrom, validUntil, State.Active);
        emit EntitlementRecorded(entitlementId, subjectDigest, assetDigest, termsDigest, validFrom, validUntil);
    }

    function revoke(bytes32 entitlementId, bytes32 reasonDigest) external onlyOperator {
        Entitlement storage e = _entitlements[entitlementId];
        if (e.state == State.None) revert Missing(entitlementId);
        if (e.state != State.Active) revert InvalidState(entitlementId);
        if (reasonDigest == bytes32(0)) revert ZeroValue();
        e.state = State.Revoked;
        emit EntitlementRevoked(entitlementId, reasonDigest);
    }

    function get(bytes32 entitlementId) external view returns (Entitlement memory) {
        return _entitlements[entitlementId];
    }

    function isActive(bytes32 entitlementId, uint64 atTime) external view returns (bool) {
        Entitlement memory e = _entitlements[entitlementId];
        if (e.state != State.Active || atTime < e.validFrom) return false;
        return e.validUntil == 0 || atTime < e.validUntil;
    }
}
