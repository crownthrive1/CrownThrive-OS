#!/usr/bin/env python3
"""Fail closed on autonomous release and publication governance bypasses."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PENTARELEASE = ROOT / ".github/workflows/pentarelease-autonomous-awareness.yml"
MAJOR_PUBLISHER = ROOT / ".github/workflows/crownthrive-os-v2-release.yml"
PUBLISHED_RECONCILER = ROOT / ".github/workflows/pentarelease-published-release-reconciler.yml"
COMPREHENSIVE_SURFACE = ROOT / ".github/workflows/pentarelease-comprehensive-release-surface.yml"
HISTORICAL_BACKFILL = ROOT / ".github/workflows/pentarelease-comprehensive-historical-backfill.yml"
MAJOR_VALIDATOR = ROOT / "scripts/pentarelease/validate_major_release.py"
MAJOR_TERMS_TEMPLATE = ROOT / ".pentarelease/templates/major-release-terms.v4.0.0.0.template.json"
MAJOR_REQUEST_TEMPLATE = ROOT / ".pentarelease/templates/major-release-request.v4.0.0.0.template.json"
GOVERNED_GATE = ROOT / ".github/workflows/governed-merge-gate.yml"
CHLOM_PUBLISHER = ROOT / ".github/workflows/chlom-continuous-publisher.yml"
RUNTIME_POLICY = ROOT / "developers/manifests/github-actions-runtime-policy.v1.json"
RUNTIME_STANDARD = ROOT / "standards/github-actions-runtime-supply-chain-standard.md"


class InvariantViolation(ValueError):
    """Raised when an executable release-governance invariant is absent."""


def _read(path: Path) -> str:
    if not path.is_file():
        raise InvariantViolation(f"missing governed file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def _require(text: str, fragment: str, context: str) -> None:
    if fragment not in text:
        raise InvariantViolation(f"{context}: required invariant missing: {fragment!r}")


def _forbid(text: str, pattern: str, context: str) -> None:
    if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
        raise InvariantViolation(f"{context}: prohibited bypass matched {pattern!r}")


def _require_order(text: str, fragments: tuple[str, ...], context: str) -> None:
    offsets = []
    for fragment in fragments:
        offset = text.find(fragment)
        if offset < 0:
            raise InvariantViolation(f"{context}: ordered invariant missing: {fragment!r}")
        offsets.append(offset)
    if offsets != sorted(offsets) or len(set(offsets)) != len(offsets):
        raise InvariantViolation(f"{context}: governance operations are out of order")


def _reject_pentarelease_bypasses(text: str) -> None:
    context = PENTARELEASE.relative_to(ROOT).as_posix()
    prohibited = (
        r"\bgh\s+workflow\s+run\s+governed-merge-gate(?:\.yml)?\b",
        r"\bTARGET\s*=\s*[\"']?\$BRANCH\b",
        r"\bgh\s+release\s+edit\b",
        r"\bgh\s+release\s+upload\b[^\n]*\s--clobber\b",
        r"\bfallback\b|\bfalling\s+back\b",
    )
    for pattern in prohibited:
        _forbid(text, pattern, context)


def validate_pentarelease() -> None:
    text = _read(PENTARELEASE)
    context = PENTARELEASE.relative_to(ROOT).as_posix()
    _reject_pentarelease_bypasses(text)
    for fragment in (
        "timeout-minutes: 30",
        "'target_ref':'main'",
        '"target": "main"',
        'PR_URL=$(gh pr create --base main --head "$BRANCH"',
        'gh pr merge "$PR_URL" --merge --delete-branch',
        'MERGE_SHA=$(gh pr view "$PR_URL" --json state,mergeCommit',
        'git merge-base --is-ancestor "$HEAD_SHA" "$MERGE_SHA"',
        'git merge-base --is-ancestor "$MERGE_SHA" origin/main',
        'TARGET="$MERGE_SHA"',
        'gh release create "$TAG" --target "$TARGET"',
        "sha256sum --strict --check SHA256SUMS",
    ):
        _require(text, fragment, context)
    target_assignments = re.findall(r'^\s*TARGET=(.+)$', text, flags=re.MULTILINE)
    if target_assignments != ['"$MERGE_SHA"']:
        raise InvariantViolation(
            f"{context}: release target must have one exact merge-SHA assignment; "
            f"observed={target_assignments}"
        )
    _require_order(
        text,
        (
            'git push origin "$BRANCH"',
            "PR_URL=$(gh pr create",
            'commits/${HEAD_SHA}/check-runs',
            'gh pr merge "$PR_URL"',
            'git merge-base --is-ancestor "$HEAD_SHA" "$MERGE_SHA"',
            'TARGET="$MERGE_SHA"',
            'gh release create "$TAG" --target "$TARGET"',
        ),
        context,
    )


def _reject_major_publisher_bypasses(text: str) -> None:
    context = MAJOR_PUBLISHER.relative_to(ROOT).as_posix()
    for pattern in (
        r"\bgh\s+release\s+edit\b",
        r"\bgh\s+release\s+upload\b[^\n]*--clobber\b",
        r"\bTARGET=\$\(jq\b",
        r"\bTARGET=[\"']?main\b",
        r"\bprovider_write_authorized[\"']?\s*[:=]\s*[\"']?true\b.*\bwithout",
    ):
        _forbid(text, pattern, context)


def validate_major_publisher() -> None:
    text = _read(MAJOR_PUBLISHER)
    validator = _read(MAJOR_VALIDATOR)
    context = MAJOR_PUBLISHER.relative_to(ROOT).as_posix()
    _reject_major_publisher_bypasses(text)
    for fragment in (
        "ref: ${{ github.sha }}",
        'TARGET="$GITHUB_SHA"',
        'test "$TARGET" = "$GITHUB_SHA"',
        'git diff --diff-filter=A --name-only "$TARGET^1" "$TARGET"',
        'git merge-base --is-ancestor "$HEAD_SHA" "$TARGET"',
        'test "$(git rev-parse "$TARGET^2")" = "$HEAD_SHA"',
        'test "$(git rev-parse "$HEAD_SHA^{tree}")" = "$(git rev-parse "$TARGET^{tree}")"',
        'gh pr checks "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --required',
        "author_association",
        "scripts/pentarelease/validate_major_release.py",
        '.provider_write_authorized == true',
        'cmp --silent "$EXISTING_DIR/$NAME" "dist/pentarelease/$NAME"',
        'gh release create "$TAG"',
        'gh release upload "$TAG"',
        '(.assets | length) == 5',
        "sha256sum --strict --check SHA256SUMS",
        'test "$(git rev-parse "${PREVIOUS_RELEASE_TAG}^{commit}")" = "$PREVIOUS_RELEASE_TAG_SHA"',
        'git merge-base --is-ancestor "$SOURCE_BASELINE_SHA" "$SOURCE_HEAD_SHA"',
        'test "$SOURCE_BASELINE_SHA" = "$TAG_PARENT"',
        ".lineage.legacy_generated_release_parent_allowlist[]",
    ):
        _require(text, fragment, context)
    for fragment in (
        "CROWNTHRIVE_D3_MAJOR_RELEASE_APPROVED",
        'EXPECTED_APPROVER = "crownthrive1"',
        'record.get("author_association") != "OWNER"',
        'record.get("commit_id") != head_sha',
        '"terms_sha256": terms_sha256',
        '"request_sha256": request_sha256',
        'require(gate["state"] == "PASS"',
        "validate_no_private_conversation",
    ):
        _require(validator, fragment, MAJOR_VALIDATOR.relative_to(ROOT).as_posix())
    _require_order(
        text,
        (
            "Checkout immutable main-push merge",
            "Resolve immutable request and event-bound merge target",
            "Prove governed PR head H and accepted merge M",
            "Validate exact package and build deterministic artifacts",
            "Establish fresh or exact-identity partial publication state",
            "Resolve live human D3 authority and validate all thirteen gates",
            'gh release create "$TAG"',
            "Verify exact provider identity and downloaded checksums",
        ),
        context,
    )

    gates = {
        f"CT-MAJOR-{number:03d}"
        for number in range(1, 14)
    }
    observed = set(re.findall(r'"(CT-MAJOR-\d{3})"', validator))
    if observed != gates:
        raise InvariantViolation(
            f"{MAJOR_VALIDATOR.relative_to(ROOT)}: exact thirteen-gate identity drift: "
            f"observed={sorted(observed)}"
        )
    for path in (MAJOR_TERMS_TEMPLATE, MAJOR_REQUEST_TEMPLATE):
        payload = json.loads(_read(path))
        if payload.get("validity", {}).get("single_use_nonce") is not None and path == MAJOR_TERMS_TEMPLATE:
            raise InvariantViolation(f"{path.relative_to(ROOT)}: template nonce must remain unassigned")
    request = json.loads(_read(MAJOR_REQUEST_TEMPLATE))
    if request.get("idempotency_key") is not None or request.get("candidate_binding", {}).get("frozen_head_sha") is not None:
        raise InvariantViolation("major request template manufactures candidate or approval identity")
    if any(gate.get("state") != "PASS" for gate in request.get("prepublication_gates", [])) is False:
        raise InvariantViolation("major request template must remain HOLD/UNKNOWN until frozen")


def validate_provider_writer_lease() -> None:
    shared = "group: pentarelease-provider-writes-${{ github.repository }}"
    workflows = (
        MAJOR_PUBLISHER,
        PENTARELEASE,
        PUBLISHED_RECONCILER,
        COMPREHENSIVE_SURFACE,
        HISTORICAL_BACKFILL,
    )
    for path in workflows:
        text = _read(path)
        context = path.relative_to(ROOT).as_posix()
        if text.count(shared) != 1:
            raise InvariantViolation(f"{context}: provider-write workflow lacks the one shared lease")
        _require(text, "cancel-in-progress: false", context)

    autonomous = _read(PENTARELEASE)
    _require(autonomous, "Yield to the human D3 major-release lane", str(PENTARELEASE))
    _require(autonomous, "human_d3_major_request_pending", str(PENTARELEASE))
    _require(autonomous, "human_d3_major_release_lane_staged", str(PENTARELEASE))
    _require_order(
        autonomous,
        (
            "Yield to the human D3 major-release lane",
            "Observe repository and decide",
            "Materialize autonomous release package",
            "gh release create",
        ),
        str(PENTARELEASE),
    )
    _require(_read(PUBLISHED_RECONCILER), "Human D3 v4 is protected", str(PUBLISHED_RECONCILER))
    _require(_read(COMPREHENSIVE_SURFACE), "cannot mutate the exact-five-asset human D3 v4 release", str(COMPREHENSIVE_SURFACE))
    _require(_read(HISTORICAL_BACKFILL), "Skipping protected exact-five-asset human D3 v4 release", str(HISTORICAL_BACKFILL))


def validate_governed_gate() -> None:
    text = _read(GOVERNED_GATE)
    context = GOVERNED_GATE.relative_to(ROOT).as_posix()
    manual_rejection = """      - name: Reject manual dispatch as merge acceptance
        if: github.event_name == 'workflow_dispatch'
        shell: bash
        run: |
          echo 'Manual validation cannot certify a pull request or release candidate.' >&2
          exit 78
