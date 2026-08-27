#!/usr/bin/env bash
set -Eeuo pipefail

# CrownThrive PentaFabric / RTC GitHub Actions runner bootstrap.
#
# Security contract:
# - GH_TOKEN is accepted only from the process environment and is never written to disk.
# - The short-lived GitHub runner registration token is held only in memory.
# - This runner is intended for trusted main/workflow_dispatch/schedule jobs only.
# - Do NOT route public fork pull_request code to this runner.

REPOSITORY="${GITHUB_REPOSITORY:-crownthrive1/CrownThrive-OS}"
RUNNER_NAME="${PENTA_RUNNER_NAME:-$(hostname)-pentafabric}"
RUNNER_ROOT="${PENTA_RUNNER_ROOT:-/opt/crownthrive/actions-runner}"
RUNNER_USER="${PENTA_RUNNER_USER:-github-runner}"
RUNNER_LABELS="${PENTA_RUNNER_LABELS:-crownthrive,pentafabric,rtc,trusted,provider,pentamail}"
RUNNER_ARCH="${PENTA_RUNNER_ARCH:-x64}"
MINIMUM_RUNNER_VERSION="2.327.1"
GITHUB_API_URL="${GITHUB_API_URL:-https://api.github.com}"
GITHUB_SERVER_URL="${GITHUB_SERVER_URL:-https://github.com}"

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "ERROR: GH_TOKEN must be supplied in the environment with repository administration permission." >&2
  exit 64
fi

for command in curl jq tar sha256sum sort head; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "ERROR: required command '$command' is not installed." >&2
    exit 69
  fi
done

case "$RUNNER_ARCH" in
  x64|arm64) ;;
  *)
    echo "ERROR: PENTA_RUNNER_ARCH must be x64 or arm64 for this Linux bootstrap." >&2
    exit 64
    ;;
esac

case "$RUNNER_ROOT" in
  /opt/crownthrive/*|/srv/crownthrive/*|/var/lib/crownthrive/*) ;;
  *)
    echo "ERROR: PENTA_RUNNER_ROOT must be a dedicated child of /opt/crownthrive, /srv/crownthrive, or /var/lib/crownthrive." >&2
    exit 64
    ;;
esac

if [[ "$RUNNER_ROOT" == */../* || "$RUNNER_ROOT" == */.. || "$RUNNER_ROOT" == *//* ]]; then
  echo "ERROR: PENTA_RUNNER_ROOT must be a normalized absolute path." >&2
  exit 64
fi

api() {
  # Read the bearer header from stdin so the token is not copied into curl's
  # process arguments. The token remains environment/in-memory only.
  printf 'header = "Authorization: Bearer %s"\n' "$GH_TOKEN" | curl --fail --silent --show-error \
    --retry 3 \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    --config - \
    "$@"
}

release_json="$(api "${GITHUB_API_URL}/repos/actions/runner/releases/latest")"
runner_tag="$(jq -r '.tag_name' <<<"$release_json")"
runner_version="${runner_tag#v}"
asset_name="actions-runner-linux-${RUNNER_ARCH}-${runner_version}.tar.gz"
asset_json="$(jq -c --arg name "$asset_name" '.assets[] | select(.name == $name)' <<<"$release_json" | head -n1)"
asset_url="$(jq -r '.browser_download_url // empty' <<<"$asset_json")"
asset_digest="$(jq -r '.digest // empty' <<<"$asset_json")"

if [[ -z "$runner_tag" || "$runner_tag" == "null" || -z "$asset_url" ]]; then
  echo "ERROR: could not resolve the official actions/runner Linux ${RUNNER_ARCH} release asset." >&2
  exit 70
fi

if [[ "$(printf '%s\n%s\n' "$MINIMUM_RUNNER_VERSION" "$runner_version" | sort -V | head -n1)" != "$MINIMUM_RUNNER_VERSION" ]]; then
  echo "ERROR: official runner release $runner_version is below governed minimum $MINIMUM_RUNNER_VERSION." >&2
  exit 70
fi

