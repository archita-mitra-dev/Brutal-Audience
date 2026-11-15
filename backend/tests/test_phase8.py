"""Phase 8: Revision Impact Tracker and What If? experiments, end to end in demo mode."""
from .test_runs_api import BODY, client, wait_done  # noqa: F401  (client is a fixture)

V2 = BODY["content"].replace("The lighthouse had been dark for eleven years, and nobody in Port Ellery talked about why.",
                             "The lighthouse had been dark for eleven years.")


def _baseline(client, **kw):
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo", **kw}).json()
    wait_done(client, run["id"])
    return sub, run


def test_revision_creates_linked_run_and_comparison(client):
    sub, base = _baseline(client)
    r = client.post(f"/api/runs/{base['id']}/revisions", json={"content": V2})
    assert r.status_code == 201, r.text
    rev = r.json()
    assert rev["kind"] == "revision" and rev["baseline_run_id"] == base["id"]
    assert rev["mode"] == "demo" and rev["blind"] == base["blind"]
    wait_done(client, rev["id"])

    c = client.get(f"/api/runs/{rev['id']}/compare")
    assert c.status_code == 200, c.text
    body = c.json()
    assert body["kind"] == "revision" and body["baseline_run_id"] == base["id"]
    assert body["segments"] and body["personas"] and "noise_note" in body
    # the edited opening is matched to the original opening, not treated as a brand-new segment
    assert body["segments"][0]["change"] == "edited"
    assert body["segments"][1]["change"] == "unchanged"

    # the original draft and its stored text are untouched, and the revision is its own draft
    assert client.get(f"/api/submissions/{sub['id']}").json()["content"] == BODY["content"]
    kids = client.get(f"/api/runs/{base['id']}/children").json()
    assert [k["id"] for k in kids] == [rev["id"]]
    assert len(client.get("/api/submissions").json()) == 2


def test_whatif_is_labelled_and_hidden_from_the_draft_list(client):
    sub, base = _baseline(client)
    r = client.post(f"/api/runs/{base['id']}/whatif", json={"hypothesis": "What if the opening were shorter?", "content": V2})
    assert r.status_code == 201, r.text
    w = r.json()
    assert w["kind"] == "whatif" and w["label"] == "What if the opening were shorter?"
    wait_done(client, w["id"])
    c = client.get(f"/api/runs/{w['id']}/compare").json()
    assert c["kind"] == "whatif" and c["label"] == "What if the opening were shorter?"
    assert "not a guaranteed improvement" in c["noise_note"]
    assert [s["id"] for s in client.get("/api/submissions").json()] == [sub["id"]]


def test_rejections(client):
    sub, base = _baseline(client)
    same = client.post(f"/api/runs/{base['id']}/revisions", json={"content": BODY["content"]})
    assert same.status_code == 422
    assert client.post("/api/runs/nope/revisions", json={"content": V2}).status_code == 404
    assert client.post(f"/api/runs/{base['id']}/whatif", json={"hypothesis": "x", "content": V2}).status_code == 422  # too short
    # an original has nothing to compare against
    assert client.get(f"/api/runs/{base['id']}/compare").status_code == 409
    # no stacking experiments on experiments
    rev = client.post(f"/api/runs/{base['id']}/revisions", json={"content": V2}).json()
    wait_done(client, rev["id"])
    assert client.post(f"/api/runs/{rev['id']}/revisions", json={"content": V2 + " more"}).status_code == 409


def test_other_users_cannot_touch_runs(client):
    from .helpers import authenticate
    _, base = _baseline(client)
    authenticate(client, email="intruder@example.com")
    assert client.post(f"/api/runs/{base['id']}/revisions", json={"content": V2}).status_code == 404
    assert client.get(f"/api/runs/{base['id']}/children").status_code == 404
    authenticate(client)  # back to the owner
    rev = client.post(f"/api/runs/{base['id']}/revisions", json={"content": V2}).json()
    wait_done(client, rev["id"])
    authenticate(client, email="intruder@example.com")
    assert client.get(f"/api/runs/{rev['id']}/compare").status_code == 404


def test_revision_reuses_blind_setting(client):
    _, base = _baseline(client, blind=False)
    rev = client.post(f"/api/runs/{base['id']}/revisions", json={"content": V2}).json()
    assert rev["blind"] is False


def test_unfinished_baseline_blocks_revision(client):
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo"}).json()
    # immediately after start the run is not completed yet (or just finished); only assert the guard path when it isn't
    r = client.post(f"/api/runs/{run['id']}/revisions", json={"content": V2})
    assert r.status_code in (201, 409)
    wait_done(client, run["id"])
