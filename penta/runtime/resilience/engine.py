from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence


class ResilienceError(RuntimeError):
    """Base error for the Penta resilience suite."""


class PolicyViolation(ResilienceError):
    """Raised when a requested action violates range or recovery policy."""


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RangeState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    CONTAINED = "contained"
    VERIFIED = "verified"
    DESTROYED = "destroyed"


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CHANGE_ID_RE = re.compile(r"^CHG-[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
SNAPSHOT_ID_RE = re.compile(r"^snap-[0-9a-f]{14}$")
CONTROL_ID_RE = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")


def _record_digest(value: object, digest_field: str) -> str:
    payload = asdict(value)  # type: ignore[arg-type]
    payload[digest_field] = ""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _validate_change_id(value: str) -> str:
    if not isinstance(value, str) or CHANGE_ID_RE.fullmatch(value) is None:
        raise PolicyViolation("approved_change_id must match CHG-<bounded-identifier>")
    return value


def _safe_relative_path(value: str, *, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise PolicyViolation(f"{field} must be a portable relative path")
    path = Path(value)
    if path.is_absolute() or path == Path(".") or any(part in {"", ".", ".."} for part in path.parts):
        raise PolicyViolation(f"{field} must stay inside its governed root")
    return path


def _canonical_root(value: Path, *, field: str) -> Path:
    lexical = Path(os.path.abspath(os.fspath(value)))
    if lexical.is_symlink():
        raise PolicyViolation(f"{field} may not be a symlink")
    resolved = lexical.resolve(strict=True)
    if lexical != resolved:
        raise PolicyViolation(f"{field} may not traverse a symlink")
    if not resolved.is_dir():
        raise PolicyViolation(f"{field} must be a directory")
    return resolved


def _ensure_safe_directory(root: Path, *parts: str) -> Path:
    current = root
    for part in parts:
        if not part or part in {".", ".."} or "/" in part or "\\" in part:
            raise PolicyViolation("unsafe governed directory component")
        current = current / part
        if current.exists() and (current.is_symlink() or not current.is_dir()):
            raise PolicyViolation(f"governed directory is not a safe directory: {current}")
        current.mkdir(exist_ok=True)
        resolved = current.resolve(strict=True)
        if not _inside(resolved, root):
            raise PolicyViolation("governed directory escaped the target root")
        current = resolved
    return current


def _approval_binding(
    approved_change_id: str,
    *,
    operation: str,
    target_root: Path,
    provenance_sha256: str,
) -> str:
    _validate_change_id(approved_change_id)
    if not _valid_sha256(provenance_sha256):
        raise PolicyViolation("approved change provenance must be a SHA-256 digest")
    payload = {
        "schema": "ct.penta.resilience.approved-change-binding.v1",
        "approved_change_id": approved_change_id,
        "operation": operation,
        "target_root": str(target_root),
        "provenance_sha256": provenance_sha256,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class FileEvidence:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class SnapshotManifest:
    snapshot_id: str
    source_root: str
    created_at: float
    tree_sha256: str
    files: tuple[FileEvidence, ...]
    storage_root: str
    manifest_sha256: str = ""

    def with_digest(self) -> "SnapshotManifest":
        return replace(self, manifest_sha256=_record_digest(self, "manifest_sha256"))


@dataclass(frozen=True)
class RangeLease:
    range_id: str
    clone_root: str
    nonce: str
    issued_at: float
    expires_at: float
    source_tree_sha256: str


@dataclass(frozen=True)
class AttackEvent:
    event_id: str
    scenario: str
    path: str
    action: str
    timestamp: float
    severity: Severity
    simulation_only: bool = True


@dataclass(frozen=True)
class Detection:
    detection_id: str
    event_id: str
    scenario: str
    path: str
    contained: bool
    restored: bool
    timestamp: float
    severity: Severity


@dataclass(frozen=True)
class Finding:
    finding_id: str
    category: str
    severity: Severity
    scenario: str
    evidence_path: str
    blue_contained: bool
    recommendation: str


@dataclass(frozen=True)
class HardeningAction:
    action_id: str
    control: str
    rationale: str
    priority: int
    policy_key: str
    policy_value: object


@dataclass(frozen=True)
class HardeningPlan:
    plan_id: str
    report_id: str
    report_digest: str
    source_root: str
    source_tree_sha256: str
    created_at: float
    actions: tuple[HardeningAction, ...]
    dry_run: bool = True
    digest: str = ""

    def with_digest(self) -> "HardeningPlan":
        return replace(self, digest=_record_digest(self, "digest"))


@dataclass(frozen=True)
class RollbackResult:
    rollback_id: str
    snapshot_id: str
    approved_change_id: str
    restored: bool
    health_ok: bool
    timestamp: float
    target_root: str
    provenance_sha256: str
    approval_binding_sha256: str


@dataclass(frozen=True)
class DrillReport:
    report_id: str
    range_id: str
    source_root: str
    source_tree_before: str
    source_tree_after: str
    clone_tree_baseline: str
    clone_tree_final: str
    source_unchanged: bool
    clone_restored: bool
    events: tuple[AttackEvent, ...]
    detections: tuple[Detection, ...]
    findings: tuple[Finding, ...]
    started_at: float
    completed_at: float
    digest: str = ""

    def with_digest(self) -> "DrillReport":
        return replace(self, digest=_record_digest(self, "digest"))


IGNORE_NAMES = {".git", "__pycache__", ".pytest_cache"}


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _reject_symlink_chain(path: Path, stop: Path) -> None:
    stop = stop.resolve(strict=False)
    current = path
    while _inside(current, stop):
        if current.is_symlink():
            raise PolicyViolation(f"symlink path rejected: {current}")
        if current.resolve(strict=False) == stop:
            break
        current = current.parent


def tree_evidence(root: Path, *, ignore: Iterable[str] = IGNORE_NAMES) -> tuple[tuple[FileEvidence, ...], str]:
    root = root.resolve(strict=True)
    ignored = set(ignore)
    evidence: list[FileEvidence] = []
    if root.is_symlink():
        raise PolicyViolation("tree root may not be a symlink")
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in ignored for part in rel.parts):
            continue
        if path.is_symlink():
            raise PolicyViolation(f"symlink in protected tree rejected: {rel}")
        if not path.is_file():
            continue
        data = path.read_bytes()
        evidence.append(FileEvidence(str(rel), hashlib.sha256(data).hexdigest(), len(data)))
    joined = "\n".join(f"{e.path}\0{e.sha256}\0{e.size}" for e in evidence).encode()
    return tuple(evidence), hashlib.sha256(joined).hexdigest()


class RangePolicy:
    """Fail-closed policy proving Red operates only inside a leased ephemeral clone."""

    def __init__(self, max_lease_seconds: int = 900):
        self.max_lease_seconds = max_lease_seconds
        self._leases: dict[str, RangeLease] = {}

    def issue(self, clone_root: Path, source_tree_sha256: str, ttl_seconds: int = 300) -> RangeLease:
        clone_root = clone_root.resolve(strict=True)
        if ttl_seconds <= 0 or ttl_seconds > self.max_lease_seconds:
            raise PolicyViolation("invalid range TTL")
        marker = clone_root / ".penta-honeypot-range"
        if not marker.is_file():
            raise PolicyViolation("range marker missing")
        nonce = marker.read_text(encoding="utf-8").strip()
        if not nonce:
            raise PolicyViolation("range marker is empty")
        now = time.time()
        lease = RangeLease(
            range_id=f"range-{uuid.uuid4().hex[:12]}",
            clone_root=str(clone_root),
            nonce=nonce,
            issued_at=now,
            expires_at=now + ttl_seconds,
            source_tree_sha256=source_tree_sha256,
        )
        self._leases[lease.range_id] = lease
        return lease

    def assert_target(self, lease: RangeLease, target: Path) -> Path:
        current = self._leases.get(lease.range_id)
        if current != lease:
            raise PolicyViolation("unknown or superseded range lease")
        if time.time() >= lease.expires_at:
            raise PolicyViolation("range lease expired")
        root = Path(lease.clone_root).resolve(strict=True)
        marker = root / ".penta-honeypot-range"
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != lease.nonce:
            raise PolicyViolation("range proof failed")
        target = target.resolve(strict=False)
        if target == root or not _inside(target, root):
            raise PolicyViolation("PentaRed target must be a child of the leased clone")
        _reject_symlink_chain(target.parent, root)
        return target

    def revoke(self, lease: RangeLease) -> None:
        self._leases.pop(lease.range_id, None)


class PentaSnapshot:
    """Evidence-backed filesystem snapshots with SHA-256 manifests."""

    def __init__(self, store_root: Path | None = None):
        self.store_root = Path(store_root or tempfile.mkdtemp(prefix="pentasnapshot-")).resolve()
        self.store_root.mkdir(parents=True, exist_ok=True)
        self._issued_manifests: dict[str, str] = {}

    def create(self, source_root: Path) -> SnapshotManifest:
        source_root = _canonical_root(source_root, field="snapshot source")
        files, tree_hash = tree_evidence(source_root)
        snapshot_id = f"snap-{uuid.uuid4().hex[:14]}"
        dest = self.store_root / snapshot_id / "tree"
        dest.parent.mkdir(parents=True, exist_ok=False)
        try:
            shutil.copytree(source_root, dest, symlinks=False, ignore=shutil.ignore_patterns(*IGNORE_NAMES))
            copied_files, copied_hash = tree_evidence(dest)
            source_files_after, source_hash_after = tree_evidence(source_root)
            if (
                copied_hash != tree_hash
                or copied_files != files
                or source_hash_after != tree_hash
                or source_files_after != files
            ):
                raise PolicyViolation("snapshot source changed while the snapshot was captured")
        except Exception:
            shutil.rmtree(dest.parent, ignore_errors=True)
            raise
        manifest = SnapshotManifest(
            snapshot_id,
            str(source_root),
            time.time(),
            tree_hash,
            files,
            str(dest.resolve(strict=True)),
        ).with_digest()
        (dest.parent / "manifest.json").write_text(
            json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self._issued_manifests[manifest.snapshot_id] = manifest.manifest_sha256
        return manifest

    def verify(self, manifest: SnapshotManifest) -> bool:
        if not isinstance(manifest, SnapshotManifest):
            return False
        if not isinstance(manifest.snapshot_id, str) or SNAPSHOT_ID_RE.fullmatch(manifest.snapshot_id) is None:
            return False
        if not _valid_sha256(manifest.tree_sha256) or not _valid_sha256(manifest.manifest_sha256):
            return False
        expected_manifest_digest = _record_digest(manifest, "manifest_sha256")
        if not hmac.compare_digest(manifest.manifest_sha256, expected_manifest_digest):
            return False
        issued_digest = self._issued_manifests.get(manifest.snapshot_id)
        if issued_digest is None or not hmac.compare_digest(issued_digest, manifest.manifest_sha256):
            return False
        expected_root = (self.store_root / manifest.snapshot_id / "tree").resolve(strict=False)
        if manifest.storage_root != str(expected_root):
            return False
        try:
            root = _canonical_root(Path(manifest.storage_root), field="snapshot storage")
            persisted = json.loads((root.parent / "manifest.json").read_text(encoding="utf-8"))
            expected_persisted = json.loads(json.dumps(asdict(manifest), default=str))
            files, digest = tree_evidence(root)
        except (OSError, json.JSONDecodeError, PolicyViolation):
            return False
        return persisted == expected_persisted and files == manifest.files and digest == manifest.tree_sha256


class PentaRollback:
    """Approved rollback primitive. It never manufactures recovery authority."""

    def __init__(self, snapshotter: PentaSnapshot):
        self.snapshotter = snapshotter

    def restore(
        self,
        manifest: SnapshotManifest,
        target_root: Path,
        *,
        approved_change_id: str,
        provenance_sha256: str | None = None,
        health_check: Callable[[Path], bool] | None = None,
    ) -> RollbackResult:
        _validate_change_id(approved_change_id)
        if not self.snapshotter.verify(manifest):
            raise PolicyViolation("snapshot verification failed")
        target = _canonical_root(target_root, field="rollback target")
        source = _canonical_root(Path(manifest.storage_root), field="snapshot storage")
        if manifest.source_root != str(target):
            raise PolicyViolation("snapshot is not bound to the exact rollback target")
        provenance = provenance_sha256 or manifest.manifest_sha256
        approval_binding = _approval_binding(
            approved_change_id,
            operation="rollback_restore",
            target_root=target,
            provenance_sha256=provenance,
        )

        stage_parent = target.parent
        stage = Path(tempfile.mkdtemp(prefix="pentarollback-stage-", dir=stage_parent)) / "tree"
        shutil.copytree(source, stage, symlinks=False)
        _, staged_hash = tree_evidence(stage)
        if staged_hash != manifest.tree_sha256:
            shutil.rmtree(stage.parent, ignore_errors=True)
            raise PolicyViolation("staged rollback hash mismatch")

        backup = target.with_name(f"{target.name}.pentarollback-{uuid.uuid4().hex[:8]}")
        os.replace(target, backup)
        try:
            os.replace(stage, target)
            health_ok = True if health_check is None else bool(health_check(target))
            if not health_ok:
                failed = target.with_name(f"{target.name}.failed-{uuid.uuid4().hex[:8]}")
                os.replace(target, failed)
                os.replace(backup, target)
                shutil.rmtree(failed, ignore_errors=True)
                restored = False
            else:
                shutil.rmtree(backup, ignore_errors=True)
                restored = True
        except Exception:
            if not target.exists() and backup.exists():
                os.replace(backup, target)
            raise
        finally:
            shutil.rmtree(stage.parent, ignore_errors=True)

        return RollbackResult(
            rollback_id=f"rollback-{uuid.uuid4().hex[:12]}",
            snapshot_id=manifest.snapshot_id,
            approved_change_id=approved_change_id,
            restored=restored,
            health_ok=health_ok,
            timestamp=time.time(),
            target_root=str(target),
            provenance_sha256=provenance,
            approval_binding_sha256=approval_binding,
        )


class PentaRed:
    """Sandbox-only adversary simulator. No host/network target interface exists."""

    SCENARIOS: Mapping[str, tuple[str, str, Severity]] = {
        "config_tamper": ("lab/config.json", "config-tampered", Severity.HIGH),
        "privilege_marker": ("lab/access.policy", "admin=true", Severity.CRITICAL),
        "secret_canary": ("lab/secrets.canary", "CANARY_EXPOSED", Severity.HIGH),
        "service_degrade": ("lab/service.state", "degraded", Severity.MEDIUM),
        "integrity_tamper": ("lab/integrity.txt", "integrity-broken", Severity.HIGH),
    }

    def __init__(self, policy: RangePolicy):
        self.policy = policy

    def execute(self, lease: RangeLease, scenario: str) -> AttackEvent:
        if scenario not in self.SCENARIOS:
            raise PolicyViolation(f"unapproved simulation scenario: {scenario}")
        rel, value, severity = self.SCENARIOS[scenario]
        target = self.policy.assert_target(lease, Path(lease.clone_root) / rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value + "\n", encoding="utf-8")
        return AttackEvent(
            event_id=f"red-{uuid.uuid4().hex[:12]}",
            scenario=scenario,
            path=rel,
            action="simulated-local-tamper",
            timestamp=time.time(),
            severity=severity,
        )


class PentaBlue:
    """Detection, containment, and restore engine for PentaHoneyPot ranges."""

    def __init__(self, snapshotter: PentaSnapshot):
        self.snapshotter = snapshotter

    def inspect_and_contain(
        self,
        clone_root: Path,
        baseline: SnapshotManifest,
        events: Sequence[AttackEvent],
    ) -> tuple[tuple[Detection, ...], tuple[Finding, ...]]:
        clone_root = _canonical_root(clone_root, field="containment target")
        if baseline.source_root != str(clone_root) or not self.snapshotter.verify(baseline):
            raise PolicyViolation("baseline is not verified for the exact containment target")
        baseline_root = _canonical_root(Path(baseline.storage_root), field="containment baseline")
        detections: list[Detection] = []
        findings: list[Finding] = []
        baseline_map = {f.path: f for f in baseline.files}

        for event in events:
            scenario = PentaRed.SCENARIOS.get(event.scenario)
            if scenario is None or event.simulation_only is not True or event.path != scenario[0]:
                raise PolicyViolation("blue containment accepts only allowlisted simulation events")
            relative = _safe_relative_path(event.path, field="attack event path")
            target_path = clone_root / relative
            target = target_path.resolve(strict=False)
            if target == clone_root or not _inside(target, clone_root):
                raise PolicyViolation("blue containment target escaped range")
            _reject_symlink_chain(target_path.parent, clone_root)
            expected = baseline_map.get(event.path)
            changed = target.exists()
            if expected and target.exists():
                if target_path.is_symlink():
                    raise PolicyViolation("blue containment target may not be a symlink")
                changed = hashlib.sha256(target.read_bytes()).hexdigest() != expected.sha256
            restored = False
            if changed:
                baseline_file_path = baseline_root / relative
                baseline_file = baseline_file_path.resolve(strict=False)
                if not _inside(baseline_file, baseline_root):
                    raise PolicyViolation("blue containment baseline escaped snapshot root")
                _reject_symlink_chain(baseline_file_path.parent, baseline_root)
                if baseline_file_path.is_symlink():
                    raise PolicyViolation("blue containment baseline may not be a symlink")
                if baseline_file.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    _reject_symlink_chain(target_path.parent, clone_root)
                    if target_path.is_symlink():
                        raise PolicyViolation("blue containment target may not be a symlink")
                    shutil.copy2(baseline_file, target)
                elif target.exists():
                    if target_path.is_symlink() or target.is_dir():
                        raise PolicyViolation("blue containment may remove only a regular in-range file")
                    target.unlink()
                restored = True
            detections.append(
                Detection(
                    detection_id=f"blue-{uuid.uuid4().hex[:12]}",
                    event_id=event.event_id,
                    scenario=event.scenario,
                    path=event.path,
                    contained=changed,
                    restored=restored,
                    timestamp=time.time(),
                    severity=event.severity,
                )
            )
            findings.append(
                Finding(
                    finding_id=f"finding-{uuid.uuid4().hex[:12]}",
                    category=event.scenario,
                    severity=event.severity,
                    scenario=event.scenario,
                    evidence_path=event.path,
                    blue_contained=changed and restored,
                    recommendation=self._recommend(event.scenario),
                )
            )
        return tuple(detections), tuple(findings)

    @staticmethod
    def _recommend(scenario: str) -> str:
        return {
            "config_tamper": "enforce configuration integrity and signed-change policy",
            "privilege_marker": "enforce least privilege and deny privilege drift",
            "secret_canary": "enforce secret reference isolation and canary alerting",
            "service_degrade": "enforce health gates, circuit breaking, and recovery SLOs",
            "integrity_tamper": "enforce immutable manifests and continuous integrity verification",
        }[scenario]


class PentaHoneyPot:
    """Creates an ephemeral clone, runs Red/Blue drills, proves source immutability, then destroys the clone."""

    def __init__(self, policy: RangePolicy | None = None, snapshotter: PentaSnapshot | None = None):
        self.policy = policy or RangePolicy()
        self.snapshotter = snapshotter or PentaSnapshot()
        self.red = PentaRed(self.policy)
        self.blue = PentaBlue(self.snapshotter)
        self._issued_reports: dict[str, str] = {}

    def verify_report(self, report: DrillReport) -> bool:
        if not isinstance(report, DrillReport) or not _valid_sha256(report.digest):
            return False
        issued = self._issued_reports.get(report.report_id)
        return (
            issued is not None
            and hmac.compare_digest(issued, report.digest)
            and hmac.compare_digest(report.digest, _record_digest(report, "digest"))
        )

    def run(self, source_root: Path, scenarios: Sequence[str] | None = None) -> DrillReport:
        source_root = source_root.resolve(strict=True)
        _, source_before = tree_evidence(source_root)
        started = time.time()
        scenarios = tuple(scenarios or PentaRed.SCENARIOS.keys())
        if len(scenarios) != len(set(scenarios)):
            raise PolicyViolation("honeypot scenarios must be unique")
        if any(scenario not in PentaRed.SCENARIOS for scenario in scenarios):
            raise PolicyViolation("honeypot scenarios must come from the allowlisted catalog")

        with tempfile.TemporaryDirectory(prefix="pentahoneypot-") as td:
            clone_root = Path(td) / "os-clone"
            shutil.copytree(source_root, clone_root, symlinks=False, ignore=shutil.ignore_patterns(*IGNORE_NAMES))
            nonce = uuid.uuid4().hex
            (clone_root / ".penta-honeypot-range").write_text(nonce, encoding="utf-8")
            lab = clone_root / "lab"
            lab.mkdir(parents=True, exist_ok=True)
            baseline_values = {
                "config.json": '{"mode":"normal"}\n',
                "access.policy": "admin=false\n",
                "secrets.canary": "CANARY_SAFE\n",
                "service.state": "healthy\n",
                "integrity.txt": "integrity-ok\n",
            }
            for name, value in baseline_values.items():
                (lab / name).write_text(value, encoding="utf-8")

            baseline = self.snapshotter.create(clone_root)
            lease = self.policy.issue(clone_root, source_before)
            events: list[AttackEvent] = []
            try:
                for scenario in scenarios:
                    events.append(self.red.execute(lease, scenario))
                detections, findings = self.blue.inspect_and_contain(clone_root, baseline, events)
                _, clone_final = tree_evidence(clone_root)
                clone_restored = clone_final == baseline.tree_sha256
            finally:
                self.policy.revoke(lease)

        _, source_after = tree_evidence(source_root)
        report = DrillReport(
            report_id=f"drill-{uuid.uuid4().hex[:14]}",
            range_id=lease.range_id,
            source_root=str(source_root),
            source_tree_before=source_before,
            source_tree_after=source_after,
            clone_tree_baseline=baseline.tree_sha256,
            clone_tree_final=clone_final,
            source_unchanged=source_before == source_after,
            clone_restored=clone_restored,
            events=tuple(events),
            detections=detections,
            findings=findings,
            started_at=started,
            completed_at=time.time(),
        ).with_digest()
        if not report.source_unchanged:
            raise PolicyViolation("source tree changed during honeypot drill")
        if not report.clone_restored or not all(d.contained and d.restored for d in report.detections):
            raise PolicyViolation("honeypot clone did not return to its verified baseline")
        self._issued_reports[report.report_id] = report.digest
        return report


class PentaLiency:
    """Turns evidence into governed hardening policies and rollback-backed application."""

    CONTROL_MAP: Mapping[str, tuple[str, str, object]] = {
        "config_tamper": ("CT-RES-CONFIG-INTEGRITY", "require_signed_config_changes", True),
        "privilege_marker": ("CT-RES-PRIVILEGE-DRIFT", "deny_unapproved_privilege_drift", True),
        "secret_canary": ("CT-RES-SECRET-ISOLATION", "secret_canary_alerting", True),
        "service_degrade": ("CT-RES-HEALTH-GATE", "require_pre_post_health_gate", True),
        "integrity_tamper": ("CT-RES-MANIFEST", "continuous_manifest_verification", True),
    }

    def __init__(
        self,
        snapshotter: PentaSnapshot | None = None,
        report_verifier: Callable[[DrillReport], bool] | None = None,
    ):
        self.snapshotter = snapshotter or PentaSnapshot()
        self.rollback = PentaRollback(self.snapshotter)
        self.report_verifier = report_verifier
        self._verified_reports: dict[str, str] = {}
        self._issued_plans: dict[str, str] = {}

    def _verify_report(self, report: DrillReport) -> None:
        if not isinstance(report, DrillReport):
            raise PolicyViolation("PentaLiency requires a DrillReport")
        if not _valid_sha256(report.digest) or not hmac.compare_digest(
            report.digest, _record_digest(report, "digest")
        ):
            raise PolicyViolation("drill report digest verification failed")
        if self.report_verifier is None or self.report_verifier(report) is not True:
            raise PolicyViolation("drill report was not issued by the configured PentaHoneyPot verifier")
        if (
            not report.source_unchanged
            or report.source_tree_before != report.source_tree_after
            or not report.clone_restored
            or report.clone_tree_baseline != report.clone_tree_final
        ):
            raise PolicyViolation("drill report does not prove source safety and clone restoration")
        for value in (
            report.source_tree_before,
            report.source_tree_after,
            report.clone_tree_baseline,
            report.clone_tree_final,
        ):
            if not _valid_sha256(value):
                raise PolicyViolation("drill report contains an invalid evidence digest")
        if (
            not isinstance(report.started_at, (int, float))
            or isinstance(report.started_at, bool)
            or not isinstance(report.completed_at, (int, float))
            or isinstance(report.completed_at, bool)
            or report.completed_at < report.started_at
            or report.started_at <= 0
        ):
            raise PolicyViolation("drill report time bounds are invalid")
        try:
            source_root = _canonical_root(Path(report.source_root), field="drill source")
            current_source_digest = tree_evidence(source_root)[1]
        except (OSError, TypeError, PolicyViolation) as exc:
            raise PolicyViolation("drill source is unavailable for provenance verification") from exc
        if report.source_root != str(source_root) or current_source_digest != report.source_tree_after:
            raise PolicyViolation("drill report is stale or bound to a different source tree")
        if not report.events or len(report.events) != len(report.detections) or len(report.events) != len(report.findings):
            raise PolicyViolation("drill evidence must contain one detection and finding per event")
        if any(
            not isinstance(event.event_id, str)
            or not isinstance(event.scenario, str)
            or not isinstance(event.path, str)
            or not isinstance(event.action, str)
            for event in report.events
        ):
            raise PolicyViolation("drill events contain invalid identifiers")
        if any(
            not isinstance(detection.detection_id, str)
            or not isinstance(detection.event_id, str)
            or not isinstance(detection.scenario, str)
            or not isinstance(detection.path, str)
            for detection in report.detections
        ):
            raise PolicyViolation("drill detections contain invalid identifiers")
        if any(
            not isinstance(finding.finding_id, str)
            or not isinstance(finding.scenario, str)
            or not isinstance(finding.category, str)
            or not isinstance(finding.evidence_path, str)
            or not isinstance(finding.recommendation, str)
            for finding in report.findings
        ):
            raise PolicyViolation("drill findings contain invalid identifiers")
        if len({event.event_id for event in report.events}) != len(report.events):
            raise PolicyViolation("drill event IDs must be unique")
        if len({detection.detection_id for detection in report.detections}) != len(report.detections):
            raise PolicyViolation("drill detection IDs must be unique")
        if len({finding.finding_id for finding in report.findings}) != len(report.findings):
            raise PolicyViolation("drill finding IDs must be unique")

        detections = {detection.event_id: detection for detection in report.detections}
        findings = {(finding.scenario, finding.evidence_path): finding for finding in report.findings}
        if len(findings) != len(report.findings):
            raise PolicyViolation("drill findings must be unique by scenario and evidence path")
        for event in report.events:
            scenario = PentaRed.SCENARIOS.get(event.scenario)
            if scenario is None or event.simulation_only is not True:
                raise PolicyViolation("drill event is not an allowlisted simulation")
            expected_path, _, expected_severity = scenario
            _safe_relative_path(event.path, field="drill event path")
            if (
                event.path != expected_path
                or event.action != "simulated-local-tamper"
                or event.severity != expected_severity
            ):
                raise PolicyViolation("drill event does not match the allowlisted scenario contract")
            detection = detections.get(event.event_id)
            if detection is None or (
                detection.scenario != event.scenario
                or detection.path != event.path
                or detection.severity != event.severity
                or detection.contained is not True
                or detection.restored is not True
            ):
                raise PolicyViolation("drill detection does not prove containment and restoration")
            finding = findings.get((event.scenario, event.path))
            if finding is None or (
                finding.category != event.scenario
                or finding.severity != event.severity
                or finding.blue_contained is not True
                or not finding.recommendation.strip()
            ):
                raise PolicyViolation("drill finding does not match verified Blue evidence")

    def _validate_plan(self, plan: HardeningPlan) -> None:
        if not isinstance(plan, HardeningPlan):
            raise PolicyViolation("hardening apply requires a HardeningPlan")
        if not _valid_sha256(plan.digest) or not hmac.compare_digest(plan.digest, _record_digest(plan, "digest")):
            raise PolicyViolation("hardening plan digest verification failed")
        if self._issued_plans.get(plan.plan_id) != plan.digest:
            raise PolicyViolation("hardening plan was not issued by this verified PentaLiency session")
        if self._verified_reports.get(plan.report_id) != plan.report_digest:
            raise PolicyViolation("hardening plan report provenance is not verified")
        if not _valid_sha256(plan.report_digest) or not _valid_sha256(plan.source_tree_sha256):
            raise PolicyViolation("hardening plan provenance digest is invalid")
        if not plan.actions or len({action.control for action in plan.actions}) != len(plan.actions):
            raise PolicyViolation("hardening plan controls must be nonempty and unique")
        allowed = {
            control: (policy_key, policy_value)
            for control, policy_key, policy_value in self.CONTROL_MAP.values()
        }
        for action in plan.actions:
            if not isinstance(action.control, str) or CONTROL_ID_RE.fullmatch(action.control) is None:
                raise PolicyViolation("hardening control name is unsafe")
            expected = allowed.get(action.control)
            if (
                expected is None
                or action.policy_key != expected[0]
                or action.policy_value != expected[1]
                or not isinstance(action.priority, int)
                or isinstance(action.priority, bool)
                or action.priority not in range(5)
                or not isinstance(action.rationale, str)
                or not action.rationale.strip()
                or not isinstance(action.action_id, str)
                or re.fullmatch(r"hardening-[0-9a-f]{12}", action.action_id) is None
            ):
                raise PolicyViolation("hardening action does not match the registered control contract")
            relative = _safe_relative_path(f"{action.control.lower()}.json", field="hardening policy path")
            if len(relative.parts) != 1:
                raise PolicyViolation("hardening policies must be direct children of the control directory")

    def plan(self, report: DrillReport) -> HardeningPlan:
        self._verify_report(report)
        prior = self._verified_reports.get(report.report_id)
        if prior is not None and prior != report.digest:
            raise PolicyViolation("drill report ID collision detected")
        self._verified_reports[report.report_id] = report.digest
        actions: list[HardeningAction] = []
        seen: set[str] = set()
        for finding in report.findings:
            if finding.category in seen:
                continue
            seen.add(finding.category)
            control, key, value = self.CONTROL_MAP[finding.category]
            priority = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}[finding.severity]
            actions.append(
                HardeningAction(
                    action_id=f"hardening-{uuid.uuid4().hex[:12]}",
                    control=control,
                    rationale=finding.recommendation,
                    priority=priority,
                    policy_key=key,
                    policy_value=value,
                )
            )
        actions.sort(key=lambda a: (a.priority, a.control))
        plan = HardeningPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:14]}",
            report_id=report.report_id,
            report_digest=report.digest,
            source_root=report.source_root,
            source_tree_sha256=report.source_tree_after,
            created_at=time.time(),
            actions=tuple(actions),
            dry_run=True,
        ).with_digest()
        self._issued_plans[plan.plan_id] = plan.digest
        return plan

    def apply(
        self,
        plan: HardeningPlan,
        target_root: Path,
        *,
        approved_change_id: str,
        health_check: Callable[[Path], bool] | None = None,
    ) -> dict[str, object]:
        _validate_change_id(approved_change_id)
        self._validate_plan(plan)
        target_root = _canonical_root(target_root, field="hardening target")
        if plan.source_root != str(target_root):
            raise PolicyViolation("hardening plan is not bound to the exact target root")
        if tree_evidence(target_root)[1] != plan.source_tree_sha256:
            raise PolicyViolation("hardening target changed after the verified drill")
        approval_binding = _approval_binding(
            approved_change_id,
            operation="hardening_apply",
            target_root=target_root,
            provenance_sha256=plan.digest,
        )
        pre = self.snapshotter.create(target_root)
        rollback_result = None
        try:
            policy_dir = _ensure_safe_directory(target_root, ".penta-hardening", "controls")
            for action in plan.actions:
                relative = _safe_relative_path(f"{action.control.lower()}.json", field="hardening policy path")
                policy_file_path = policy_dir / relative
                if policy_file_path.is_symlink():
                    raise PolicyViolation("hardening policy target may not be a symlink")
                policy_file = policy_file_path.resolve(strict=False)
                if policy_file.parent != policy_dir or not _inside(policy_file, target_root):
                    raise PolicyViolation("hardening policy target escaped its governed directory")
                payload = {
                    "control": action.control,
                    "policy_key": action.policy_key,
                    "policy_value": action.policy_value,
                    "rationale": action.rationale,
                    "source_plan": plan.plan_id,
                    "source_plan_sha256": plan.digest,
                    "approved_change_id": approved_change_id,
                    "approval_binding_sha256": approval_binding,
                    "target_root": str(target_root),
                    "applied_at": time.time(),
                }
                policy_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            health_ok = True if health_check is None else bool(health_check(target_root))
            if not health_ok:
                rollback_result = self.rollback.restore(
                    pre,
                    target_root,
                    approved_change_id=approved_change_id,
                    provenance_sha256=plan.digest,
                    health_check=lambda _: True,
                )
        except Exception:
            if target_root.exists() and self.snapshotter.verify(pre):
                self.rollback.restore(
                    pre,
                    target_root,
                    approved_change_id=approved_change_id,
                    provenance_sha256=plan.digest,
                    health_check=lambda _: True,
                )
            raise
        return {
            "plan_id": plan.plan_id,
            "plan_sha256": plan.digest,
            "approved_change_id": approved_change_id,
            "approval_binding_sha256": approval_binding,
            "target_root": str(target_root),
            "snapshot_id": pre.snapshot_id,
            "health_ok": health_ok,
            "rollback": asdict(rollback_result) if rollback_result else None,
            "applied": health_ok,
        }


