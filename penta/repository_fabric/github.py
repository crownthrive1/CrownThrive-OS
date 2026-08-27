#!/usr/bin/env python3
"""Authenticated, read-only GitHub observation adapter for repository fabric.

Restricted repository locators are supplied at runtime and are never included in
the adapter output.  The adapter retains an in-process allow-set of observations
that were assembled from authenticated provider responses; RepositoryFabric
uses that independent verifier instead of trusting a JSON `verified` flag.
"""

from __future__ import annotations

import base64
import fnmatch
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .fabric import (
    PUBLIC_REPOSITORY_RE,
    ConvergenceError,
    canonical_sha256,
    validate_control_plane,
)


class GitHubObservationError(ConvergenceError):
    """A sanitized provider observation failure."""


JsonTransport = Callable[[str, str], Any]


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent bearer credentials from following provider redirects."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


class GitHubRepositoryObserver:
    """Collect exact-head GitHub readback without returning provider locators."""

    API_VERSION = "2022-11-28"
    MAX_RESPONSE_BYTES = 2_000_000
    MAX_ATTESTATION_BYTES = 65_536

    def __init__(
        self,
        policy: Mapping[str, Any],
        *,
        token: str,
        restricted_bindings: Mapping[str, str],
        api_base: str = "https://api.github.com",
        transport: JsonTransport | None = None,
    ):
        if not isinstance(token, str) or not token.strip() or any(char.isspace() for char in token):
            raise GitHubObservationError("repository read credential is unbound")
        self.policy = dict(policy)
        rows = validate_control_plane(self.policy)
        self.nodes = {row["stable_id"]: row for row in rows}
        restricted_ids = {
            row["stable_id"] for row in rows if row["visibility_class"] == "restricted"
        }
        if set(restricted_bindings) != restricted_ids:
            raise GitHubObservationError("restricted repository binding census mismatch")
        self.bindings: dict[str, str] = {}
        for stable_id, repository in restricted_bindings.items():
            if not isinstance(repository, str) or not PUBLIC_REPOSITORY_RE.fullmatch(repository):
                raise GitHubObservationError(f"invalid restricted binding for {stable_id}")
            self.bindings[stable_id] = repository
        public_locators = {
            str(row["repository"]).lower()
            for row in rows
            if row["visibility_class"] == "public"
        }
        restricted_locators = [repository.lower() for repository in self.bindings.values()]
        if (
            len(restricted_locators) != len(set(restricted_locators))
            or public_locators.intersection(restricted_locators)
        ):
            raise GitHubObservationError("repository runtime bindings are not one-to-one")
        self.token = token
        self.api_base = api_base.rstrip("/")
        parsed_api = urllib.parse.urlsplit(self.api_base)
        if transport is None and (
            parsed_api.scheme != "https"
            or parsed_api.hostname != "api.github.com"
            or parsed_api.username is not None
            or parsed_api.password is not None
            or parsed_api.port not in {None, 443}
            or parsed_api.path not in {"", "/"}
            or parsed_api.query
            or parsed_api.fragment
        ):
            raise GitHubObservationError("GitHub API credential destination is not allowlisted")
        self.transport = transport or self._request_json
        self._verified: set[tuple[str, str]] = set()

    def _request_json(self, path: str, stable_id: str) -> Any:
        request = urllib.request.Request(
            self.api_base + path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self.token,
                "User-Agent": "CrownThrive-PentaRepositoryFabric/1.0",
                "X-GitHub-Api-Version": self.API_VERSION,
            },
            method="GET",
        )
        try:
            opener = urllib.request.build_opener(_NoRedirectHandler)
            with opener.open(request, timeout=20) as response:
                final = urllib.parse.urlsplit(response.geturl())
                if final.scheme != "https" or final.hostname != "api.github.com":
                    raise GitHubObservationError(
                        f"provider redirect boundary failed for {stable_id}"
                    )
                payload = response.read(self.MAX_RESPONSE_BYTES + 1)
        except GitHubObservationError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            status = getattr(exc, "code", "transport")
            raise GitHubObservationError(
                f"provider readback failed for {stable_id} ({status})"
            ) from None
        if len(payload) > self.MAX_RESPONSE_BYTES:
            raise GitHubObservationError(f"provider response too large for {stable_id}")
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GitHubObservationError(f"provider returned invalid JSON for {stable_id}") from None
        if not isinstance(value, (Mapping, list)):
            raise GitHubObservationError(f"provider response shape invalid for {stable_id}")
        return value

    @staticmethod
    def _repository_path(repository: str) -> str:
        owner, name = repository.split("/", 1)
        return "/repos/" + urllib.parse.quote(owner, safe="") + "/" + urllib.parse.quote(name, safe="")

    def _locator(self, spec: Mapping[str, Any]) -> str:
        if spec["visibility_class"] == "public":
            return str(spec["repository"])
        return self.bindings[str(spec["stable_id"])]

    def _attestation(self, base: str, head_sha: str, stable_id: str) -> dict[str, Any]:
        path = (
            base
            + "/contents/.crownthrive/penta-node.v1.json?"
            + urllib.parse.urlencode({"ref": head_sha})
        )
        response = self.transport(path, stable_id)
        if not isinstance(response, Mapping):
            raise GitHubObservationError(f"node attestation response invalid for {stable_id}")
        if response.get("type") != "file" or response.get("encoding") != "base64":
            raise GitHubObservationError(f"node attestation response invalid for {stable_id}")
        encoded = response.get("content")
        if not isinstance(encoded, str):
            raise GitHubObservationError(f"node attestation content missing for {stable_id}")
        try:
            raw = base64.b64decode("".join(encoded.split()), validate=True)
        except ValueError:
            raise GitHubObservationError(f"node attestation encoding invalid for {stable_id}") from None
        if len(raw) > self.MAX_ATTESTATION_BYTES:
            raise GitHubObservationError(f"node attestation too large for {stable_id}")
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GitHubObservationError(f"node attestation JSON invalid for {stable_id}") from None
        if not isinstance(value, dict):
            raise GitHubObservationError(f"node attestation shape invalid for {stable_id}")
        return value

    def _build_readback(self, base: str, head_sha: str, branch: str, stable_id: str) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {"branch": branch, "head_sha": head_sha, "status": "completed", "per_page": 30}
        )
        response = self.transport(base + "/actions/runs?" + query, stable_id)
        if not isinstance(response, Mapping):
            return {"state": "unknown", "head_sha": None, "evidence": "provider_shape_invalid"}
        runs = response.get("workflow_runs")
        if not isinstance(runs, list):
            return {"state": "unknown", "head_sha": None, "evidence": "provider_shape_invalid"}
        approved_paths = {
            ".github/workflows/penta-federated-build.yml",
            ".github/workflows/penta-repository-convergence.yml",
        }
        for run in runs:
            if not isinstance(run, Mapping):
                continue
            workflow_path = str(run.get("path", "")).split("@", 1)[0]
            if (
                run.get("head_sha") == head_sha
                and run.get("head_branch") == branch
                and run.get("status") == "completed"
                and run.get("conclusion") == "success"
                and run.get("event") in {"push", "schedule", "workflow_dispatch"}
                and workflow_path in approved_paths
            ):
                return {
                    "state": "passed",
                    "head_sha": head_sha,
                    "evidence": "exact_head_approved_workflow_readback",
                }
        return {"state": "unknown", "head_sha": None, "evidence": "no_matching_success"}

    @staticmethod
    def _ruleset_applies_to_default_branch(ruleset: Mapping[str, Any], branch: str) -> bool:
        if ruleset.get("enforcement") != "active" or ruleset.get("target") != "branch":
            return False
        conditions = ruleset.get("conditions")
        if not isinstance(conditions, Mapping):
            return False
        ref_name = conditions.get("ref_name")
        if not isinstance(ref_name, Mapping):
            return False
        include = ref_name.get("include", [])
        exclude = ref_name.get("exclude", [])
        if not isinstance(include, list) or not isinstance(exclude, list):
            return False
        ref = f"refs/heads/{branch}"

        def matches(pattern: object) -> bool:
            return isinstance(pattern, str) and (
                pattern in {"~ALL", "~DEFAULT_BRANCH", branch, ref}
                or fnmatch.fnmatchcase(ref, pattern)
            )

        included = bool(include) and any(matches(item) for item in include)
        excluded = any(matches(item) for item in exclude)
        return included and not excluded

    def _release_governance_readback(
        self, base: str, head_sha: str, branch: str, stable_id: str
    ) -> dict[str, Any]:
        policy = self.policy["release_governance"]
        required = set(policy["required_check_contexts"])
        summaries: list[Any] = []
        for page in range(1, 11):
            response = self.transport(
                base + f"/rulesets?per_page=100&page={page}", stable_id
            )
            if not isinstance(response, list):
                raise GitHubObservationError(
                    f"provider ruleset response invalid for {stable_id}"
                )
            summaries.extend(response)
            if len(response) < 100:
                break
        else:
            raise GitHubObservationError(
                f"provider ruleset census exceeds bounded readback for {stable_id}"
            )

        applicable: list[Mapping[str, Any]] = []
        seen_ruleset_ids: set[int] = set()
        for summary in summaries:
            if not isinstance(summary, Mapping):
                raise GitHubObservationError(
                    f"provider ruleset summary invalid for {stable_id}"
                )
            ruleset_id = summary.get("id")
            if not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool):
                raise GitHubObservationError(
                    f"provider ruleset identity invalid for {stable_id}"
                )
            if ruleset_id in seen_ruleset_ids:
                raise GitHubObservationError(
                    f"provider ruleset identity duplicated for {stable_id}"
                )
            seen_ruleset_ids.add(ruleset_id)
            detail = self.transport(base + f"/rulesets/{ruleset_id}", stable_id)
            if not isinstance(detail, Mapping) or detail.get("id") != ruleset_id:
                raise GitHubObservationError(
                    f"provider ruleset detail invalid for {stable_id}"
                )
            if detail.get("enforcement") == "active" and detail.get("target") == "branch":
                conditions = detail.get("conditions")
                ref_name = conditions.get("ref_name") if isinstance(conditions, Mapping) else None
                if (
                    not isinstance(ref_name, Mapping)
                    or not isinstance(ref_name.get("include"), list)
                    or not isinstance(ref_name.get("exclude"), list)
                ):
                    raise GitHubObservationError(
                        f"provider ruleset conditions invalid for {stable_id}"
                    )
            if self._ruleset_applies_to_default_branch(detail, branch):
                applicable.append(detail)

        bypass_count = 0
        required_bindings: set[tuple[str, int | None]] = set()
        for ruleset in applicable:
            bypass = ruleset.get("bypass_actors", [])
            rules = ruleset.get("rules", [])
            if not isinstance(bypass, list) or not isinstance(rules, list):
                raise GitHubObservationError(f"provider ruleset detail invalid for {stable_id}")
            bypass_count += len(bypass)
            for rule in rules:
                if not isinstance(rule, Mapping) or rule.get("type") != "required_status_checks":
                    continue
                parameters = rule.get("parameters")
                checks = (
                    parameters.get("required_status_checks", [])
                    if isinstance(parameters, Mapping)
                    else []
                )
                if not isinstance(checks, list):
                    raise GitHubObservationError(
                        f"provider required-check rules invalid for {stable_id}"
                    )
                for check in checks:
                    if not isinstance(check, Mapping):
                        raise GitHubObservationError(
                            f"provider required-check detail invalid for {stable_id}"
                        )
                    context = check.get("context")
                    integration_id = check.get("integration_id")
                    if not isinstance(context, str) or not context:
                        raise GitHubObservationError(
                            f"provider required-check context invalid for {stable_id}"
                        )
                    if integration_id is not None and (
                        not isinstance(integration_id, int)
                        or isinstance(integration_id, bool)
                        or integration_id <= 0
                    ):
                        raise GitHubObservationError(
                            f"provider required-check integration invalid for {stable_id}"
                        )
                    required_bindings.add((context, integration_id))

        ruleset_contexts = {context for context, _ in required_bindings}

        latest_checks: dict[tuple[str, int | None], Mapping[str, Any]] = {}
        for page in range(1, 11):
            response = self.transport(
                base + f"/commits/{head_sha}/check-runs?per_page=100&page={page}",
                stable_id,
            )
            runs = response.get("check_runs") if isinstance(response, Mapping) else None
            if not isinstance(runs, list):
                raise GitHubObservationError(f"provider check-run response invalid for {stable_id}")
            for run in runs:
                if not isinstance(run, Mapping):
                    raise GitHubObservationError(
                        f"provider check-run entry invalid for {stable_id}"
                    )
                name = run.get("name")
                run_id = run.get("id")
                if (
                    not isinstance(name, str)
                    or not name
                    or not isinstance(run_id, int)
                    or isinstance(run_id, bool)
                ):
                    raise GitHubObservationError(
                        f"provider check-run identity invalid for {stable_id}"
                    )
                app = run.get("app")
                app_id = app.get("id") if isinstance(app, Mapping) else None
                if not isinstance(app_id, int) or isinstance(app_id, bool) or app_id <= 0:
                    app_id = None
                for key in ((name, None), (name, app_id)):
                    current = latest_checks.get(key)
                    if current is None or run_id > int(current.get("id", -1)):
                        latest_checks[key] = run
            if len(runs) < 100:
                break

        latest_statuses: dict[str, Mapping[str, Any]] = {}
        for page in range(1, 11):
            status_response = self.transport(
                base + f"/commits/{head_sha}/status?per_page=100&page={page}", stable_id
            )
            statuses = (
                status_response.get("statuses")
                if isinstance(status_response, Mapping)
                else None
            )
            if not isinstance(statuses, list):
                raise GitHubObservationError(
                    f"provider commit-status response invalid for {stable_id}"
                )
            for status in statuses:
                if not isinstance(status, Mapping):
                    raise GitHubObservationError(
                        f"provider commit-status entry invalid for {stable_id}"
                    )
                context = status.get("context")
                status_id = status.get("id")
                if (
                    not isinstance(context, str)
                    or not context
                    or not isinstance(status_id, int)
                    or isinstance(status_id, bool)
                ):
                    raise GitHubObservationError(
                        f"provider commit-status identity invalid for {stable_id}"
                    )
                current = latest_statuses.get(context)
                if current is None or status_id > int(current.get("id", -1)):
                    latest_statuses[context] = status
            if len(statuses) < 100:
                break

        successful_bindings: set[tuple[str, int | None]] = set()
        for context, integration_id in required_bindings:
            check = latest_checks.get((context, integration_id))
            status = latest_statuses.get(context)
            if check is not None and check.get("status") == "completed" and check.get("conclusion") == "success":
                successful_bindings.add((context, integration_id))
            elif integration_id is None and status is not None and status.get("state") == "success":
                successful_bindings.add((context, integration_id))

        successful = {
            context
            for context in ruleset_contexts
            if all(
                binding in successful_bindings
                for binding in required_bindings
                if binding[0] == context
            )
        }

        active = bool(applicable)
        policy_contexts_bound = required.issubset(ruleset_contexts)
        all_ruleset_contexts_successful = bool(required_bindings) and required_bindings.issubset(
            successful_bindings
        )
        passed = (
            active
            and bypass_count <= policy["max_bypass_actor_count"]
            and policy_contexts_bound
            and required.issubset(successful)
            and all_ruleset_contexts_successful
        )
        return {
            "state": "passed" if passed else "hold",
            "head_sha": head_sha,
            "active_default_branch_ruleset": active,
            "applicable_ruleset_count": len(applicable),
            "bypass_actor_count": bypass_count,
            "required_contexts": sorted(required),
            "successful_contexts": sorted(required.intersection(successful)),
            "all_ruleset_contexts_successful": all_ruleset_contexts_successful,
        }

    def observe_node(self, spec: Mapping[str, Any], *, observed_at: str | None = None) -> dict[str, Any]:
        stable_id = str(spec["stable_id"])
        repository = self._locator(spec)
        base = self._repository_path(repository)
        metadata = self.transport(base, stable_id)
        if not isinstance(metadata, Mapping):
            raise GitHubObservationError(f"provider metadata invalid for {stable_id}")
        if metadata.get("full_name") != repository:
            raise GitHubObservationError(f"provider repository identity mismatch for {stable_id}")
        branch = metadata.get("default_branch")
        visibility = metadata.get("visibility")
        if not isinstance(branch, str) or not isinstance(visibility, str):
            raise GitHubObservationError(f"provider metadata incomplete for {stable_id}")
        ref_path = base + "/git/ref/heads/" + urllib.parse.quote(branch, safe="")
        ref = self.transport(ref_path, stable_id)
        if not isinstance(ref, Mapping):
            raise GitHubObservationError(f"provider head readback invalid for {stable_id}")
        ref_object = ref.get("object")
        head_sha = ref_object.get("sha") if isinstance(ref_object, Mapping) else None
        if not isinstance(head_sha, str):
            raise GitHubObservationError(f"provider head readback missing for {stable_id}")
        if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
            raise GitHubObservationError(f"provider head readback invalid for {stable_id}")
        if metadata.get("archived") is not False or metadata.get("disabled") is not False:
            raise GitHubObservationError(f"provider repository is not active for {stable_id}")
        attestation = self._attestation(base, head_sha, stable_id)
        body: dict[str, Any] = {
            "schema": "ct.penta.repository-observation.v1",
            "source_adapter": "ct.adapter.github-repository-read.v1",
            "stable_id": stable_id,
            "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
            "default_branch": branch,
            "provider_visibility": visibility,
            "head_sha": head_sha,
            "node_attestation": attestation,
            "node_attestation_sha256": canonical_sha256(attestation),
            "build": self._build_readback(base, head_sha, branch, stable_id),
        }
        if stable_id == self.policy["release_governance"]["stable_id"]:
            body["release_governance"] = self._release_governance_readback(
                base, head_sha, branch, stable_id
            )
        body["observation_sha256"] = canonical_sha256(body)
        self._verified.add((stable_id, body["observation_sha256"]))
        return body

    def collect(
        self, *, observed_at: str | None = None
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        observations: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        for stable_id in sorted(self.nodes):
            try:
                observations[stable_id] = self.observe_node(
                    self.nodes[stable_id], observed_at=observed_at
                )
            except GitHubObservationError as exc:
                # The exception is deliberately coordinate-free.
                errors[stable_id] = str(exc)
            except Exception:
                # Unexpected transport/shape failures still fail closed without
                # reflecting credentials or restricted provider coordinates.
                errors[stable_id] = f"provider observer internal failure for {stable_id}"
        return observations, errors

    def verify_observation(
        self, spec: Mapping[str, Any], observation: Mapping[str, Any]
    ) -> bool:
        stable_id = spec.get("stable_id")
        digest = observation.get("observation_sha256")
        return isinstance(stable_id, str) and isinstance(digest, str) and (stable_id, digest) in self._verified
