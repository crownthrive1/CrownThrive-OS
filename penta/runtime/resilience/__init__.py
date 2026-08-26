"""CrownThrive Penta resilience suite.

PentaRed is intentionally simulation-only and can operate only inside a
PentaHoneyPot range lease. Production hardening is owned by PentaLiency and
requires an approved change ID plus PentaSnapshot/PentaRollback protection.
"""

from .engine import (
    AttackEvent,
    Detection,
    DrillReport,
    Finding,
    HardeningAction,
    HardeningPlan,
    PentaBlue,
    PentaHoneyPot,
    PentaLiency,
    PentaRed,
    PentaResilienceLoop,
    PentaRollback,
    PentaSnapshot,
    PolicyViolation,
    RangeLease,
    RangePolicy,
    RollbackResult,
    Severity,
    SnapshotManifest,
    penta_status_adapter,
    plan_json,
    report_json,
    tree_evidence,
)

__all__ = [name for name in globals() if not name.startswith("_")]
__version__ = "1.0.0"
