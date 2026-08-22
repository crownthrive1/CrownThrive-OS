// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title CHLOM Split Policy Registry (controlled-test reference)
/// @notice Commits approved split policy digests. It never transfers funds.
contract ChlomSplitPolicyRegistry {
    error Unauthorized();
    error Paused();
    error InvalidBps();
    error Exists(bytes32 policyId);
    error ZeroValue();

    struct Policy {
        bytes32 scheduleDigest;
        uint16 legCount;
        uint64 createdAt;
        bool superseded;
    }

    address public admin;
    address public operator;
    bool public paused;
    mapping(bytes32 => Policy) private _policies;

    event OperatorChanged(address indexed previousOperator, address indexed newOperator);
    event PauseChanged(bool paused);
    event PolicyRecorded(bytes32 indexed policyId, bytes32 indexed scheduleDigest, uint16 legCount);
    event PolicySuperseded(bytes32 indexed policyId, bytes32 indexed replacementPolicyId);

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

    function validateBps(uint16[] calldata bps) public pure returns (bool) {
        if (bps.length == 0 || bps.length > 64) return false;
        uint256 total;
        for (uint256 i = 0; i < bps.length; i++) total += bps[i];
        return total == 10_000;
    }

    function record(bytes32 policyId, bytes32 scheduleDigest, uint16[] calldata bps) external onlyOperator {
        if (paused) revert Paused();
        if (policyId == bytes32(0) || scheduleDigest == bytes32(0)) revert ZeroValue();
        if (!validateBps(bps)) revert InvalidBps();
        if (_policies[policyId].createdAt != 0) revert Exists(policyId);
        _policies[policyId] = Policy(scheduleDigest, uint16(bps.length), uint64(block.timestamp), false);
        emit PolicyRecorded(policyId, scheduleDigest, uint16(bps.length));
    }

    function supersede(bytes32 policyId, bytes32 replacementPolicyId) external onlyOperator {
        if (replacementPolicyId == bytes32(0)) revert ZeroValue();
        _policies[policyId].superseded = true;
        emit PolicySuperseded(policyId, replacementPolicyId);
    }

    function get(bytes32 policyId) external view returns (Policy memory) {
        return _policies[policyId];
    }
}
