from scripts.penta_pr_admission import decide


def candidate():
    return {
        "repo": "crownthrive1/CrownThrive-OS",
        "subject_key": "release:3.69.1.0",
        "owner_lane": "penta.release",
        "release_candidate_key": "crownthrive1/CrownThrive-OS:3.69.1.0:gen1",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "base_relationship": "current_main",
        "authority_class": "D2",
        "changed_files": ["release.json"],
        "tests": {"status": "PASS"},
        "rollback": {"defined": True, "procedure": "abandon candidate"},
        "evidence": {
            "claims": [
                {
                    "name": "governed_gate",
                    "state": "PASS",
                    "exact_head": True,
                    "provider_receipt": "github-actions:123",
                }
            ]
        },
        "post_open_obligations": ["PentaCertifier exact-head certificate"],
        "authority_created": False,
        "reconciliation": {
            "current_main_sha": "a" * 40,
            "checked_at": "2026-08-31T18:40:00Z",
            "topology_snapshot_ref": "penta-census:current",
            "current_changes_checked": True,
            "open_prs_checked": True,
            "active_owners_checked": True,
            "production_truth_checked": True,
            "founder_intent_checked": True,
            "behavior_change_review_complete": True,
            "affected_surfaces": ["release"],
            "current_change_refs": ["git:main@" + "a" * 40],
            "production_truth_refs": ["provider:readback:1"],
            "active_owner_refs": [],
            "behavior_changes": [],
        },
    }


def test_create_only_complete_current_reconciled_unowned_candidate():
    assert decide(candidate(), [])["decision"] == "CREATE"


def test_reuse_same_subject():
    c = candidate()
    r = decide(c, [{"repo": c["repo"], "subject_key": c["subject_key"], "number": 2174}])
    assert (r["decision"], r["pr_number"]) == ("REUSE", 2174)


def test_reuse_same_release_generation_even_if_subject_label_drifted():
    c = candidate()
    r = decide(
        c,
        [
            {
                "repo": c["repo"],
                "subject_key": "release-intelligence:3.69.1.0",
                "release_candidate_key": c["release_candidate_key"],
                "number": 2176,
            }
        ],
    )
    assert r["decision"] == "REUSE"


def test_hold_unproven_pass_claim():
    c = candidate()
    c["evidence"]["claims"][0]["provider_receipt"] = None
    assert decide(c, [])["reason"] == "unproven_pass_claim"


def test_hold_multiple_open_owners():
    c = candidate()
    prs = [
        {"repo": c["repo"], "subject_key": c["subject_key"], "number": 1},
        {"repo": c["repo"], "subject_key": c["subject_key"], "number": 2},
    ]
    assert decide(c, prs)["reason"] == "multiple_open_owner_prs"


def test_hold_stale_main_before_new_pr_creation():
    c = candidate()
    c["reconciliation"]["current_main_sha"] = "c" * 40
    assert decide(c, [])["reason"] == "stale_base_requires_reconcile"


def test_hold_when_topology_or_current_change_scan_missing():
    c = candidate()
    c["reconciliation"]["current_changes_checked"] = False
    c["reconciliation"]["active_owners_checked"] = False
    result = decide(c, [])
    assert result["reason"] == "current_reconciliation_incomplete"
    assert set(result["incomplete"]) == {"current_changes_checked", "active_owners_checked"}


def test_hold_behavior_change_without_explicit_authority():
    c = candidate()
    c["reconciliation"]["behavior_changes"] = [
        {
            "behavior_key": "collab_portal_tracking_cc",
            "observed_state": "enabled",
            "desired_state": "disabled",
        }
    ]
    result = decide(c, [])
    assert result["reason"] == "behavior_change_without_authority"
    assert result["behavior_key"] == "collab_portal_tracking_cc"


def test_allow_authorized_behavior_change_after_current_truth_review():
    c = candidate()
    c["reconciliation"]["behavior_changes"] = [
        {
            "behavior_key": "example_behavior",
            "observed_state": "v1",
            "desired_state": "v2",
            "authority_ref": "founder-directive:example",
        }
    ]
    assert decide(c, [])["decision"] == "CREATE"


def test_stacked_candidate_requires_open_owner_and_exact_owner_head():
    c = candidate()
    c["base_relationship"] = "stacked_owner"
    c["stacked_on_pr"] = 99
    c["base_sha"] = "d" * 40
    owner = {"repo": c["repo"], "number": 99, "head_sha": "d" * 40, "subject_key": "dependency"}
    assert decide(c, [owner])["decision"] == "CREATE"
    c["base_sha"] = "e" * 40
    assert decide(c, [owner])["reason"] == "stacked_base_not_owner_head"
