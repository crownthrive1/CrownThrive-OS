from scripts import penta_pm_reconcile as pm


def test_project_state_query_braces_are_balanced() -> None:
    assert pm.PROJECT_STATE_QUERY.count("{") == pm.PROJECT_STATE_QUERY.count("}")


def test_project_items_and_fields_uses_canonical_query(monkeypatch) -> None:
    seen = {}

    def fake_graphql(token, query, variables=None):
        seen["token"] = token
        seen["query"] = query
        seen["variables"] = variables
        return {"node": {"fields": {"nodes": []}, "items": {"nodes": []}}}

    monkeypatch.setattr(pm, "graphql", fake_graphql)
    result = pm.project_items_and_fields("token", "project-id")

    assert result == {"fields": {"nodes": []}, "items": {"nodes": []}}
    assert seen == {
        "token": "token",
        "query": pm.PROJECT_STATE_QUERY,
        "variables": {"id": "project-id"},
    }
