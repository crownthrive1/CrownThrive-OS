// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ThriveFund Obligation Registry (controlled-test reference)
/// @notice Records approved obligation commitments only. It does not custody or disburse funds.
contract ThriveFundObligationRegistry {
    error Unauthorized();
    error Paused();
    error Exists(bytes32 obligationId);
    error Missing(bytes32 obligationId);
    error ZeroValue();

    enum State { None, Recorded, SettledExternally, Reversed }

    struct Obligation {
        bytes32 sourceDigest;
        bytes32 programDigest;
        bytes32 assetDigest;
        uint256 amountMinor;
        State state;
        uint64 recordedAt;
    }

    address public admin;
    address public operator;
    bool public paused;
    mapping(bytes32 => Obligation) private _obligations;

    event OperatorChanged(address indexed previousOperator, address indexed newOperator);
    event PauseChanged(bool paused);
    event ObligationRecorded(bytes32 indexed obligationId, bytes32 indexed sourceDigest, bytes32 indexed programDigest, bytes32 assetDigest, uint256 amountMinor);
    event ObligationStateChanged(bytes32 indexed obligationId, State state, bytes32 indexed evidenceDigest);

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

    function record(bytes32 obligationId, bytes32 sourceDigest, bytes32 programDigest, bytes32 assetDigest, uint256 amountMinor) external onlyOperator {
        if (paused) revert Paused();
        if (obligationId == bytes32(0) || sourceDigest == bytes32(0) || programDigest == bytes32(0) || assetDigest == bytes32(0)) revert ZeroValue();
        if (_obligations[obligationId].state != State.None) revert Exists(obligationId);
        _obligations[obligationId] = Obligation(sourceDigest, programDigest, assetDigest, amountMinor, State.Recorded, uint64(block.timestamp));
        emit ObligationRecorded(obligationId, sourceDigest, programDigest, assetDigest, amountMinor);
    }

    function markSettledExternally(bytes32 obligationId, bytes32 evidenceDigest) external onlyOperator {
        Obligation storage o = _obligations[obligationId];
        if (o.state != State.Recorded) revert Missing(obligationId);
        o.state = State.SettledExternally;
        emit ObligationStateChanged(obligationId, State.SettledExternally, evidenceDigest);
    }

    function reverse(bytes32 obligationId, bytes32 evidenceDigest) external onlyOperator {
        Obligation storage o = _obligations[obligationId];
        if (o.state == State.None) revert Missing(obligationId);
        o.state = State.Reversed;
        emit ObligationStateChanged(obligationId, State.Reversed, evidenceDigest);
    }

    function get(bytes32 obligationId) external view returns (Obligation memory) {
        return _obligations[obligationId];
    }
}
