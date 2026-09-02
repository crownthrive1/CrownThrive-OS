#!/usr/bin/env python3
"""Trusted main-branch collision observer with bounded public GET degradation.

The main reconciliation path shares the exact read-only transport used by the
trusted pull-request observer. Authenticated provider reads are attempted first;
a provider 403/429 can degrade only when the same public repository resource is
readable through GitHub's public GET surface. The client never writes to GitHub,
never expands merge or D3 authority, and remains fail-closed when both reads
fail.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping, Sequence
from typing import Any

import governed_collision_agent_v2 as agent
from governed_collision_agent_v2_trusted import TrustedCandidateClient


MAIN_RECONCILIATION_CANDIDATE = 0
DEFAULT_EVENT_ACTION = "trusted-main-reconciliation"


def _audit_sha(value: str | None, branch: str) -> str:
    """Return non-authoritative event context; live refs remain both fences."""
    return value.strip() if value and value.strip() else f"live-ref:{branch}"


def build_client(
    repository: str,
    token: str | None,
    *,
    branch: str,
    event_sha: str | None,
) -> TrustedCandidateClient:
    return TrustedCandidateClient(
        repository,
        token,
        event_base_sha=_audit_sha(event_sha, branch),
        candidate=MAIN_RECONCILIATION_CANDIDATE,
    )


def _transport_evidence(client: TrustedCandidateClient | None) -> dict[str, Any] | None:
    if client is None:
        return None
    return client.transport_evidence()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--event-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--event-action", default=DEFAULT_EVENT_ACTION)
    parser.add_argument("--output", default="collision-governance-v2-report.json")
    parser.add_argument("--fail-on-severity", type=int, default=6)
    args = parser.parse_args(argv)

    if not args.repository:
        parser.error("--repository or GITHUB_REPOSITORY is required")

    client: TrustedCandidateClient | None = None
    try:
        client = build_client(
            args.repository,
            args.token,
            branch=args.branch,
            event_sha=args.event_sha,
        )
        report = agent.analyze_snapshot(
            client,
            branch=args.branch,
            candidate=None,
            event_action=args.event_action,
        )
        report["trusted_event_sha"] = _audit_sha(args.event_sha, args.branch)
        report["trusted_base_fence_source"] = "git_ref_live_branch_sha"
        report["trusted_end_fence_source"] = "git_ref_live_branch_sha"
        report["trusted_provider_transport"] = client.transport_evidence()
        report["merge_authority"] = False
        report["D3_auto"] = False
        agent.write_report(report, args.output)

        decision = report.get("decision")
        if isinstance(decision, Mapping) and int(decision.get("max_severity", 0)) >= args.fail_on_severity:
            return 2
        return 0
    except (agent.ContractError, agent.GitHubReadError, KeyError, TypeError, ValueError, OSError) as exc:
        failure: dict[str, Any] = {
            "schema_version": agent.SCHEMA_VERSION,
            "disposition": "HOLD",
            "reason_code": "COLLISION_OBSERVER_FAILED_CLOSED",
            "error": str(exc),
            "trusted_event_sha": _audit_sha(args.event_sha, args.branch),
            "trusted_base_fence_source": "git_ref_live_branch_sha",
            "trusted_end_fence_source": "git_ref_live_branch_sha",
            "merge_authority": False,
            "D3_auto": False,
        }
        evidence = _transport_evidence(client)
        if evidence is not None:
            failure["trusted_provider_transport"] = evidence
        agent.write_report(failure, args.output)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
