from __future__ import annotations

import hashlib
import json
import os
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
    created_at: float
    actions: tuple[HardeningAction, ...]
    dry_run: bool = True


@dataclass(frozen=True)
class RollbackResult:
    rollback_id: str
    snapshot_id: str
    approved_change_id: str
    restored: bool
    health_ok: bool
    timestamp: float


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
        payload = asdict(self)
        payload["digest"] = ""
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        digest = hashlib.sha256(raw).hexdigest()
        return replace(self, digest=digest)


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

    def create(self, source_root: Path) -> SnapshotManifest:
        source_root = source_root.resolve(strict=True)
        files, tree_hash = tree_evidence(source_root)
        snapshot_id = f"snap-{uuid.uuid4().hex[:14]}"
        dest = self.store_root / snapshot_id / "tree"
        dest.parent.mkdir(parents=True, exist_ok=False)
        shutil.copytree(source_root, dest, symlinks=False, ignore=shutil.ignore_patterns(*IGNORE_NAMES))
        manifest = SnapshotManifest(snapshot_id, str(source_root), time.time(), tree_hash, files, str(dest))
        (dest.parent / "manifest.json").write_text(
            json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8"
        )
        return manifest

    def verify(self, manifest: SnapshotManifest) -> bool:
        root = Path(manifest.storage_root)
        _, digest = tree_evidence(root)
        return digest == manifest.tree_sha256


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
        health_check: Callable[[Path], bool] | None = None,
    ) -> RollbackResult:
        if not approved_change_id or not approved_change_id.strip():
            raise PolicyViolation("rollback requires approved_change_id")
        if not self.snapshotter.verify(manifest):
            raise PolicyViolation("snapshot verification failed")
        target = target_root.resolve(strict=True)
        source = Path(manifest.storage_root).resolve(strict=True)
        if target.is_symlink() or source.is_symlink():
            raise PolicyViolation("symlink roots are not permitted")

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

    def inspect_and_contain(
        self,
        clone_root: Path,
        baseline: SnapshotManifest,
        events: Sequence[AttackEvent],
    ) -> tuple[tuple[Detection, ...], tuple[Finding, ...]]:
        clone_root = clone_root.resolve(strict=True)
        baseline_root = Path(baseline.storage_root).resolve(strict=True)
        detections: list[Detection] = []
        findings: list[Finding] = []
        baseline_map = {f.path: f for f in baseline.files}

        for event in events:
            target = (clone_root / event.path).resolve(strict=False)
            if not _inside(target, clone_root):
                raise PolicyViolation("blue containment target escaped range")
            expected = baseline_map.get(event.path)
            changed = target.exists()
            if expected and target.exists():
                changed = hashlib.sha256(target.read_bytes()).hexdigest() != expected.sha256
            restored = False
            if changed:
                baseline_file = baseline_root / event.path
                if baseline_file.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(baseline_file, target)
                elif target.exists():
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
        self.blue = PentaBlue()

    def run(self, source_root: Path, scenarios: Sequence[str] | None = None) -> DrillReport:
        source_root = source_root.resolve(strict=True)
        _, source_before = tree_evidence(source_root)
        started = time.time()
        scenarios = tuple(scenarios or PentaRed.SCENARIOS.keys())

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

    def __init__(self, snapshotter: PentaSnapshot | None = None):
        self.snapshotter = snapshotter or PentaSnapshot()
        self.rollback = PentaRollback(self.snapshotter)

    def plan(self, report: DrillReport) -> HardeningPlan:
        if not report.digest or not report.source_unchanged:
            raise PolicyViolation("only verified, source-safe drill reports may feed PentaLiency")
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
        return HardeningPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:14]}",
            report_id=report.report_id,
            created_at=time.time(),
            actions=tuple(actions),
            dry_run=True,
        )

    def apply(
        self,
        plan: HardeningPlan,
        target_root: Path,
        *,
        approved_change_id: str,
        health_check: Callable[[Path], bool] | None = None,
    ) -> dict[str, object]:
        if not approved_change_id or not approved_change_id.strip():
            raise PolicyViolation("hardening apply requires approved_change_id")
        target_root = target_root.resolve(strict=True)
        if target_root.is_symlink():
            raise PolicyViolation("hardening target may not be a symlink")
        pre = self.snapshotter.create(target_root)
        policy_dir = target_root / ".penta-hardening" / "controls"
        policy_dir.mkdir(parents=True, exist_ok=True)
        for action in plan.actions:
            policy_file = policy_dir / f"{action.control.lower()}.json"
            payload = {
                "control": action.control,
                "policy_key": action.policy_key,
                "policy_value": action.policy_value,
                "rationale": action.rationale,
                "source_plan": plan.plan_id,
                "approved_change_id": approved_change_id,
                "applied_at": time.time(),
            }
            policy_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        health_ok = True if health_check is None else bool(health_check(target_root))
        rollback_result = None
        if not health_ok:
            rollback_result = self.rollback.restore(
                pre,
                target_root,
                approved_change_id=approved_change_id,
                health_check=lambda _: True,
            )
        return {
            "plan_id": plan.plan_id,
            "approved_change_id": approved_change_id,
            "snapshot_id": pre.snapshot_id,
            "health_ok": health_ok,
            "rollback": asdict(rollback_result) if rollback_result else None,
            "applied": health_ok,
        }


@dataclass
class PentaResilienceLoop:
    honeypot: PentaHoneyPot = field(default_factory=PentaHoneyPot)
    liency: PentaLiency = field(default_factory=PentaLiency)

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