@dataclass
class PentaResilienceLoop:
    honeypot: PentaHoneyPot = field(default_factory=PentaHoneyPot)
    liency: PentaLiency = field(default_factory=PentaLiency)

    def __post_init__(self) -> None:
        if self.liency.report_verifier is None:
            self.liency.report_verifier = self.honeypot.verify_report

    def drill_and_plan(self, source_root: Path, scenarios: Sequence[str] | None = None) -> tuple[DrillReport, HardeningPlan]:
        report = self.honeypot.run(source_root, scenarios)
        plan = self.liency.plan(report)
        return report, plan


def penta_status_adapter(report: DrillReport | None = None, plan: HardeningPlan | None = None) -> dict[str, object]:
    """Machine-readable PentaStatus adapter for the resilience family."""
    critical_high = 0
    if report is not None:
        critical_high = sum(1 for f in report.findings if f.severity in {Severity.CRITICAL, Severity.HIGH})
    return {
        "canonical_id": "penta-resilience-suite",
        "canonical_name": "Penta Resilience Suite",
        "version": "1.0.0",
        "lifecycle_state": "institutionalized",
        "overall_state": (
            "verified" if report and report.source_unchanged and report.clone_restored else "ready"
        ),
        "heartbeat_time": time.time(),
        "latest_drill_id": report.report_id if report else None,
        "source_unchanged": report.source_unchanged if report else None,
        "clone_restored": report.clone_restored if report else None,
        "critical_high_findings": critical_high,
        "latest_plan_id": plan.plan_id if plan else None,
        "pending_hardening_actions": len(plan.actions) if plan else 0,
        "security_boundary": "PentaRed sandbox-only; no network/production target primitive",
        "portal": "/io/pentas/liency",
        "docs": "PENTA-RESILIENCE-SUITE.md",
    }


def report_json(report: DrillReport) -> str:
    return json.dumps(asdict(report), indent=2, sort_keys=True, default=str)


def plan_json(plan: HardeningPlan) -> str:
    return json.dumps(asdict(plan), indent=2, sort_keys=True, default=str)
