from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import penta_pr_autopilot as autopilot  # noqa: E402
import penta_pr_lifecycle as lifecycle  # noqa: E402
from penta_github_labels import LABEL_SPECS  # noqa: E402

REPO = "crownthrive1/CrownThrive-OS"
RULE_MESSAGE = (
    'Repository rule violations found\n\nRequired status check '
    '"CrownThrive governed merge gate" is expected.\n\n'
)


class Provider:
    """In-memory HTTP boundary; exercises the real GH client and sweep."""

    def __init__(self):
        self.pulls = {
            number: {
                "number": number,
                "title": f"Candidate {number}",
                "body": "",
                "state": "open",
                "merged": False,
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "head": {"sha": str(number) * 40},
            }
            for number in (1, 2)
        }
        self.labels = {number: {"penta:tagged", "custom:keep"} for number in self.pulls}
        self.comments = {number: [] for number in self.pulls}
        self.checks = {
            number: [{
                "id": number,
                "app": {"slug": "github-actions"},
                "name": "CrownThrive governed merge gate",
                "status": "completed",
                "conclusion": "success",
            }]
            for number in self.pulls
        }
        self.merge_error: BaseException | tuple[int, str] | None = (
            405, json.dumps({"message": RULE_MESSAGE})
        )
        self.requests = []

    def urlopen(self, request, timeout):
        assert timeout == 30
        method = request.get_method()
        path = urlsplit(request.full_url).path
        route = path.removeprefix(f"/repos/{REPO}/").split("/")
        body = json.loads(request.data) if request.data else None
        self.requests.append((method, path, body))
        result = self.respond(method, path, route, body)
        return io.BytesIO(json.dumps(result).encode())

    def respond(self, method, path, route, body):
        if method == "GET" and route == ["labels"]:
            return [{"name": name} for name in LABEL_SPECS]
        if method == "GET" and route == ["pulls"]:
            return [pull for pull in self.pulls.values() if pull["state"] == "open"]
        if route[0] == "commits":
            number = next(n for n, p in self.pulls.items() if p["head"]["sha"] == route[1])
            if method == "GET" and route[2] == "check-runs":
                return {"check_runs": self.checks[number]}
            if method == "GET" and route[2] == "status":
                return {"state": "pending", "total_count": 0, "statuses": []}
        if route[:2] == ["issues", "comments"] and method == "PATCH":
            comment = next(c for cs in self.comments.values() for c in cs if c["id"] == int(route[2]))
            comment.update(body)
            return comment
        number = int(route[1])
        if method == "GET" and route[0] == "pulls":
            return self.pulls[number]
        if route[0] == "issues":
            if method == "GET" and len(route) == 2:
                return {"number": number, "labels": [{"name": n} for n in self.labels[number]]}
            if route[2] == "comments":
                if method == "GET":
                    return self.comments[number]
                if method == "POST":
                    comment = {"id": number * 100 + len(self.comments[number]), **body}
                    self.comments[number].append(comment)
                    return comment
            if route[2] == "labels":
                if method == "POST":
                    self.labels[number].update(body["labels"])
                    return [{"name": n} for n in self.labels[number]]
                if method == "DELETE":
                    self.labels[number].discard(unquote(route[3]))
                    return None
        if method == "PUT" and route == ["pulls", str(number), "merge"]:
            if number == 1 and self.merge_error is not None:
                if isinstance(self.merge_error, BaseException):
                    raise self.merge_error
                status, raw = self.merge_error
                raise urllib.error.HTTPError(
                    lifecycle.API + path, status, "provider refusal", {}, io.BytesIO(raw.encode())
                )
            self.pulls[number].update(state="closed", merged=True)
            return {"merged": True, "message": "Pull Request successfully merged"}
        raise AssertionError(f"unexpected provider operation: {method} {path}")

    def merge_requests(self, number):
        return [r for r in self.requests if r[:2] == ("PUT", f"/repos/{REPO}/pulls/{number}/merge")]


