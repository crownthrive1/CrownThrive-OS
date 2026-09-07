from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from penta_github_tagger import tag_entity  # noqa: E402


class LifecycleRaceGH:
    def __init__(self, *, labels=None, inject_concurrent=False):
        self.repo = "crownthrive1/CrownThrive-OS"
        self.issue = {
            "number": 3448,
            "title": "Repository resources reconciliation",
            "body": "Governed registry correction",
            "state": "open",
            "html_url": "https://github.test/pr/3448",
            "pull_request": {},
            "labels": [{"name": name} for name in (labels or [])],
        }
        self.pr = {
            "number": 3448,
            "title": self.issue["title"],
            "body": self.issue["body"],
            "state": "open",
            "merged": False,
            "draft": False,
            "html_url": self.issue["html_url"],
        }
        self.files = [{"filename": ".crownthrive/resources/repository-resources.v1.json"}]
        self.inject_concurrent = inject_concurrent
        self.injected = False
        self.deleted = []
        self.request_count = 0
        self.last_transport = "fake-provider"

    def get(self, path):
        self.request_count += 1
        if "/issues/" in path and "/comments" not in path:
            names = {item["name"] for item in self.issue["labels"]}
            if (
                self.inject_concurrent
                and not self.injected
                and "penta:authority:tagger" in names
            ):
                self.issue["labels"].append({"name": "penta:stage:nurture"})
                self.injected = True
            return self.issue
        if "/pulls/" in path and "/files" not in path:
            return self.pr
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, body):
        self.request_count += 1
        if path.endswith("/labels"):
            names = {item["name"] for item in self.issue["labels"]}
            names.update(body["labels"])
            self.issue["labels"] = [{"name": name} for name in sorted(names)]
            return self.issue["labels"]
        raise AssertionError(f"unexpected POST {path}")

    def delete(self, path):
        self.request_count += 1
        label = unquote(path.rsplit("/", 1)[-1])
        self.deleted.append(label)
        self.issue["labels"] = [
            item for item in self.issue["labels"] if item["name"] != label
        ]
        return None

    def paginate(self, path, *, list_key=None, max_pages=10):
        self.request_count += 1
        if path.endswith("/files?per_page=100"):
            return list(self.files)
        raise AssertionError(f"unexpected paginate {path}")


def labels_of(gh):
    return {item["name"] for item in gh.issue["labels"]}


def test_open_pr_preserves_existing_pentapr_lifecycle():
    gh = LifecycleRaceGH(labels=["penta:stage:nurture"])
    receipt = tag_entity(gh, 3448, comment=False)
    labels = labels_of(gh)
    assert receipt["status"] == "PASS"
    assert receipt["stage"] == "penta:stage:nurture"
    assert "penta:stage:nurture" in labels
    assert "penta:stage:review" not in labels
    assert "penta:stage:nurture" not in gh.deleted


def test_open_pr_accepts_concurrent_pentapr_lifecycle_write():
    gh = LifecycleRaceGH(inject_concurrent=True)
    receipt = tag_entity(gh, 3448, comment=False)
    labels = labels_of(gh)
    assert receipt["status"] == "PASS"
    assert receipt["stage"] == "penta:stage:nurture"
    assert "penta:stage:nurture" in labels
    assert "penta:stage:review" not in labels
    assert gh.injected is True