if [[ ! "$asset_digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "ERROR: official GitHub release metadata lacks a governed SHA-256 digest for $asset_name." >&2
  exit 70
fi
expected_archive_sha256="${asset_digest#sha256:}"

install_root() {
  mkdir -p "$RUNNER_ROOT"
  if [[ "$(id -u)" -eq 0 ]]; then
    if ! id "$RUNNER_USER" >/dev/null 2>&1; then
      useradd --system --create-home --shell /bin/bash "$RUNNER_USER"
    fi
    chown -R "$RUNNER_USER":"$RUNNER_USER" "$RUNNER_ROOT"
  fi
}

install_root

tmp_dir="$(mktemp -d)"
cleanup() {
  unset registration_token GH_TOKEN
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

archive="${tmp_dir}/${asset_name}"
curl --fail --location --silent --show-error --retry 3 "$asset_url" -o "$archive"
archive_sha256="$(sha256sum "$archive" | awk '{print $1}')"
if [[ "$archive_sha256" != "$expected_archive_sha256" ]]; then
  echo "ERROR: runner archive SHA-256 does not match official GitHub release metadata." >&2
  exit 70
fi

# Request the short-lived registration credential only after the downloaded
# runner payload has passed official digest and minimum-version verification.
registration_json="$(api -X POST "${GITHUB_API_URL}/repos/${REPOSITORY}/actions/runners/registration-token")"
registration_token="$(jq -r '.token' <<<"$registration_json")"
registration_expiry="$(jq -r '.expires_at' <<<"$registration_json")"

if [[ -z "$registration_token" || "$registration_token" == "null" ]]; then
  echo "ERROR: GitHub did not issue a runner registration token." >&2
  exit 77
fi

if [[ "$(id -u)" -eq 0 ]]; then
  run_as_runner=(runuser -u "$RUNNER_USER" --)
else
  run_as_runner=()
fi

# Reprovision deterministically. Stop/uninstall an existing local service first,
# then remove local runner identity and payload. --replace below reconciles any
# same-name server-side registration without retaining stale local credentials.
if [[ -x "$RUNNER_ROOT/svc.sh" && -f "$RUNNER_ROOT/.service" ]]; then
  if [[ "$(id -u)" -eq 0 ]]; then
    (cd "$RUNNER_ROOT" && ./svc.sh stop || true)
    (cd "$RUNNER_ROOT" && ./svc.sh uninstall || true)
  elif command -v sudo >/dev/null 2>&1; then
    (cd "$RUNNER_ROOT" && sudo ./svc.sh stop || true)
    (cd "$RUNNER_ROOT" && sudo ./svc.sh uninstall || true)
  fi
fi
find "$RUNNER_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

tar -xzf "$archive" -C "$RUNNER_ROOT"
chown -R "${RUNNER_USER}:${RUNNER_USER}" "$RUNNER_ROOT" 2>/dev/null || true

repo_url="${GITHUB_SERVER_URL}/${REPOSITORY}"
"${run_as_runner[@]}" "$RUNNER_ROOT/config.sh" \
  --unattended \
  --replace \
  --url "$repo_url" \
  --token "$registration_token" \
  --name "$RUNNER_NAME" \
  --labels "$RUNNER_LABELS" \
  --work _work

# The registration token is no longer needed after config.sh completes.
unset registration_token

if [[ "$(uname -s)" == "Linux" ]]; then
  if [[ "$(id -u)" -eq 0 ]]; then
    (cd "$RUNNER_ROOT" && ./svc.sh install "$RUNNER_USER" && ./svc.sh start)
  elif command -v sudo >/dev/null 2>&1; then
    (cd "$RUNNER_ROOT" && sudo ./svc.sh install "$USER" && sudo ./svc.sh start)
  else
    echo "ERROR: runner registered, but service installation requires root or sudo." >&2
    exit 77
  fi
else
  echo "ERROR: this bootstrap currently institutionalizes Linux runner nodes only." >&2
  exit 69
fi

mkdir -p "$RUNNER_ROOT/_penta_evidence"
cat > "$RUNNER_ROOT/_penta_evidence/bootstrap.json" <<JSON
{
  "repository": "${REPOSITORY}",
  "runner_name": "${RUNNER_NAME}",
  "runner_release": "${runner_tag}",
  "minimum_runner_version": "${MINIMUM_RUNNER_VERSION}",
  "runner_arch": "${RUNNER_ARCH}",
  "runner_labels": "${RUNNER_LABELS}",
  "download_sha256": "${archive_sha256}",
  "official_release_sha256": "${expected_archive_sha256}",
  "digest_verified": true,
  "registration_token_expires_at": "${registration_expiry}",
  "security_scope": "trusted-main-dispatch-schedule-only"
}
JSON
chown -R "${RUNNER_USER}:${RUNNER_USER}" "$RUNNER_ROOT/_penta_evidence" 2>/dev/null || true

echo "PentaFabric runner bootstrap complete."
echo "Repository: ${REPOSITORY}"
echo "Runner: ${RUNNER_NAME}"
echo "Release: ${runner_tag}"
echo "Labels: ${RUNNER_LABELS}"
echo "Downloaded runner SHA-256: ${archive_sha256}"
echo "Next proof: dispatch 'Penta Runner Fabric Certification' and require an attested PASS."
