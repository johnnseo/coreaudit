from coreaudit import gbp, pagespeed
from coreaudit.models import Finding
from coreaudit.scoring import route_lead, score


class R:
    def __init__(self, code, body):
        self.status_code, self._b, self.text = code, body, str(body)

    def json(self):
        return self._b

    def raise_for_status(self):
        pass


OK = {"lighthouseResult": {"categories": {"performance": {"score": 0.71}}, "audits": {
    "largest-contentful-paint": {"numericValue": 3000}}}}
BADKEY = {"error": {"message": "API key not valid. Please pass a valid API key.", "errors": [{"reason": "badRequest"}]}}


def test_pagespeed_falls_back_when_key_rejected(monkeypatch):
    monkeypatch.setenv("PAGESPEED_API_KEY", "bad")
    calls = []

    def fake(url, params=None, timeout=0):
        calls.append(dict(params))
        return R(400, BADKEY) if "key" in params else R(200, OK)
    monkeypatch.setattr(pagespeed.requests, "get", fake)
    r = pagespeed.run("https://x.test/", "mobile")
    assert r["score"] == 71 and "rejected" in r["note"] and "key" not in calls[-1]


def test_pagespeed_tries_other_url_spelling(monkeypatch):
    monkeypatch.delenv("PAGESPEED_API_KEY", raising=False)
    seen = []

    def fake(url, params=None, timeout=0):
        seen.append(params["url"])
        return R(400, {"error": {"message": "FAILED_DOCUMENT_REQUEST", "errors": [{"reason": "badRequest"}]}}) \
            if len(seen) == 1 else R(200, OK)
    monkeypatch.setattr(pagespeed.requests, "get", fake)
    assert pagespeed.run("https://x.test", "mobile")["score"] == 71 and len(set(seen)) == 2


def test_gbp_findings():
    g = {"ok": True, "found": True, "name": "Acme", "rating": 4.8, "reviews": 3, "claimed": True, "phone": "(312) 555-0100",
         "hours": True, "photos": 2}
    ids = {f.id: f for f in gbp.findings(g, "312-555-0199")}
    assert ids["E-gbp-reviews"].status == "warn" and ids["E-gbp-nap"].status == "warn" and "ok-gbp" in ids
    assert gbp.findings({"ok": True, "found": False}, "")[0].id == "E-gbp-none"
    assert gbp.findings({"ok": False}, "") == []


def test_routing_uses_answers():
    f = [Finding(id=str(i), area="E", title="t", status="fail", severity="high") for i in range(2)]
    s = score(f)
    assert route_lead(s, f, {"help": "dfy", "goals": ["leads"]}) == "done_for_you"
    assert route_lead(s, [], {"help": "unsure", "goals": ["unsure"]}) == "nurture"
