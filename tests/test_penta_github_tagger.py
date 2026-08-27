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
    classify_lanes,
    classify_risk,
    tag_entity,
    target_from_event,
)
from penta_github_labels import LABEL_SPECS  # noqa: E402


class FakeGH:
    def __init__(self, *, issue, pr=None, files=None):
        self.repo = "crownthrive1/CrownThrive-OS"
        self.issue = issue
        self.pr = pr
        self.files = files or []
        self.repo_labels = set()
        self.comments = []
        self.pr_state_writes = []

    def get(self, path):
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
        if path.startswith(f"/repos/{self.repo}/issues?state=open"):
            return [self.issue]
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, body):
        if path.endswith("/labels") and "/issues/" not in path:
            self.repo_labels.add(body["name"])
            return body
        if "/issues/" in path and path.endswith("/labels"):
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
        label = unquote(path.rsplit("/", 1)[-1])
        self.issue["labels"] = [item for item in self.issue.get("labels", []) if item["name"] != label]
        return None

    def paginate(self, path, *, list_key=None, max_pages=10):
        if path.endswith("/labels?per_page=100"):
            return [{"name": name} for name in sorted(self.repo_labels)]
        if path.endswith("/comments?per_page=100"):
            return list(self.comments)
        if path.endswith("/files?per_page=100"):
            return list(self.files)
        if "issues?state=open" in path:
            return [self.issue]
        raise AssertionError(f"unexpected paginate {path}")


class PentaGitHubTaggerTests(unittest.TestCase):
    def test_lane_and_risk_classification(self):
        files = (
            ".github/workflows/penta-github-tagger.yml",
            "supabase/migrations/20260826220000_penta.sql",
            "docs/penta/tagger.md",
        )
        lanes = classify_lanes("Wire PentaTagger to production", "Add GitHub labels and migration", files)
        self.assertIn("workflow", lanes)
        self.assertIn("database", lanes)
        self.assertIn("docs", lanes)
        self.assertEqual(classify_risk("production", "migration", files, lanes), "d2")

    def test_docs_only_is_d0(self):
        files = ("docs/penta/PENTA_TAGGER.md", "README.md")
        lanes = classify_lanes("Document PentaTagger", "Guide only", files)
        self.assertIn("docs", lanes)
        self.assertEqual(classify_risk("Document PentaTagger", "Guide only", files, lanes), "d0")

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
        gh = FakeGH(issue=issue, pr=pr, files=[{"filename": "runtime/provider/adapter.py"}])
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
        gh = FakeGH(issue=issue, pr=pr, files=[{"filename": ".github/workflows/x.yml"}])
        receipt = tag_entity(gh, 93)
        labels = {item["name"] for item in issue["labels"]}
        self.assertEqual(receipt["terminal"], "penta:terminal:merged")
        self.assertIn("penta:terminal:merged", labels)
        self.assertNotIn("penta:stage:review", labels)

    def test_receipt_comment_is_idempotent(self):
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
        second = tag_entity(gh, 94)
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(len(gh.comments), 1)
        self.assertEqual(second["comment_state"], "unchanged")

    def test_event_target_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "event.json"
            path.write_text(json.dumps({"pull_request": {"number": 77}}), encoding="utf-8")
            self.assertEqual(target_from_event(str(path)), 77)

    def test_all_expected_labels_have_specs(self):
        required = {
            "penta:tagged", "penta:entity:pr", "penta:entity:issue",
            "penta:authority:tagger", "penta:authority:pr",
            "penta:authority:merge", "penta:authority:closer",
            "penta:stage:close-candidate", "penta:terminal:closed",
            "penta:terminal:merged", "penta:hold",
        }
        self.assertTrue(required.issubset(LABEL_SPECS))


if __name__ == "__main__":
    unittest.main()
