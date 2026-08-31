from scripts.penta_pr_admission import decide


def candidate():
    return {
        "repo":"crownthrive1/CrownThrive-OS","subject_key":"release:3.69.1.0","owner_lane":"penta.release",
        "release_candidate_key":"crownthrive1/CrownThrive-OS:3.69.1.0:gen1","base_sha":"a"*40,"head_sha":"b"*40,
        "authority_class":"D2","changed_files":["release.json"],"tests":{"status":"PASS"},
        "rollback":{"defined":True,"procedure":"abandon candidate"},
        "evidence":{"claims":[{"name":"governed_gate","state":"PASS","exact_head":True,"provider_receipt":"github-actions:123"}]},
        "post_open_obligations":["PentaCertifier exact-head certificate"],"authority_created":False,
    }


def test_create_only_complete_unowned_candidate():
    assert decide(candidate(), [])["decision"] == "CREATE"


def test_reuse_same_subject():
    c=candidate(); r=decide(c,[{"repo":c["repo"],"subject_key":c["subject_key"],"number":2174}])
    assert (r["decision"],r["pr_number"]) == ("REUSE",2174)


def test_reuse_same_release_generation_even_if_subject_label_drifted():
    c=candidate(); r=decide(c,[{"repo":c["repo"],"subject_key":"release-intelligence:3.69.1.0","release_candidate_key":c["release_candidate_key"],"number":2176}])
    assert r["decision"] == "REUSE"


def test_hold_unproven_pass_claim():
    c=candidate(); c["evidence"]["claims"][0]["provider_receipt"] = None
    assert decide(c,[])["reason"] == "unproven_pass_claim"


def test_hold_multiple_open_owners():
    c=candidate(); prs=[{"repo":c["repo"],"subject_key":c["subject_key"],"number":1},{"repo":c["repo"],"subject_key":c["subject_key"],"number":2}]
    assert decide(c,prs)["reason"] == "multiple_open_owner_prs"
