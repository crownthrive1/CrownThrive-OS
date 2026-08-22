// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title CHLOM Anchor Registry (controlled-test reference)
/// @notice Stores cryptographic proof commitments only. It does not store private evidence or move value.
contract ChlomAnchorRegistry {
    error Unauthorized();
    error Paused();
    error AlreadyAnchored(bytes32 batchId);
    error ZeroValue();

    struct Anchor {
        bytes32 rootDigest;
        bytes32 policyDigest;
        uint64 anchoredAt;
        address committer;
    }

    address public admin;
    address public operator;
    bool public paused;
    mapping(bytes32 => Anchor) private _anchors;

    event AdminChanged(address indexed previousAdmin, address indexed newAdmin);
    event OperatorChanged(address indexed previousOperator, address indexed newOperator);
    event PauseChanged(bool paused);
    event Anchored(bytes32 indexed batchId, bytes32 indexed rootDigest, bytes32 indexed policyDigest, address committer);

    constructor(address initialAdmin) {
        if (initialAdmin == address(0)) revert ZeroValue();
        admin = initialAdmin;
        emit AdminChanged(address(0), initialAdmin);
    }

    modifier onlyAdmin() {
        if (msg.sender != admin) revert Unauthorized();
        _;
    }

    modifier onlyOperator() {
        if (msg.sender != admin && msg.sender != operator) revert Unauthorized();
        _;
    }

    function setAdmin(address newAdmin) external onlyAdmin {
        if (newAdmin == address(0)) revert ZeroValue();
        emit AdminChanged(admin, newAdmin);
        admin = newAdmin;
    }

    function setOperator(address newOperator) external onlyAdmin {
        emit OperatorChanged(operator, newOperator);
        operator = newOperator;
    }

    function setPaused(bool value) external onlyAdmin {
        paused = value;
        emit PauseChanged(value);
    }

    function anchor(bytes32 batchId, bytes32 rootDigest, bytes32 policyDigest) external onlyOperator {
        if (paused) revert Paused();
        if (batchId == bytes32(0) || rootDigest == bytes32(0) || policyDigest == bytes32(0)) revert ZeroValue();
        if (_anchors[batchId].anchoredAt != 0) revert AlreadyAnchored(batchId);
        _anchors[batchId] = Anchor(rootDigest, policyDigest, uint64(block.timestamp), msg.sender);
        emit Anchored(batchId, rootDigest, policyDigest, msg.sender);
    }

    function getAnchor(bytes32 batchId) external view returns (Anchor memory) {
        return _anchors[batchId];
    }
}
