#!/usr/bin/env python3
"""Adapter tests for semantic parsing, stale snapshots, and reaction behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from governed_collision_agent_v2 import ChangedFile, analyze_snapshot  # noqa: E402


ZERO40 = "0" * 40
ONE40 = "1" * 40
TWO40 = "2" * 40
THREE40 = "3" * 40


def pull(number: int, head: str, base: str, body: str | None = None) -> dict[str, Any]:
    return {"number": number, "head": {"sha": head}, "base": {"sha": base}, "body": body}


class FakeGitHubClient:
    repository = "crownthrive1/CrownThrive-OS"

    def __init__(
        self,
        pulls: list[dict[str, Any]],
        files: dict[int, list[ChangedFile]],
        contents: dict[tuple[str, str], str] | None = None,
        main_reads: list[str] | None = None,
        terminal_pulls: dict[int, dict[str, Any]] | None = None,
        terminal_open_pulls: list[dict[str, Any]] | None = None,
    ) -> None:
        self._pulls = pulls
        self._files = files
        self._contents = contents or {}
        self._main_reads = iter(main_reads or [ZERO40, ZERO40])
        self._terminal_pulls = terminal_pulls or {int(item["number"]): item for item in pulls}
        self._terminal_open_pulls = terminal_open_pulls or pulls
        self._open_pull_reads = 0

    def main_sha(self, _branch: str) -> str:
        return next(self._main_reads)

    def open_pulls(self) -> list[dict[str, Any]]:
        self._open_pull_reads += 1
        return list(self._pulls if self._open_pull_reads == 1 else self._terminal_open_pulls)

    def pull(self, number: int) -> dict[str, Any]:
        return self._terminal_pulls[number]

    def files(self, number: int) -> list[ChangedFile]:
        return self._files[number]

    def content(self, path: str, ref: str) -> str:
        try:
            return self._contents[(path, ref)]
        except KeyError as exc:
            raise RuntimeError(f"missing_fixture:{path}:{ref}") from exc


def changed(path: str, marker: str = "blob", access: str = "mutate") -> ChangedFile:
    import hashlib

    return ChangedFile(
        path=path,
        access=access,
        value_digest=hashlib.sha256(marker.encode("utf-8")).hexdigest(),
    )


class AdapterTests(unittest.TestCase):
    def test_same_agent_id_in_different_manifests_is_ct3(self) -> None:
        prs = [pull(1, ONE40, ZERO40), pull(2, TWO40, ZERO40)]
        paths = {1: [changed("developers/manifests/a.json", "a")], 2: [changed("developers/manifests/b.json", "b")]}
        contents = {
            ("developers/manifests/a.json", ONE40): '{"agent_id":"ct.agent.duplicate"}',
            ("developers/manifests/b.json", TWO40): '{"agent_id":"ct.agent.duplicate"}',
        }
        report = analyze_snapshot(FakeGitHubClient(prs, paths, contents), branch="main", candidate=1, event_action="synchronize")
        self.assertEqual(report["decision"]["disposition"], "HOLD")
        self.assertEqual(report["decision"]["max_severity"], 3)

    def test_duplicate_cron_is_runtime_collision(self) -> None:
        prs = [pull(1, ONE40, ZERO40), pull(2, TWO40, ZERO40)]
        paths = {1: [changed(".github/workflows/a.yml", "a")], 2: [changed(".github/workflows/b.yml", "b")]}
        contents = {
            (".github/workflows/a.yml", ONE40): "schedule:\n  - cron: '17 * * * *'\n",
            (".github/workflows/b.yml", TWO40): 'schedule:\n  - cron: "17 * * * *"\n',
        }
        report = analyze_snapshot(FakeGitHubClient(prs, paths, contents), branch="main", candidate=1, event_action="opened")
        self.assertEqual(report["decision"]["max_severity"], 4)

    def test_main_movement_forces_hold(self) -> None:
        prs = [pull(1, ONE40, ZERO40)]
        paths = {1: [changed("plain.txt")]}
        report = analyze_snapshot(
            FakeGitHubClient(prs, paths, main_reads=[ZERO40, TWO40]),
            branch="main",
            candidate=1,
            event_action="synchronize",
        )
        self.assertFalse(report["snapshot_stable"])
        self.assertIn("snapshot_changed_during_evaluation", report["decision"]["reason_codes"])
        self.assertEqual(report["decision"]["disposition"], "HOLD")

    def test_candidate_head_movement_forces_hold(self) -> None:
        original = pull(1, ONE40, ZERO40)
        moved = pull(1, THREE40, ZERO40)
        report = analyze_snapshot(
            FakeGitHubClient(
                [original],
                {1: [changed("plain.txt")]},
                terminal_pulls={1: moved},
                terminal_open_pulls=[moved],
            ),
            branch="main",
            candidate=1,
            event_action="synchronize",
        )
        self.assertFalse(report["snapshot_stable"])
        self.assertEqual(report["candidate_head_start"], ONE40)
        self.assertEqual(report["candidate_head_end"], THREE40)

    def test_malformed_semantic_json_forces_hold(self) -> None:
        prs = [pull(1, ONE40, ZERO40)]
        path = "developers/manifests/broken.json"
        report = analyze_snapshot(
            FakeGitHubClient(prs, {1: [changed(path)]}, {(path, ONE40): "{"}),
            branch="main",
            candidate=1,
            event_action="opened",
        )
        self.assertEqual(report["decision"]["disposition"], "HOLD")
        self.assertIn("semantic_inspection_incomplete", report["decision"]["reason_codes"])

    def test_byte_identical_direct_stack_is_inert_awareness(self) -> None:
        prs = [pull(1, ONE40, ZERO40), pull(2, TWO40, ONE40)]
        shared = changed("guides/shared.mdx", "same-blob")
        paths = {1: [shared], 2: [shared]}
        contents = {("guides/shared.mdx", ONE40): "shared", ("guides/shared.mdx", TWO40): "shared"}
        report = analyze_snapshot(FakeGitHubClient(prs, paths, contents), branch="main", candidate=1, event_action="synchronize")
        self.assertEqual(report["decision"]["disposition"], "ALLOW_AWARE")
        self.assertEqual(report["decision"]["max_severity"], 1)

    def test_closed_event_emits_release_reaction(self) -> None:
        item = pull(7, ONE40, ZERO40)
        report = analyze_snapshot(
            FakeGitHubClient([item], {7: [changed("x.txt")]}),
            branch="main",
            candidate=7,
            event_action="closed",
        )
        self.assertEqual(report["reaction"], "RELEASE_OWNERSHIP_AND_RECONCILE")
        self.assertFalse(report["merge_authority"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
