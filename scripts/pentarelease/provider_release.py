#!/usr/bin/env python3
"""Resolve and reuse verified GitHub release truth for PentaRelease surfaces.

This adapter keeps provider availability separate from release truth:
- canonical tag selection comes from fetched local Git tags;
- the exact candidate must be independently verified through the GitHub provider;
- authenticated GitHub REST is the hot read path;
- rate-limited authenticated reads may fail over once to the unauthenticated public
  GitHub REST endpoint for the same exact tag; that warm path is read-only;
- exact release assets may be recovered through their provider-verified public
  GitHub download URLs without consuming installation API quota;
- 403/429/5xx and network failures remain bounded and ultimately fail closed;
- authenticated 404, mismatched tags, drafts, asset identity drift, size drift, and
  digest drift fail closed immediately;
- the verified provider payload can be reused by release_surface.py without a
  second provider lookup that could disagree because of rate limits or API lag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable

VERSION_TAG = re.compile(r"^v\d+(?:\.\d+){2,3}$")
RETRYABLE_HTTP_STATUS = {403, 429, 500, 502, 503, 504}
PUBLIC_READ_FAILOVER_STATUS = {403, 429}
DEFAULT_ATTEMPTS = 12
MAX_DELAY_SECONDS = 30


class ProviderReleaseError(RuntimeError):
    """Fail-closed provider release resolution error."""


class ProviderPublicReadUnavailable(ProviderReleaseError):
    """Public GitHub provider read could not establish external release truth."""


def _version_key(tag: str) -> tuple[tuple[int, int, int, int], int]:
    raw = tag[1:] if tag.startswith("v") else tag
    numbers = [int(part) for part in raw.split(".")]
    padded = tuple((numbers + [0] * (4 - len(numbers)))[:4])
    return padded, len(numbers)


def select_latest_version_tag(tags: Iterable[str]) -> str:
    candidates = [tag.strip() for tag in tags if VERSION_TAG.fullmatch(tag.strip())]
    return max(candidates, key=_version_key) if candidates else ""


def resolve_local_tag(requested_tag: str | None = None) -> str:
    requested = (requested_tag or "").strip()
    if requested:
        if not VERSION_TAG.fullmatch(requested):
            raise ProviderReleaseError(f"unsupported_release_tag:{requested}")
        probe = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", f"refs/tags/{requested}^{{commit}}"],
            text=True,
            capture_output=True,
        )
        if probe.returncode:
            raise ProviderReleaseError(f"local_release_tag_missing:{requested}")
        return requested

    tags = subprocess.check_output(["git", "tag", "--list"], text=True).splitlines()
    selected = select_latest_version_tag(tags)
    if not selected:
        raise ProviderReleaseError("no_local_release_tag")
    return selected


def _retry_delay(headers: Any, attempt: int) -> int:
    retry_after = None
    reset_at = None
    if headers is not None:
        retry_after = headers.get("Retry-After")
        reset_at = headers.get("X-RateLimit-Reset")
    if retry_after:
        try:
            return max(1, min(MAX_DELAY_SECONDS, int(float(retry_after))))
        except (TypeError, ValueError):
            pass
    if reset_at:
        try:
            delta = int(float(reset_at)) - int(time.time()) + 1
            return max(1, min(MAX_DELAY_SECONDS, delta))
        except (TypeError, ValueError):
            pass
    return max(1, min(MAX_DELAY_SECONDS, attempt * 5))


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")[:1000]
    except Exception:
        return ""


def _split_repository(repository: str) -> tuple[str, str]:
    if repository.count("/") != 1:
        raise ProviderReleaseError(f"invalid_repository:{repository}")
    owner, name = repository.split("/", 1)
    if not owner or not name:
        raise ProviderReleaseError(f"invalid_repository:{repository}")
    return owner, name


def _provider_release_url(repository: str, tag: str) -> str:
    owner, name = _split_repository(repository)
    return (
        "https://api.github.com/repos/"
        f"{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(name, safe='')}"
        f"/releases/tags/{urllib.parse.quote(tag, safe='')}"
    )


def _provider_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CrownThrive-PentaRelease",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def validate_provider_release(payload: dict[str, Any], expected_tag: str) -> dict[str, Any]:
    if payload.get("tag_name") != expected_tag:
        raise ProviderReleaseError(
            f"provider_release_tag_mismatch:expected={expected_tag}:actual={payload.get('tag_name')}"
        )
    if payload.get("draft") is not False:
        raise ProviderReleaseError(f"provider_release_not_published:{expected_tag}")
    return payload


def _read_provider_once(
    url: str,
    tag: str,
    headers: dict[str, str],
    *,
    timeout: int,
    opener: Callable[..., Any],
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with opener(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ProviderReleaseError("provider_release_payload_not_object")
    return validate_provider_release(payload, tag)


def fetch_public_provider_release(
    repository: str,
    tag: str,
    *,
    timeout: int = 20,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """Read exact public GitHub release truth without consuming installation quota.

    This is a warm, read-only provider path. Transport/visibility failures are
    intentionally distinct from semantic release failures so a tag mismatch or
    draft response can never be downgraded into a retry or local fallback.
    """
    url = _provider_release_url(repository, tag)
    try:
        return _read_provider_once(
            url,
            tag,
            _provider_headers(),
            timeout=timeout,
            opener=opener,
        )
    except urllib.error.HTTPError as exc:
        body = _read_error_body(exc)
        raise ProviderPublicReadUnavailable(
            f"provider_public_http_{exc.code}:{body}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderPublicReadUnavailable(
            f"provider_public_network_error:{exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ProviderPublicReadUnavailable(
            f"provider_public_invalid_json:{exc}"
        ) from exc


def fetch_provider_release(
    repository: str,
    tag: str,
    token: str,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    timeout: int = 20,
    sleep_fn: Callable[[float], None] = time.sleep,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    url = _provider_release_url(repository, tag)

    if not token:
        try:
            payload = fetch_public_provider_release(
                repository,
                tag,
                timeout=timeout,
                opener=opener,
            )
            print(
                f"PentaRelease verified {tag} through public GitHub REST warm read "
                "because no installation token was available.",
                file=sys.stderr,
            )
            return payload
        except ProviderPublicReadUnavailable as exc:
            raise ProviderReleaseError(
                f"provider_token_missing:public_read_unavailable:{exc}"
            ) from exc

    headers = _provider_headers(token)
    last_error = "provider_read_failed"
    public_failover_attempted = False
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return _read_provider_once(
                url,
                tag,
                headers,
                timeout=timeout,
                opener=opener,
            )
        except urllib.error.HTTPError as exc:
            body = _read_error_body(exc)
            last_error = f"provider_http_{exc.code}:{body}"
            if exc.code == 404:
                raise ProviderReleaseError(f"provider_release_not_found:{tag}") from exc
            if exc.code not in RETRYABLE_HTTP_STATUS:
                raise ProviderReleaseError(last_error) from exc

            if (
                exc.code in PUBLIC_READ_FAILOVER_STATUS
                and not public_failover_attempted
            ):
                public_failover_attempted = True
                try:
                    payload = fetch_public_provider_release(
                        repository,
                        tag,
                        timeout=timeout,
                        opener=opener,
                    )
                    print(
                        f"PentaRelease verified {tag} through public GitHub REST warm read "
                        f"after authenticated provider HTTP {exc.code}.",
                        file=sys.stderr,
                    )
                    return payload
                except ProviderPublicReadUnavailable as public_exc:
                    last_error = f"{last_error}:public_warm={public_exc}"

            if attempt >= attempts:
                break
            delay = _retry_delay(exc.headers, attempt)
            print(
                f"PentaRelease authenticated provider read unavailable for {tag} "
                f"(HTTP {exc.code}, attempt {attempt}/{attempts}); retrying in {delay}s.",
                file=sys.stderr,
            )
            sleep_fn(delay)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = f"provider_network_error:{exc}"
            if attempt >= attempts:
                break
            delay = min(MAX_DELAY_SECONDS, max(1, attempt * 5))
            print(
                f"PentaRelease authenticated provider network read unavailable for {tag} "
                f"(attempt {attempt}/{attempts}); retrying in {delay}s.",
                file=sys.stderr,
            )
            sleep_fn(delay)
        except (json.JSONDecodeError, ProviderReleaseError):
            raise

    raise ProviderReleaseError(f"provider_read_retry_exhausted:{tag}:{last_error}")


def write_verified_release(repository: str, tag: str, output: Path, token: str) -> dict[str, Any]:
    payload = fetch_provider_release(repository, tag, token)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(output)
    return payload


def load_verified_release(path: Path, expected_tag: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProviderReleaseError("verified_release_payload_not_object")
    return validate_provider_release(payload, expected_tag)


def _select_verified_asset(
    payload: dict[str, Any],
    expected_tag: str,
    asset_name: str,
) -> dict[str, Any]:
    validate_provider_release(payload, expected_tag)
    if not asset_name or "/" in asset_name or "\\" in asset_name:
        raise ProviderReleaseError(f"invalid_release_asset_name:{asset_name}")
    matches = [
        asset for asset in (payload.get("assets") or [])
        if isinstance(asset, dict) and asset.get("name") == asset_name
    ]
    if not matches:
        raise ProviderReleaseError(
            f"verified_release_asset_missing:{expected_tag}:{asset_name}"
        )
    if len(matches) != 1:
        raise ProviderReleaseError(
            f"verified_release_asset_ambiguous:{expected_tag}:{asset_name}"
        )
    return matches[0]


def _verified_asset_url(
    repository: str,
    tag: str,
    asset_name: str,
    asset: dict[str, Any],
) -> str:
    url = asset.get("browser_download_url")
    if not isinstance(url, str) or not url:
        raise ProviderReleaseError(
            f"verified_release_asset_url_missing:{tag}:{asset_name}"
        )
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "github.com":
        raise ProviderReleaseError(
            f"verified_release_asset_url_untrusted:{tag}:{asset_name}"
        )
    if parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
        raise ProviderReleaseError(
            f"verified_release_asset_url_untrusted:{tag}:{asset_name}"
        )
    owner, repo = _split_repository(repository)
    decoded_path = urllib.parse.unquote(parsed.path)
    expected_path = f"/{owner}/{repo}/releases/download/{tag}/{asset_name}"
    if decoded_path != expected_path:
        raise ProviderReleaseError(
            f"verified_release_asset_url_mismatch:{tag}:{asset_name}"
        )
    return url


def download_verified_release_asset(
    release_json: Path,
    repository: str,
    tag: str,
    asset_name: str,
    output: Path,
    *,
    timeout: int = 30,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """Recover one exact asset from an already provider-verified public release.

    The initial URL is constrained to the canonical GitHub release download path
    for the exact repository/tag/name. No installation token is sent. Provider
    size and optional SHA-256 digest are independently checked before atomic write.
    """
    payload = load_verified_release(release_json, tag)
    asset = _select_verified_asset(payload, tag, asset_name)
    url = _verified_asset_url(repository, tag, asset_name, asset)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CrownThrive-PentaRelease"},
        method="GET",
    )
    try:
        with opener(request, timeout=timeout) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        body = _read_error_body(exc)
        raise ProviderReleaseError(
            f"provider_asset_http_{exc.code}:{tag}:{asset_name}:{body}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderReleaseError(
            f"provider_asset_network_error:{tag}:{asset_name}:{exc}"
        ) from exc

    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ProviderReleaseError(
            f"provider_asset_empty:{tag}:{asset_name}"
        )
    data = bytes(data)

    expected_size = asset.get("size")
    if not isinstance(expected_size, int) or expected_size < 0:
        raise ProviderReleaseError(
            f"provider_asset_size_missing:{tag}:{asset_name}"
        )
    if len(data) != expected_size:
        raise ProviderReleaseError(
            f"provider_asset_size_mismatch:{tag}:{asset_name}:expected={expected_size}:actual={len(data)}"
        )

    digest = asset.get("digest")
    if digest is not None:
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise ProviderReleaseError(
                f"provider_asset_digest_unsupported:{tag}:{asset_name}"
            )
        expected_digest = digest.removeprefix("sha256:")
        actual_digest = hashlib.sha256(data).hexdigest()
        if expected_digest != actual_digest:
            raise ProviderReleaseError(
                f"provider_asset_digest_mismatch:{tag}:{asset_name}"
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_bytes(data)
    temp.replace(output)
    return {
        "status": "verified_asset_downloaded",
        "tag": tag,
        "name": asset_name,
        "size": len(data),
        "digest": digest,
        "url": url,
    }


def normalize_for_release_surface(payload: dict[str, Any], expected_tag: str) -> dict[str, Any]:
    payload = validate_provider_release(payload, expected_tag)
    return {
        "tagName": payload.get("tag_name"),
        "name": payload.get("name"),
        "url": payload.get("html_url"),
        "isDraft": bool(payload.get("draft")),
        "isPrerelease": bool(payload.get("prerelease")),
        "targetCommitish": payload.get("target_commitish"),
        "assets": [
            {
                "name": asset.get("name"),
                "size": asset.get("size"),
                "url": asset.get("browser_download_url") or asset.get("url"),
            }
            for asset in (payload.get("assets") or [])
            if isinstance(asset, dict)
        ],
        "body": payload.get("body") or "",
        "publishedAt": payload.get("published_at"),
        "createdAt": payload.get("created_at"),
    }


def run_verified_surface(args: argparse.Namespace) -> None:
    from scripts.pentarelease import release_surface

    payload = load_verified_release(Path(args.release_json), args.tag)
    normalized = normalize_for_release_surface(payload, args.tag)
    original_argv = sys.argv[:]
    original_release_view = release_surface.release_view
    forwarded = [
        original_argv[0],
        "--repository", args.repository,
        "--tag", args.tag,
        "--policy", args.policy,
        "--source-dir", args.source_dir,
        "--outdir", args.outdir,
        "--repo-root", args.repo_root,
    ]
    if args.no_sync_repository:
        forwarded.append("--no-sync-repository")
    try:
        release_surface.release_view = lambda repository, tag: (
            normalized
            if repository == args.repository and tag == args.tag
            else (_ for _ in ()).throw(
                ProviderReleaseError(f"verified_release_scope_mismatch:{repository}:{tag}")
            )
        )
        sys.argv = forwarded
        release_surface.main()
    finally:
        release_surface.release_view = original_release_view
        sys.argv = original_argv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    read = sub.add_parser("read")
    read.add_argument("--repository", required=True)
    read.add_argument("--tag")
    read.add_argument("--output", required=True)

    asset = sub.add_parser("asset")
    asset.add_argument("--release-json", required=True)
    asset.add_argument("--repository", required=True)
    asset.add_argument("--tag", required=True)
    asset.add_argument("--name", required=True)
    asset.add_argument("--output", required=True)

    surface = sub.add_parser("surface")
    surface.add_argument("--release-json", required=True)
    surface.add_argument("--repository", required=True)
    surface.add_argument("--tag", required=True)
    surface.add_argument("--policy", default=".pentarelease/policy.json")
    surface.add_argument("--source-dir", default="/tmp/pentarelease-source")
    surface.add_argument("--outdir", default="dist/pentarelease-surface")
    surface.add_argument("--repo-root", default=".")
    surface.add_argument("--no-sync-repository", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "read":
            tag = resolve_local_tag(args.tag)
            payload = write_verified_release(
                args.repository,
                tag,
                Path(args.output),
                os.environ.get("GH_TOKEN", ""),
            )
            print(json.dumps({
                "status": "verified",
                "tag": payload.get("tag_name"),
                "url": payload.get("html_url"),
                "draft": payload.get("draft"),
                "prerelease": payload.get("prerelease"),
            }, indent=2))
        elif args.command == "asset":
            result = download_verified_release_asset(
                Path(args.release_json),
                args.repository,
                args.tag,
                args.name,
                Path(args.output),
            )
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            run_verified_surface(args)
    except ProviderReleaseError as exc:
        print(f"PentaRelease HOLD: {exc}", file=sys.stderr)
        raise SystemExit(45) from exc


if __name__ == "__main__":
    main()
