from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from penta_github_tagger import (  # noqa: E402
    EXIT_DEFERRED,
    Entity,
    GH,
    GitHubRequestError,
    RateLimitDeferred,
    classify_lanes,
    classify_risk,
    entity_from_event_payload,
    main,
    sweep_numbers,
    tag_entity,
    target_from_event,
    write_outputs,
)
from penta_github_labels import LABEL_SPECS, add_labels  # noqa: E402


class FakeGH:
    def __init__(self, *, issue, pr=None, files=None):
        self.repo = "crownthrive1/CrownThrive-OS"
        self.issue = issue
        self.pr = pr
        self.files = files or []
        self.repo_labels = set(LABEL_SPECS)
        self.comments = []
        self.pr_state_writes = []
        self.calls = []
        self.request_count = 0
        self.authenticated_request_count = 0
        self.public_request_count = 0
        self.last_transport = "fake-provider"
        self.last_rate_limit = None
        self.fail_unknown_labels = False

    def _record(self, method, path):
        self.calls.append((method, path))
        self.request_count += 1
        self.authenticated_request_count += 1

    def get(self, path):
        self._record("GET", path)
        if path.endswith("/labels?per_page=100&page=1"):
            return [{"name": name} for name in sorted(self.repo_labels)]
        if "/issues/" in path and path.endswith("/comments?per_page=100&page=1"):
            return list(self.comments)
        if "/issues/" in path and "/comments" not in path:
            return self.issue
        if "/pulls/" in path and path.endswith("/files?per_page=100&page=1"):
            return self.files
        if "/pulls/" in path:
            return self.pr
        if "/issues?state=all" in path:
            return [self.issue]
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, body):
        self._record("POST", path)
        if path.endswith("/labels") and "/issues/" not in path:
            self.repo_labels.add(body["name"])
            return body
        if "/issues/" in path and path.endswith("/labels"):
            if self.fail_unknown_labels:
                unknown = set(body["labels"]).difference(self.repo_labels)
                if unknown:
                    raise RuntimeError(
                        "POST labels -> 422: Validation Failed: label does not exist"
                    )
            existing = {item["name"] for item in self.issue.get("labels", [])}
            existing.update(body["labels"])
            self.issue["labels"] = [{"name": name} for name in sorted(existing)]
            return self.issue["labels"]
        if path.endswith("/comments"):
            comment = {"id": len(self.comments) + 1, "body": body["body"]}
            self.comments.append(comment)
            return comment
        raise AssertionError(f"unexpected POST {path}")

    def patch(self, path, body):
        self._record("PATCH", path)
        if "/issues/comments/" in path:
            comment_id = int(path.rsplit("/", 1)[-1])
            for comment in self.comments:
                if comment["id"] == comment_id:
                    comment["body"] = body["body"]
                    return comment
        if "/pulls/" in path:
            self.pr_state_writes.append((path, body))
            return body
        raise AssertionError(f"unexpected PATCH {path}")

    def delete(self, path):
        self._record("DELETE", path)
        label = unquote(path.rsplit("/", 1)[-1])
        self.issue["labels"] = [
            item for item in self.issue.get("labels", []) if item["name"] != label
        ]
        return None

    def paginate(self, path, *, list_key=None, max_pages=10):
        if path.endswith("/labels?per_page=100"):
            self._record("GET", path)
            return [{"name": name} for name in sorted(self.repo_labels)]
        if path.endswith("/comments?per_page=100"):
            self._record("GET", path)
            return list(self.comments)
        if path.endswith("/files?per_page=100"):
            self._record("GET", path)
            return list(self.files)
        if "issues?state=all" in path:
            self._record("GET", path)
            return [self.issue]
        raise AssertionError(f"unexpected paginate {path}")


class ScriptedTransportGH(GH):
    def __init__(self, script):
        super().__init__(
            "crownthrive1/CrownThrive-OS",
            token="token",
            max_attempts=1,
            inline_wait_seconds=0,
            sleeper=lambda _: None,
            clock=lambda: 1_700_000_000.0,
            randomizer=lambda: 0.0,
        )
        self.script = list(script)

    def _request_once(self, method, path, body, *, token):
        self.request_count += 1
        if token:
            self.authenticated_request_count += 1
        else:
            self.public_request_count += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        self.last_transport = "authenticated" if token else "public-fallback"
        return item


def rate_limit_error(method="GET", path="/repos/x/y/issues/1"):
    return GitHubRequestError(
        method=method,
        path=path,
        status=403,
        body='{"message":"API rate limit exceeded for installation"}',
        headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1700003600",
            "X-RateLimit-Resource": "core",
            "X-GitHub-Request-Id": "TEST:123",
        },
    )


