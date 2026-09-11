import re
from pathlib import Path

MIGRATION = Path("supabase/migrations/20260903055000_penta_security_pr_cleanup_source_policy_pack_v2.sql")
ROLLBACK = Path("supabase/rollback/20260903055000_penta_security_pr_cleanup_source_policy_pack_v2_rollback.sql")

SQL_OBJECT = re.compile(
    r"\b(?:create|alter|drop)\s+(?:or\s+replace\s+)?(?:table|function|view|sequence|policy|trigger)\s+"
    r"(?:if\s+(?:not\s+)?exists\s+)?([A-Za-z_][A-Za-z0-9_.]*)",
    re.IGNORECASE,
)


def test_cleanup_policy_pack_is_additive_and_authority_neutral():
    src = MIGRATION.read_text(encoding="utf-8")
    assert src.count("'1.0.0'") >= 4
    assert src.count("'none'") >= 4
    assert "ON CONFLICT(policy_key,policy_version) DO NOTHING" in src
    assert "DELETE FROM penta_security.provider_source_policies_v1" not in src.upper()
    assert "UPDATE penta_security.provider_source_policies_v1" not in src


def test_cleanup_policy_pack_covers_root_terminalization_subjects():
    src = MIGRATION.read_text(encoding="utf-8")
    expected = {
        "supabase/migrations/20260902193000_penta_pr_lifecycle_stale_sequence_fix_v2.sql",
        "supabase/migrations/20260901210200_penta_pr_repo_identity_citext_v2.sql",
        ".github/workflows/pentarelease-release-intelligence-v3.yml",
        "supabase/functions/penta-institutional-pr-terminal-provider/index.ts",
    }
    for path in expected:
        assert path in src


def test_cleanup_policy_pack_requires_security_controls_not_business_outcomes():
    src = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "HOLD_STALE_PREDECESSOR_HANDOFF_REQUIRED",
        "penta_pr_active_alias_head_conflict",
        "Reusing deterministic exact-base/exact-content release-intelligence subject",
        'const institutional = sb.schema("integration_control");',
        "authority_effect"
    ):
        assert marker in src
    assert "independent_certification',true" not in src
    assert "authority_expansion',true" not in src


def test_policy_data_literals_do_not_claim_target_runtime_objects_in_collision_scanner():
    src = MIGRATION.read_text(encoding="utf-8")
    assert SQL_OBJECT.findall(src) == []


def test_cleanup_policy_rollback_is_append_only_retirement():
    src = ROLLBACK.read_text(encoding="utf-8")
    assert "'1.0.1'" in src
    assert "'retired'" in src
    assert "'1.0.0'" in src
    assert "DELETE FROM penta_security.provider_source_policies_v1" not in src.upper()
    assert "UPDATE penta_security.provider_source_policies_v1" not in src