class AutopilotMergeHoldTests(unittest.TestCase):
    @contextlib.contextmanager
    def mocked_provider(self, provider):
        output = io.StringIO()
        with (
            patch.dict("os.environ", {"GITHUB_TOKEN": "local-test-token"}),
            patch.object(sys, "argv", ["penta_pr_autopilot.py", "--repo", REPO]),
            patch.object(lifecycle, "SELF_LIFECYCLE_CHECK_NAMES", lifecycle.SELF_LIFECYCLE_CHECK_NAMES),
            patch("urllib.request.urlopen", side_effect=provider.urlopen),
            contextlib.redirect_stdout(output),
        ):
            yield output

    def assert_held_unmerged(self, provider):
        self.assertFalse(provider.pulls[1]["merged"])
        self.assertEqual(provider.pulls[1]["state"], "open")
        self.assertFalse(any(n.startswith("penta:terminal:") for n in provider.labels[1]))
        self.assertNotIn("penta:authority:merge", provider.labels[1])
        self.assertNotIn("penta:authority:closer", provider.labels[1])
        self.assertFalse(any(r[0] == "PATCH" and r[1].endswith("/pulls/1") for r in provider.requests))

    def test_required_check_rejection_holds_one_pr_and_continues_sweep(self):
        provider = Provider()
        with self.mocked_provider(provider) as output:
            self.assertEqual(autopilot.main(), 0)
        self.assert_held_unmerged(provider)
        self.assertEqual(len(provider.merge_requests(1)), 1, "no retry after provider denial")
        self.assertEqual(
            provider.merge_requests(1)[0][2],
            {"merge_method": "squash", "sha": "1" * 40, "commit_title": "PentaMerge: Candidate 1"},
        )
        self.assertIn("#1 terminal=HOLD reason=provider_merge_rule_rejection status=405", output.getvalue())
        self.assertIn(json.dumps(RULE_MESSAGE), output.getvalue())
        self.assertNotIn("#1 merged=True", output.getvalue())
        self.assertTrue(provider.pulls[2]["merged"])
        self.assertIn("penta:terminal:merged", provider.labels[2])
        self.assertIn("#2 merged=True", output.getvalue())
        self.assertEqual(len(provider.merge_requests(2)), 1)

    def test_blocked_provider_state_skips_merge_on_repeated_sweeps(self):
        provider = Provider()
        provider.pulls[1]["mergeable_state"] = "blocked"
        with self.mocked_provider(provider) as output:
            self.assertEqual(autopilot.main(), 0)
            self.assertEqual(autopilot.main(), 0)
        self.assert_held_unmerged(provider)
        self.assertFalse(provider.merge_requests(1))
        self.assertEqual(output.getvalue().count("#1 terminal=HOLD reason=provider_merge_blocked"), 2)
        self.assertTrue(provider.pulls[2]["merged"])

    def test_explicit_rule_rejection_header_variants_hold_and_continue(self):
        for message in (
            'Repository rule violations found: Required status check "gate" is expected.',
            'Repository rule violations found:\n\nRequired status check "gate" has failed.\n',
            'Repository rule violations found\r\n\r\nRequired status check "gate" is expected.\r\n',
        ):
            with self.subTest(message=message):
                provider = Provider()
                provider.merge_error = (405, json.dumps({"message": message}))
                with self.mocked_provider(provider) as output:
                    self.assertEqual(autopilot.main(), 0)
                self.assert_held_unmerged(provider)
                self.assertEqual(len(provider.merge_requests(1)), 1)
                self.assertTrue(provider.pulls[2]["merged"])
                self.assertIn("terminal=HOLD reason=provider_merge_rule_rejection", output.getvalue())

    def test_missing_failed_and_pending_checks_remain_ineligible(self):
        for state in ("missing", "failure", "pending", "action_required"):
            with self.subTest(state=state):
                provider = Provider()
                if state == "missing":
                    provider.checks[1] = []
                elif state == "pending":
                    provider.checks[1][0].update(status="in_progress", conclusion=None)
                else:
                    provider.checks[1][0]["conclusion"] = state
                with self.mocked_provider(provider):
                    self.assertEqual(autopilot.main(), 0)
                self.assert_held_unmerged(provider)
                self.assertFalse(provider.merge_requests(1))
                self.assertIn("penta:nurture", provider.labels[1])
                self.assertTrue(provider.pulls[2]["merged"])

    def test_operator_hold_and_draft_still_prevent_merge(self):
        for restriction in ("hold", "draft"):
            with self.subTest(restriction=restriction):
                provider = Provider()
                if restriction == "hold":
                    provider.labels[1].add("penta:hold")
                else:
                    provider.pulls[1]["draft"] = True
                with self.mocked_provider(provider):
                    self.assertEqual(autopilot.main(), 0)
                self.assert_held_unmerged(provider)
                self.assertFalse(provider.merge_requests(1))
                self.assertTrue(provider.pulls[2]["merged"])

    def test_non_target_http_errors_abort_without_terminal_labels_or_retry(self):
        cases = [
            (401, {"message": "Bad credentials"}),
            (403, {"message": "Resource not accessible by integration"}),
            (403, {"message": "API rate limit exceeded"}),
            (429, {"message": "API rate limit exceeded"}),
            (500, {"message": RULE_MESSAGE}),
            (502, {"message": RULE_MESSAGE}),
            (503, {"message": RULE_MESSAGE}),
            (409, {"message": "Head branch was modified"}),
            (422, {"message": "Validation Failed"}),
            (405, {"message": "Unexpected method error"}),
            (405, {"message": "Repository rule violations found"}),
            (405, {"message": "Repository rule violations found:\n\n"}),
            (405, {"message": "Repository rule violations found\n\n"}),
            (405, {"message": "Repository rule violations foundry: unknown"}),
            (405, {"message": "Repository rule violations found:unknown"}),
            (405, {"message": RULE_MESSAGE, "merged": True}),
            (405, {"message": RULE_MESSAGE, "merged": "false"}),
            (405, {"message": None}),
            (405, ["Repository rule violations found:"]),
            (405, "Repository rule violations found:"),
        ]
        for status, payload in cases:
            with self.subTest(status=status, payload=payload):
                provider = Provider()
                provider.merge_error = (status, json.dumps(payload))
                with self.mocked_provider(provider) as output:
                    with self.assertRaises(lifecycle.GitHubAPIError) as raised:
                        autopilot.main()
                self.assertEqual(raised.exception.status, status)
                self.assert_held_unmerged(provider)
                self.assertEqual(len(provider.merge_requests(1)), 1)
                self.assertFalse(provider.merge_requests(2))
                self.assertNotIn("terminal=HOLD", output.getvalue())

    def test_malformed_error_response_is_not_a_confirmed_rejection(self):
        provider = Provider()
        provider.merge_error = (405, "<html>Repository rule violations found:</html>")
        with self.mocked_provider(provider):
            with self.assertRaises(lifecycle.GitHubAPIError) as raised:
                autopilot.main()
        self.assertIsNone(raised.exception.response)
        self.assert_held_unmerged(provider)
        self.assertFalse(provider.merge_requests(2))

    def test_uncertain_transport_and_programming_errors_abort(self):
        for error in (
            TimeoutError("merge outcome unknown"),
            urllib.error.URLError("connection reset after send"),
            RuntimeError("PUT /merge -> 405: Repository rule violations found:"),
            KeyError("unexpected payload"),
            json.JSONDecodeError("invalid merge response", "", 0),
        ):
            with self.subTest(error=type(error).__name__):
                provider = Provider()
                provider.merge_error = error
                with self.mocked_provider(provider):
                    with self.assertRaises(type(error)):
                        autopilot.main()
                self.assert_held_unmerged(provider)
                self.assertEqual(len(provider.merge_requests(1)), 1)
                self.assertFalse(provider.merge_requests(2))

    def test_rejection_is_bound_to_exact_merge_method_and_target(self):
        for method, path in (
            ("GET", f"/repos/{REPO}/pulls/1/merge"),
            ("POST", f"/repos/{REPO}/issues/1/labels"),
            ("PUT", f"/repos/{REPO}/pulls/2/merge"),
            ("PUT", f"/repos/{REPO}/pulls/1/update-branch"),
            ("PUT", "/repos/another/repository/pulls/1/merge"),
        ):
            with self.subTest(method=method, path=path):
                provider = Provider()
                error = lifecycle.GitHubAPIError(method, path, 405, json.dumps({"message": RULE_MESSAGE}))
                with self.mocked_provider(provider), patch.object(lifecycle, "attempt_merge", side_effect=error):
                    with self.assertRaises(lifecycle.GitHubAPIError):
                        autopilot.main()
                self.assert_held_unmerged(provider)
                self.assertFalse(provider.merge_requests(2))

    def test_successful_merge_behavior_and_exact_head_are_preserved(self):
        provider = Provider()
        provider.merge_error = None
        with self.mocked_provider(provider):
            self.assertEqual(autopilot.main(), 0)
        for number in (1, 2):
            self.assertTrue(provider.pulls[number]["merged"])
            self.assertIn("penta:terminal:merged", provider.labels[number])
            self.assertEqual(provider.merge_requests(number)[0][2]["sha"], str(number) * 40)

    def test_shared_closer_still_raises_instead_of_closing_after_rejection(self):
        provider = Provider()
        provider.labels[1].update(lifecycle.PRECLOSE_REQUIRED_LABELS)
        state = {
            "disposition": "CLOSE",
            "reason": "superseded_or_represented",
            "head_sha": "1" * 40,
        }
        provider.comments[1].append({
            "id": 100,
            "body": f"<!-- penta-pr-lifecycle:{json.dumps(state)} -->",
        })
        with self.mocked_provider(provider):
            with self.assertRaises(lifecycle.GitHubAPIError):
                lifecycle.pentacloser(lifecycle.GH(REPO), 1)
        self.assert_held_unmerged(provider)
        self.assertEqual(len(provider.merge_requests(1)), 1)

    def test_http_error_preserves_structure_cause_and_runtimeerror_compatibility(self):
        provider = Provider()
        with self.mocked_provider(provider):
            with self.assertRaises(RuntimeError) as raised:
                lifecycle.GH(REPO).put(f"/repos/{REPO}/pulls/1/merge", {"sha": "1" * 40})
        error = raised.exception
        self.assertIsInstance(error, lifecycle.GitHubAPIError)
        self.assertEqual(error.method, "PUT")
        self.assertEqual(error.path, f"/repos/{REPO}/pulls/1/merge")
        self.assertEqual(error.status, 405)
        self.assertEqual(error.response["message"], RULE_MESSAGE)
        self.assertIsInstance(error.__cause__, urllib.error.HTTPError)
        self.assertEqual(str(error), f"PUT /repos/{REPO}/pulls/1/merge -> 405: {json.dumps({'message': RULE_MESSAGE})}")


if __name__ == "__main__":
    unittest.main()