class PentaGitHubTaggerTests(unittest.TestCase):
    def test_lane_and_risk_classification(self):
        files = (
            ".github/workflows/penta-github-tagger.yml",
            "supabase/migrations/20260826220000_penta.sql",
            "docs/penta/tagger.md",
        )
        lanes = classify_lanes(
            "Wire PentaTagger to production",
            "Add GitHub labels and migration",
            files,
        )
        self.assertIn("workflow", lanes)
        self.assertIn("database", lanes)
        self.assertIn("docs", lanes)
        self.assertEqual(classify_risk("production", "migration", files, lanes), "d2")

    def test_docs_only_is_d0(self):
        files = ("docs/penta/PENTA_TAGGER.md", "README.md")
        lanes = classify_lanes("Document PentaTagger", "Guide only", files)
        self.assertIn("docs", lanes)
        self.assertEqual(
            classify_risk("Document PentaTagger", "Guide only", files, lanes),
            "d0",
        )

    def test_open_pr_preserves_pentapr_close_and_projects_close_stage(self):
        issue = {
            "number": 91,
            "title": "Close superseded provider PR",
            "body": "Superseded by #92",
            "state": "open",
            "html_url": "https://github.test/pr/91",
            "pull_request": {},
            "labels": [{"name": "penta:close"}, {"name": "custom:keep"}],
        }
        pr = {
            "number": 91,
            "title": issue["title"],
            "body": issue["body"],
            "state": "open",
            "merged": False,
            "draft": False,
            "html_url": issue["html_url"],
        }
        gh = FakeGH(
            issue=issue,
            pr=pr,
            files=[{"filename": "runtime/provider/adapter.py"}],
        )
        receipt = tag_entity(gh, 91)
        labels = {item["name"] for item in issue["labels"]}
        self.assertEqual(receipt["status"], "PASS")
        self.assertIn("penta:close", labels)
        self.assertIn("custom:keep", labels)
        self.assertIn("penta:stage:close-candidate", labels)
        self.assertIn("penta:authority:tagger", labels)
        self.assertIn("penta:entity:pr", labels)
        self.assertFalse(gh.pr_state_writes, "PentaTagger must never close or merge")
        self.assertEqual(len(gh.comments), 1)

    def test_closed_merged_pr_gets_terminal_merged_and_removes_stage(self):
        issue = {
            "number": 93,
            "title": "Merged workflow",
            "body": "",
            "state": "closed",
            "html_url": "https://github.test/pr/93",
            "pull_request": {},
            "labels": [{"name": "penta:stage:review"}],
        }
        pr = {
            "number": 93,
            "title": issue["title"],
            "body": "",
            "state": "closed",
            "merged": True,
            "draft": False,
            "html_url": issue["html_url"],
        }
        gh = FakeGH(
            issue=issue,
            pr=pr,
            files=[{"filename": ".github/workflows/x.yml"}],
        )
        receipt = tag_entity(gh, 93)
        labels = {item["name"] for item in issue["labels"]}
        self.assertEqual(receipt["terminal"], "penta:terminal:merged")
        self.assertIn("penta:terminal:merged", labels)
        self.assertNotIn("penta:stage:review", labels)

    def test_receipt_comment_is_idempotent_and_second_pass_uses_no_api(self):
        issue = {
            "number": 94,
            "title": "Docs",
            "body": "",
            "state": "open",
            "html_url": "https://github.test/issues/94",
            "labels": [],
        }
        gh = FakeGH(issue=issue)
        first = tag_entity(gh, 94)
        calls_after_first = len(gh.calls)
        second_entity = Entity(
            number=94,
            kind="issue",
            title=issue["title"],
            body=issue["body"],
            state="open",
            merged=False,
            draft=False,
            labels={item["name"] for item in issue["labels"]},
            files=(),
            html_url=issue["html_url"],
            source="event_payload",
        )
        second = tag_entity(gh, 94, entity=second_entity, preserve_semantics=True)
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(len(gh.comments), 1)
        self.assertEqual(second["comment_state"], "unchanged-no-api")
        self.assertEqual(len(gh.calls), calls_after_first)

    def test_event_target_and_entity_resolution(self):
        payload = {
            "action": "closed",
            "pull_request": {
                "number": 77,
                "title": "Close",
                "body": "",
                "state": "closed",
                "merged": True,
                "draft": False,
                "html_url": "https://github.test/pr/77",
                "labels": [{"name": "penta:lane:workflow"}],
            },
        }
        entity = entity_from_event_payload(payload)
        self.assertIsNotNone(entity)
        self.assertEqual(entity.number, 77)
        self.assertTrue(entity.merged)
        self.assertEqual(entity.source, "event_payload")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "event.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(target_from_event(str(path)), 77)

    def test_event_snapshot_with_complete_labels_performs_zero_api_calls(self):
        labels = {
            "penta:tagged",
            "penta:authority:tagger",
            "penta:entity:pr",
            "penta:lane:workflow",
            "penta:risk:d2",
            "penta:stage:review",
        }
        issue = {
            "number": 101,
            "title": "production workflow",
            "body": "",
            "state": "open",
            "html_url": "https://github.test/pr/101",
            "pull_request": {},
            "labels": [{"name": label} for label in sorted(labels)],
        }
        gh = FakeGH(issue=issue, pr={})
        entity = Entity(
            number=101,
            kind="pr",
            title="production workflow",
            body="",
            state="open",
            merged=False,
            draft=False,
            labels=labels,
            files=(),
            html_url=issue["html_url"],
            source="event_payload",
        )
        receipt = tag_entity(gh, 101, entity=entity, preserve_semantics=True)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["readback_source"], "event_payload")
        self.assertEqual(gh.calls, [])

    def test_authenticated_get_rate_limit_uses_public_fallback(self):
        gh = ScriptedTransportGH(
            [
                rate_limit_error(),
                {"number": 1, "labels": []},
            ]
        )
        result = gh.get("/repos/crownthrive1/CrownThrive-OS/issues/1")
        self.assertEqual(result["number"], 1)
        self.assertEqual(gh.authenticated_request_count, 1)
        self.assertEqual(gh.public_request_count, 1)
        self.assertEqual(gh.last_transport, "public-fallback")

    def test_rate_limited_write_is_explicitly_deferred(self):
        gh = ScriptedTransportGH(
            [rate_limit_error(method="POST", path="/repos/x/y/issues/1/labels")]
        )
        with self.assertRaises(RateLimitDeferred) as caught:
            gh.post("/repos/x/y/issues/1/labels", {"labels": ["penta:tagged"]})
        self.assertEqual(caught.exception.evidence.remaining, 0)
        self.assertEqual(caught.exception.evidence.resource, "core")
        self.assertEqual(caught.exception.evidence.request_id, "TEST:123")

    def test_missing_label_bootstrap_is_on_demand(self):
        issue = {
            "number": 104,
            "title": "Issue",
            "body": "",
            "state": "open",
            "html_url": "https://github.test/issues/104",
            "labels": [],
        }
        gh = FakeGH(issue=issue)
        gh.repo_labels.clear()
        gh.fail_unknown_labels = True
        add_labels(gh, 104, {"penta:tagged"})
        self.assertIn("penta:tagged", gh.repo_labels)
        self.assertIn(
            "penta:tagged",
            {item["name"] for item in issue["labels"]},
        )

    def test_sweep_recovers_recent_closed_entities(self):
        issue = {
            "number": 105,
            "title": "Closed",
            "body": "",
            "state": "closed",
            "html_url": "https://github.test/issues/105",
            "labels": [],
        }
        gh = FakeGH(issue=issue)
        numbers = sweep_numbers(gh, "all", 10, since_hours=72)
        self.assertEqual(numbers, [105])
        requested = " ".join(path for _, path in gh.calls)
        self.assertIn("state=all", requested)
        self.assertIn("since=", requested)

    def test_write_outputs_preserves_deferred_state(self):
        receipt = {
            "number": 1,
            "kind": "pr",
            "status": "DEFERRED",
            "risk": "unknown",
            "lanes": [],
            "stage": None,
            "terminal": None,
            "readback_source": "not_available",
            "digest": "a" * 64,
            "retry_at": "2026-08-27T20:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = str(Path(tmp) / "receipt.json")
            summary_path = str(Path(tmp) / "summary.md")
            payload = write_outputs([receipt], receipt_path, summary_path)
            self.assertEqual(payload["status"], "DEFERRED")
            self.assertIn("DEFERRED", Path(summary_path).read_text(encoding="utf-8"))

    def test_main_returns_75_and_writes_summary_on_rate_limit(self):
        # Patch the module-level GH constructor with a scripted transport.
        import penta_github_tagger as module

        original = module.GH
        scripted = ScriptedTransportGH(
            [
                rate_limit_error(path="/repos/crownthrive1/CrownThrive-OS/issues?state=all"),
                rate_limit_error(path="/repos/crownthrive1/CrownThrive-OS/issues?state=all"),
            ]
        )
        module.GH = lambda *args, **kwargs: scripted
        try:
            with tempfile.TemporaryDirectory() as tmp:
                receipt_path = str(Path(tmp) / "receipt.json")
                summary_path = str(Path(tmp) / "summary.md")
                code = main(
                    [
                        "sweep",
                        "--repo",
                        "crownthrive1/CrownThrive-OS",
                        "--receipt-path",
                        receipt_path,
                        "--summary-path",
                        summary_path,
                    ]
                )
                self.assertEqual(code, EXIT_DEFERRED)
                payload = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
                self.assertEqual(payload["status"], "DEFERRED")
                self.assertTrue(Path(summary_path).exists())
        finally:
            module.GH = original

    def test_all_expected_labels_have_specs(self):
        required = {
            "penta:tagged",
            "penta:entity:pr",
            "penta:entity:issue",
            "penta:authority:tagger",
            "penta:authority:pr",
            "penta:authority:merge",
            "penta:authority:closer",
            "penta:stage:close-candidate",
            "penta:terminal:closed",
            "penta:terminal:merged",
            "penta:hold",
        }
        self.assertTrue(required.issubset(LABEL_SPECS))


if __name__ == "__main__":
    unittest.main()