"""
    _require(text, manual_rejection, context)
    for fragment in (
        '- "pentarelease/**"',
        '- "chlom/publication-**"',
        "startsWith(github.ref, 'refs/heads/pentarelease/')",
        "startsWith(github.ref, 'refs/heads/chlom/publication-')",
        "run: python scripts/validate_release_governance_invariants.py",
    ):
        _require(text, fragment, context)
    if text.count("startsWith(github.ref, 'refs/heads/pentarelease/')") < 4:
        raise InvariantViolation(f"{context}: PentaRelease branches do not receive every exact-diff gate")
    if text.count("startsWith(github.ref, 'refs/heads/chlom/publication-')") < 4:
        raise InvariantViolation(f"{context}: CHLOM candidates do not receive every exact-diff gate")
    _require_order(
        text,
        ("Reject manual dispatch as merge acceptance", "Check out repository"),
        context,
    )


def _reject_direct_main_push(text: str) -> None:
    context = CHLOM_PUBLISHER.relative_to(ROOT).as_posix()
    for line in text.splitlines():
        if not re.search(r"\bgit\s+push\b", line):
            continue
        if re.search(r"(?:HEAD:|refs/heads/|\s)main(?:\s|[\"']|$)", line):
            raise InvariantViolation(f"{context}: direct-main git push is prohibited: {line.strip()}")
    _forbid(text, r"\bgh\s+pr\s+merge\b", context)


def validate_chlom_publisher() -> None:
    text = _read(CHLOM_PUBLISHER)
    context = CHLOM_PUBLISHER.relative_to(ROOT).as_posix()
    _reject_direct_main_push(text)
    for fragment in (
        "pull-requests: write",
        'BRANCH="chlom/publication-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"',
        'git push origin "HEAD:refs/heads/$BRANCH"',
        'PR_URL=$(gh pr create --base main --head "$BRANCH"',
        'publication_state="candidate_pr"',
        'pull_request_url:$pr_url',
        'resolved="$(realpath -m -- "$path")"',
        'if [[ -L "$path" ]]',
    ):
        _require(text, fragment, context)
    push_commands = [
        line.strip()
        for line in text.splitlines()
        if re.search(r"\bgit\s+push\b", line)
    ]
    if push_commands != ['git push origin "HEAD:refs/heads/$BRANCH"']:
        raise InvariantViolation(
            f"{context}: only the exact candidate-branch push is permitted; "
            f"observed={push_commands}"
        )
    _require_order(
        text,
        (
            'git push origin "HEAD:refs/heads/$BRANCH"',
            "PR_URL=$(gh pr create",
            "publication_state=\"candidate_pr\"",
            "action:\"ack\"",
        ),
        context,
    )


def validate_action_inventory_alignment() -> None:
    policy = json.loads(_read(RUNTIME_POLICY))
    approved = {
        item["uses"]: (item["version"], item["sha"])
        for item in policy.get("approved_actions", [])
    }
    if not approved:
        raise InvariantViolation("runtime policy contains no approved action inventory")

    table = {}
    row = re.compile(
        r"^\| `(?P<action>[^`]+)` \| `(?P<version>[^`]+)` \| "
        r"`(?P<sha>[0-9a-f]{40})` \| Node 24 \|",
        flags=re.MULTILINE,
    )
    for match in row.finditer(_read(RUNTIME_STANDARD)):
        table[match.group("action")] = (match.group("version"), match.group("sha"))
    if table != approved:
        missing = sorted(set(approved) - set(table))
        extra = sorted(set(table) - set(approved))
        drifted = sorted(key for key in set(table) & set(approved) if table[key] != approved[key])
        raise InvariantViolation(
            "runtime standard/action policy drift: "
            f"missing={missing}, extra={extra}, drifted={drifted}"
        )


def self_test() -> None:
    negative_vectors = (
        (_reject_pentarelease_bypasses, 'TARGET="$BRANCH"'),
        (_reject_pentarelease_bypasses, "gh workflow run governed-merge-gate.yml"),
        (_reject_pentarelease_bypasses, "falling back to the exact branch"),
        (_reject_direct_main_push, "git push origin HEAD:main"),
        (_reject_direct_main_push, 'git push origin "HEAD:refs/heads/main"'),
        (_reject_direct_main_push, 'gh pr merge "$PR_URL" --merge'),
        (_reject_major_publisher_bypasses, 'TARGET=$(jq -r .target "$REQUEST")'),
        (_reject_major_publisher_bypasses, 'gh release edit "$TAG" --target main'),
        (_reject_major_publisher_bypasses, 'gh release upload "$TAG" asset.zip --clobber'),
    )
    for validator, vector in negative_vectors:
        try:
            validator(vector)
        except InvariantViolation:
            continue
        raise AssertionError(f"negative vector was not rejected: {vector!r}")


def validate_all() -> None:
    validate_pentarelease()
    validate_major_publisher()
    validate_provider_writer_lease()
    validate_governed_gate()
    validate_chlom_publisher()
    validate_action_inventory_alignment()


def main() -> int:
    self_test()
    try:
        validate_all()
    except (InvariantViolation, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    print("Release governance invariants: PASS")
    print("- PentaRelease publication requires an exact merged-main commit")
    print("- human D3 major publication binds owner evidence to exact PR head and main merge")
    print("- every provider-writing PentaRelease workflow shares one non-cancelling lease")
    print("- manual governed-gate dispatch cannot produce merge acceptance")
    print("- CHLOM publication is candidate-branch and pull-request only")
    print("- action SHA documentation matches the executable machine policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
