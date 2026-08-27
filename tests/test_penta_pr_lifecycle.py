from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from penta_pr_lifecycle import (  # noqa: E402
    attempt_merge,
    iso,
    mark_terminal,
    pentacloser,
    require_preclose_readback,
    set_labels,
)


class FakeGH:
    def __init__(self):
        self.repo = "crownthrive1/CrownThrive-OS"
        self.issue = {
            "number": 12,
            "labels": [
                {"name": "penta:tagged"},
                {"name": "penta:authority:tagger"},
                {"name": "penta:entity:pr"},
                {"name": "penta:lane:workflow"},
                {"name": "penta:stage:review"},
                {"name": "custom:keep"},
            ],
        }
        self.pr = {
            "number": 12,
            "title": "Test PR",
            "body": "",
            "state": "open",
            "draft": False,
            "mergeable": False,
            "mergeable_state": "dirty",
            "head": {"sha": "abc"},
        }
        self.comments = []
        self.closed = False
        self.put_calls = []
        self.operations = []

    def get(self, path):
        self.operations.append(("get", path))
        if "/issues/12/comments?" in path:
            return self.comments
        if path.endswith("/issues/12"):
            return self.issue
        if path.endswith("/pulls/12"):
            return self.pr
        if "/commits/abc/check-runs" in path:
            return {"check_runs": []}
        if "/commits/abc/status" in path:
            return {"state": "success"}
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, body):
        self.operations.append(("post", path, body))
        if path.endswith("/issues/12/labels"):
            existing = {item["name"] for item in self.issue["labels"]}
            existing.update(body["labels"])
            self.issue["labels"] = [{"name": item} for item in sorted(existing)]
            return self.issue["labels"]
        if path.endswith("/issues/12/comments"):
            comment = {"id": len(self.comments) + 1, "body": body["body"]}
            self.comments.append(comment)
            return comment
        raise AssertionError(f"unexpected POST {path}")

    def patch(self, path, body):
        self.operations.append(("patch", path, body))
        if "/issues/comments/" in path:
            self.comments[0]["body"] = body["body"]
            return self.comments[0]
        if path.endswith("/pulls/12"):
            self.closed = body.get("state") == "closed"
            self.pr["state"] = body.get("state", self.pr["state"])
            return self.pr
        raise AssertionError(f"unexpected PATCH {path}")

    def put(self, path, body):
        self.operations.append(("put", path, body))
        self.put_calls.append((path, body))
        return {"merged": True, "message": "merged"}

    def delete(self, path):
        self.operations.append(("delete", path))
        label = unquote(path.rsplit("/", 1)[-1])
        self.issue["labels"] = [item for item in self.issue["labels"] if item["name"] != label]
        return None

    def paginate(self, path, *, list_key=None, max_pages=10):
        self.operations.append(("paginate", path))
        if "/pulls?state=open" in path:
            return [] if self.closed else [self.pr]
        if "/issues/12/comments" in path:
            return list(self.comments)
        if path.endswith("/labels?per_page=100"):
            return []
        raise AssertionError(f"unexpected paginate {path}")


class MissingPrecloseLabelsGH(FakeGH):
    def post(self, path, body):
        if path.endswith("/issues/12/labels") and {
            "penta:close",
            "penta:stage:close-candidate",
            "penta:authority:pr",
        }.intersection(body["labels"]):
            self.operations.append(("post_suppressed", path, body))
            return []
        return super().post(path, body)


class HoldDuringPrecloseGH(FakeGH):
    def post(self, path, body):
        result = super().post(path, body)
        if path.endswith("/issues/12/labels") and "penta:close" in body["labels"]:
            existing = {item["name"] for item in self.issue["labels"]}
            existing.add("penta:hold")
            self.issue["labels"] = [{"name": item} for item in sorted(existing)]
        return result


def label_names(gh):
    return {item["name"] for item in gh.issue["labels"]}


def install_expired_state(gh: FakeGH, *, head_sha: str = "abc") -> None:
    expired = iso(dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1))
    state = {
        "first_seen_at": expired,
        "deadline_at": expired,
        "disposition": "NURTURE",
        "reason": "test",
        "head_sha": head_sha,
    }
    gh.comments.append(
        {
            "id": 1,
            "body": f"<!-- penta-pr-lifecycle:{json.dumps(state, separators=(',', ':'))} -->\n\nstate",
        }
    )


