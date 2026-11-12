from tests.test_server import make


def start(c, **o):
    b = {"name": "Ann", "email": "ann@x.com", "consent_privacy": True, "hp": ""}
    b.update(o)
    return c.post("/api/scorecard", json=b)


def test_flow_and_scoring(tmp_path):
    c, _ = make(tmp_path)
    r = start(c)
    assert r.status_code == 200 and not r.json()["done"]
    t = r.json()["token"]
    assert c.post(f"/api/scorecard/{t}/answers", json={"answers": [1, 2]}).status_code == 400
    a = [2, 2, 2, 2, 2, 2, 1, 1, 1, 0, 0, 0]               # Engine lowest
    res = c.post(f"/api/scorecard/{t}/answers", json={"answers": a}).json()
    assert res["total"] == 15 and res["max_total"] == 24 and res["fix_first"] == 3 and res["scores"] == [6, 6, 3, 0]
    assert c.get(f"/api/scorecard/{t}").json()["done"]
    assert "Fix this first" in c.get(f"/s/{t}").text or "Your result" in c.get(f"/s/{t}").text
    assert c.get("/s/nope").status_code == 404
    again = start(c).json()                                  # same email: straight to result
    assert again["done"] and again["token"] == t


def test_validation(tmp_path):
    c, _ = make(tmp_path)
    assert start(c, hp="x").status_code == 400
    assert start(c, name="").status_code == 400
    assert start(c, consent_privacy=False).status_code == 400
    assert start(c, email="bad").status_code == 400


def test_tie_goes_to_first_area():
    from server.scorecard import score
    assert score([1] * 12)["fix_first"] == 0


def test_split_and_admin(tmp_path):
    c, _ = make(tmp_path)
    r = c.get("/get?v=scorecard", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/scorecard"
    assert c.cookies.get("core_ab") == "scorecard"
    assert c.get("/get", follow_redirects=False).headers["location"] == "/scorecard"   # sticky
    c.get("/scorecard")
    t = start(c).json()["token"]
    c.post(f"/api/scorecard/{t}/answers", json={"answers": [2] * 12})
    assert c.get("/admin/ab").status_code == 404
    html = c.get("/admin/ab?key=k").text
    assert "scorecard" in html and "<td>1</td>" in html
    csv = c.get("/admin/leads.csv?key=k").text
    assert "scorecard" in csv
    c2, _ = make(tmp_path / "b")
    assert c2.get("/get?v=audit", follow_redirects=False).headers["location"] == "/embed"
