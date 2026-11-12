import time

from tests.test_server import make, body, wait


def start(c, **o):
    b = {"name": "Ann", "email": "ann@x.com", "consent_privacy": True, "hp": ""}
    b.update(o)
    return c.post("/api/scorecard", json=b)


def test_flow_and_scoring(tmp_path):
    c, _ = make(tmp_path)
    r = start(c, src="IG Bio!")
    assert r.status_code == 200 and not r.json()["done"]
    t = r.json()["token"]
    assert c.post(f"/api/scorecard/{t}/answers", json={"answers": [1, 2]}).status_code == 400
    a = [2, 2, 2, 2, 2, 2, 1, 1, 1, 0, 0, 0]
    res = c.post(f"/api/scorecard/{t}/answers", json={"answers": a}).json()
    assert res["total"] == 15 and res["fix_first"] == 3 and res["scores"] == [6, 6, 3, 0]
    assert c.get(f"/api/scorecard/{t}").json()["done"]
    assert "Your result" in c.get(f"/s/{t}").text and c.get("/s/nope").status_code == 404
    assert start(c).json() == {"token": t, "done": True}
    assert "igbio" in c.get("/admin/ab?key=k").text or "direct" in c.get("/admin/ab?key=k").text


def test_validation(tmp_path):
    c, _ = make(tmp_path)
    assert start(c, hp="x").status_code == 400
    assert start(c, name="").status_code == 400
    assert start(c, consent_privacy=False).status_code == 400
    assert start(c, email="bad").status_code == 400


def test_tie_goes_to_first_area():
    from server.scorecard import score
    assert score([1] * 12)["fix_first"] == 0


def test_audit_bonus(tmp_path):
    c, _ = make(tmp_path)
    t = c.post("/api/audits", json=body(src="youtube")).json()["token"]
    wait(c, t)
    html = c.get(f"/r/{t}").text
    assert f"/scorecard?from={t}" in html and "Take the scorecard" in html
    c.get(f"/scorecard?from={t}")
    r = c.post("/api/scorecard", json={"from": t}).json()           # no form, reuses their details
    assert not r["done"]
    c.post(f"/api/scorecard/{r['token']}/answers", json={"answers": [2] * 12})
    assert c.post("/api/scorecard", json={"from": "bad"}).status_code == 400
    ab = c.get("/admin/ab?key=k").text
    assert "audit-bonus" in ab and "youtube" in ab
    assert "audit-bonus" in c.get("/admin/leads.csv?key=k").text or "scorecard" in c.get("/admin/leads.csv?key=k").text
