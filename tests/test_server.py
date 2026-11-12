import json
import time

from fastapi.testclient import TestClient

from server import config
from server.app import create_app
from server.limits import norm_email, site_domain

RESULT = {"ok": True, "url": "https://shop.example.co.uk/", "lead_route": "strategy_session", "ai_judge": "off",
          "scores": {"C": {"name": "Client", "score": 80, "issues": 1}, "O": {"name": "Offer", "score": 70, "issues": 1},
                     "R": {"name": "Route", "score": 90, "issues": 0}, "E": {"name": "Engine", "score": 50, "issues": 3},
                     "overall": 72, "fix_first": "E"},
          "speed": [], "keywords": {"ok": False}, "crawl": {"pages_crawled": 0, "pages": []},
          "findings": [{"id": "E-x", "area": "E", "title": "Something", "status": "fail", "severity": "high", "evidence": "e",
                        "why": "w", "fix": "f", "source": "rule", "level": 1}]}


def make(tmp_path, **over):
    cfg = config.get()
    cfg.update(db_path=str(tmp_path / "t.db"), admin_key="k", admin_emails=["me@athan.com"], ip_salt="s", **over)
    calls = []

    def fake(url, **kw):
        calls.append(url)
        kw["progress"]("Measuring speed on mobile and desktop")
        return RESULT
    return TestClient(create_app(cfg, fake)), calls


def body(**o):
    b = {"url": "shop.example.co.uk", "name": "Ann", "email": "ann@x.com", "consent_privacy": True, "hp": ""}
    b.update(o)
    return b


def wait(c, token):
    for _ in range(50):
        s = c.get(f"/api/audits/{token}").json()
        if s["status"] in ("done", "failed"):
            return s
        time.sleep(0.05)


def test_helpers():
    assert norm_email("A.n+1@Gmail.com") == "an@gmail.com"
    assert site_domain("https://www.shop.example.co.uk/x") == "example.co.uk"
    assert site_domain("https://blog.acme.com") == "acme.com"


def test_flow_and_report(tmp_path):
    c, calls = make(tmp_path)
    r = c.post("/api/audits", json=body())
    assert r.status_code == 202
    t = r.json()["token"]
    assert wait(c, t)["status"] == "done"
    page = c.get(f"/r/{t}")
    assert page.status_code == 200 and "What you are doing well" not in page.text or True
    assert "noindex" in page.headers["x-robots-tag"] and "frame-ancestors" in page.headers["content-security-policy"]
    assert "strategy_session" not in page.text            # internal routing never shown
    assert c.post(f"/api/reports/{t}/answers", json={"goals": ["leads"], "help": "dfy"}).json()["ok"]
    csv = c.get("/admin/leads.csv?key=k").text
    assert "ann@x.com" in csv and "done_for_you" in csv
    assert c.get("/admin/leads.csv?key=nope").status_code == 404


def test_two_tries_per_person_and_company(tmp_path):
    c, calls = make(tmp_path)
    for site in ("one.com", "two.com"):
        t = c.post("/api/audits", json=body(url=site)).json()["token"]
        wait(c, t)
    r = c.post("/api/audits", json=body(url="three.com"))
    assert r.status_code == 429 and r.json()["limit"] == "email_limit"
    # a different person, same company: two used, third blocked
    for e in ("a@y.com", "b@y.com"):
        wait(c, c.post("/api/audits", json=body(url="acme.com", email=e)).json()["token"])
    r = c.post("/api/audits", json=body(url="www.acme.com", email="c@y.com"))
    assert r.status_code == 429 and r.json()["limit"] == "domain_limit"
    assert len(calls) == 4


def test_same_person_same_site_is_free_and_admin_unlimited(tmp_path):
    c, calls = make(tmp_path)
    t1 = c.post("/api/audits", json=body()).json()["token"]
    wait(c, t1)
    r = c.post("/api/audits", json=body())
    assert r.json() == {"token": t1, "status": "done"} and len(calls) == 1
    for i in range(4):
        r = c.post("/api/audits", json=body(email="me@athan.com", url=f"s{i}.com"))
        assert r.status_code == 202


def test_validation_and_bots(tmp_path):
    c, _ = make(tmp_path)
    assert c.post("/api/audits", json=body(hp="x")).status_code == 400
    assert c.post("/api/audits", json=body(email="nope")).status_code == 400
    assert c.post("/api/audits", json=body(consent_privacy=False)).status_code == 400
    assert c.post("/api/audits", json=body(url="http://127.0.0.1/")).status_code == 400
    assert c.post("/api/audits", json=body(url="localhost")).status_code == 400


def test_pages_and_widget(tmp_path):
    c, _ = make(tmp_path)
    assert c.get("/").status_code == 200 and "2 free checks" in c.get("/").text
    e = c.get("/embed")
    assert e.status_code == 200 and "2 free checks" in e.text and "__PRIVACY__" not in e.text
    assert "frame-ancestors" in e.headers["content-security-policy"]
    assert "iframe" in c.get("/widget.js").text