class PentaPRLifecycleTests(unittest.TestCase):
    def test_set_labels_preserves_tagger_and_custom_labels(self):
        gh = FakeGH()
        set_labels(gh, 12, "CLOSE")
        labels = label_names(gh)
        self.assertIn("penta:tagged", labels)
        self.assertIn("penta:authority:tagger", labels)
        self.assertIn("penta:entity:pr", labels)
        self.assertIn("penta:lane:workflow", labels)
        self.assertIn("custom:keep", labels)
        self.assertIn("penta:close", labels)
        self.assertIn("penta:stage:close-candidate", labels)
        self.assertIn("penta:authority:pr", labels)
        self.assertIn("penta:deadline-12h", labels)
        self.assertNotIn("penta:stage:review", labels)

    def test_terminal_close_stamps_closer_and_removes_stage(self):
        gh = FakeGH()
        set_labels(gh, 12, "CLOSE")
        mark_terminal(gh, 12, "penta:terminal:closed", "penta:authority:closer")
        labels = label_names(gh)
        self.assertIn("penta:terminal:closed", labels)
        self.assertIn("penta:authority:closer", labels)
        self.assertFalse(any(label.startswith("penta:stage:") for label in labels))
        self.assertIn("penta:close", labels, "disposition remains as audit history")

    def test_hold_blocks_merge(self):
        gh = FakeGH()
        gh.issue["labels"].append({"name": "penta:hold"})
        merged, message = attempt_merge(gh, 12)
        self.assertFalse(merged)
        self.assertEqual(message, "operator_hold")
        self.assertFalse(gh.put_calls)

    def test_preclose_readback_checks_exact_open_head(self):
        gh = FakeGH()
        set_labels(gh, 12, "CLOSE")
        labels = require_preclose_readback(
            gh,
            12,
            lifecycle_head_sha="abc",
            expected_head_sha="abc",
        )
        self.assertIn("penta:close", labels)

    def test_closer_tags_and_reads_back_before_terminal_close(self):
        gh = FakeGH()
        install_expired_state(gh)
        pentacloser(gh)
        labels = label_names(gh)
        self.assertTrue(gh.closed)
        self.assertIn("penta:close", labels)
        self.assertIn("penta:terminal:closed", labels)
        self.assertIn("penta:authority:closer", labels)
        close_index = next(
            index
            for index, operation in enumerate(gh.operations)
            if operation[0] == "patch" and operation[1].endswith("/pulls/12")
        )
        preclose_issue_reads = [
            index
            for index, operation in enumerate(gh.operations[:close_index])
            if operation[0] == "get" and operation[1].endswith("/issues/12")
        ]
        self.assertTrue(preclose_issue_reads, "fresh issue-label readback must occur before close")

    def test_closer_fails_closed_when_provider_hides_close_labels(self):
        gh = MissingPrecloseLabelsGH()
        install_expired_state(gh)
        with self.assertRaisesRegex(RuntimeError, "preclose_label_readback_failed"):
            pentacloser(gh)
        self.assertFalse(gh.closed)

    def test_closer_requires_pentatagger_preflight_marker(self):
        gh = FakeGH()
        gh.issue["labels"] = [
            item for item in gh.issue["labels"] if item["name"] != "penta:tagged"
        ]
        install_expired_state(gh)
        with self.assertRaisesRegex(RuntimeError, "preclose_label_readback_failed"):
            pentacloser(gh)
        self.assertFalse(gh.closed)

    def test_closer_blocks_hold_added_during_preclose_window(self):
        gh = HoldDuringPrecloseGH()
        install_expired_state(gh)
        with self.assertRaisesRegex(RuntimeError, "preclose_hold_detected"):
            pentacloser(gh)
        self.assertFalse(gh.closed)

    def test_closer_blocks_stale_lifecycle_head(self):
        gh = FakeGH()
        install_expired_state(gh, head_sha="stale")
        with self.assertRaisesRegex(RuntimeError, "preclose_lifecycle_head_stale"):
            pentacloser(gh)
        self.assertFalse(gh.closed)

    def test_workflow_preflights_tagger_before_terminal_authority(self):
        workflow = (ROOT / ".github/workflows/penta-pr-lifecycle-reusable.yml").read_text(
            encoding="utf-8"
        )
        preflight = workflow.index("Preflight PentaTagger before terminal authority")
        lifecycle = workflow.index("Run PentaPR, PentaMerge, or PentaCloser")
        final = workflow.index("Project final lifecycle through PentaTagger")
        self.assertLess(preflight, lifecycle)
        self.assertLess(lifecycle, final)
        self.assertIn("env.PENTA_MODE == 'merge' || env.PENTA_MODE == 'closer'", workflow)
        self.assertIn("if: always()", workflow)


if __name__ == "__main__":
    unittest.main()
