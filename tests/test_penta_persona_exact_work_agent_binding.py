from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260829040703_penta_persona_exact_work_agent_binding_v1.sql"


def test_work_bound_execution_selects_exact_assigned_agent():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "where agent_id=v_work.assigned_agent_id" in sql
    assert "and persona_id=p_persona_id" in sql
    assert "WORK_ASSIGNED_AGENT_NOT_ACTIVE" in sql
    assert "WORK_PERSONA_ASSIGNMENT_MISMATCH" in sql
    assert "exact_work_agent_binding" in sql


def test_unbound_execution_prefers_primary_over_subagent():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "case when coalesce((metadata->>'subagent')::boolean,false) then 1 else 0 end" in sql


def test_client_execution_remains_revoked():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "revoke all on function crm.penta_persona_enqueue_execution_v1" in sql
    assert "from public,anon,authenticated" in sql
    assert "grant execute on function crm.penta_persona_enqueue_execution_v1" in sql
    assert "to service_role" in sql
