import json
import time

from fastapi.testclient import TestClient

from coreaudit.models import Finding
from server import config
from server.app import create_app
from tests.test_server import RESULT


def make2(tmp_path, ai=None, **over):
    cfg = config.get()
    cfg.update(db_path=str(tmp_path / "t.db"), admin_key="k", admin_emails=["me@athan.com"], ip_salt="s", **over)
    calls = {"audit": [], "ai": 0, "kw": []}

    def fake(url, **kw):
        calls["audit"].append(url)
        calls["kw"].append(kw)
        return RESULT

    def fake_ai(url):
        calls["ai"] += 1
        return [Finding(id="AI-0", area="C", title="Headline is vague", status="fail", severity="high",
                        evidence='"Welcome"', why="w", fix="f", source="ai", level=2)], "1 kept of 1 proposed"
    return TestClient(create_app(cfg, fake, ai or fake_ai)), calls


def wait(c, t, want="done"):
    for _ in range(60):
        j = c.get(f"/api/v2/audits/{t}").json()
        if j["status"] == want or j["status"] == "failed":
            return j
        time.sleep(0.05)
    raise AssertionError(j)


def start(c, url="shop.example.co.uk", **o):
    return c.post("/api/v2/audits", json={"url": url, "hp": "", **o})


def unlock(c, t, email="ann@x.com", **o):
    b = {"name": "Ann", "email": email, "consent_privacy": True}
    b.update(o)
    return c.post(f"/api/v2/audits/{t}/unlock", json=b)


def test_flow_teaser_then_unlock_spends_tokens_only_after_email(tmp_path):
    c, calls = make2(tmp_path)
    assert "How strong is your marketing foundation" in c.get("/v2").text and "/*THEME*/" not in c.get("/v2").text
    r = start(c, src="yt")
    assert r.status_code == 202
    t = r.json()["token"]
    j = wait(c, t)
    tz = j["teaser"]
    assert tz["overall"] == 72 and tz["fix_first"] == "E" and [a["score"] for a in tz["areas"]] == [80, 70, 90, 50]
    assert tz["to_fix"] == 1 and tz["high"] == 1 and tz["host"] == "example.co.uk"
    assert "findings" not in j and "E-x" not in json.dumps(j)         # no detail leaks before the email
    assert calls["kw"][0]["use_ai"] is False and calls["ai"] == 0       # no tokens spent yet
    assert c.get(f"/r/{t}", follow_redirects=False).status_code == 302   # report is locked
    assert unlock(c, t, consent_privacy=False).status_code == 400
    assert unlock(c, t, email="bad").status_code == 400
    assert unlock(c, t).status_code == 202
    wait(c, t)
    assert calls["ai"] == 1
    html = c.get(f"/r/{t}").text
    assert "Headline is vague" in html and "#111111" in html and "How to read your score" in html and "athan-logo-dark.png" in html           # AI finding in, dark theme on
    assert c.get(f"/api/v2/audits/{t}").json()["teaser"]["overall"] == 72   # scores did not move
    csv = c.get("/admin/leads.csv?key=k").text
    assert "audit-v2" in csv and "ann@x.com" in csv
    assert "audit-v2" in c.get("/admin/ab?key=k").text


def test_cache_limits_and_admin(tmp_path):
    c, calls = make2(tmp_path, max_per_ip_day=50, v2_domain_month=3)
    first = start(c).json()["token"]
    wait(c, first)
    again = start(c)                                                    # same site again: free, instant, not counted
    assert again.status_code == 200 and again.json()["status"] == "done" and len(calls["audit"]) == 1
    for i in range(3):                                                  # 3 runs allowed for a new company
        r = start(c, url=f"https://acme.com/p{i}")
        assert r.status_code == 202
        wait(c, r.json()["token"])
    r = start(c, url="https://acme.com/p9")
    assert r.status_code == 429 and r.json()["limit"] == "domain_limit"


def test_email_limit_and_global_cap(tmp_path):
    c, _ = make2(tmp_path, max_per_ip_day=50, v2_email_month=2)
    toks = []
    for i in range(3):
        t = start(c, url=f"https://site{i}.com").json()["token"]
        wait(c, t)
        toks.append(t)
    assert unlock(c, toks[0]).status_code == 202
    assert unlock(c, toks[1]).status_code == 202
    r = unlock(c, toks[2])
    assert r.status_code == 429 and r.json()["limit"] == "email_limit"
    assert unlock(c, toks[2], email="me@athan.com").status_code == 202   # admin exempt
    c2, _ = make2(tmp_path / "b", max_per_ip_day=50, max_audits_per_day=1)
    assert start(c2, url="https://one.com").status_code == 202
    assert start(c2, url="https://two.com").json()["limit"] == "busy"


def test_validation_and_split(tmp_path):
    c, _ = make2(tmp_path)
    assert start(c, hp="x").status_code == 400
    assert start(c, url="http://127.0.0.1").status_code == 400
    assert c.get("/api/v2/audits/nope").status_code == 404
    assert c.get("/get?v=v2&src=ig", follow_redirects=False).headers["location"] == "/v2?src=ig"
    assert c.get("/get", follow_redirects=False).headers["location"].startswith("/v2")   # sticky
    c2, _ = make2(tmp_path / "z")
    assert c2.get("/get?v=v1", follow_redirects=False).headers["location"] == "/embed"
