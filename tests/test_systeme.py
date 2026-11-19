from server import config, systeme as S


class R:
    def __init__(self, code, data=None):
        self.status_code, self._d, self.text = code, data or {}, str(data)

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(self.status_code)


def make(monkeypatch, contact_status=201):
    cfg = config.load() if hasattr(config, "load") else config.get()
    cfg["systeme"]["api_key"] = "k"
    calls = []

    def post(url, **kw):
        calls.append(("POST", url, kw.get("json")))
        if url.endswith("/contacts"):
            return R(contact_status, {"id": 7})
        if url.endswith("/tags") and "contacts" not in url:
            return R(201, {"id": 9, "name": kw["json"]["name"]})
        return R(200)

    def get(url, **kw):
        calls.append(("GET", url, kw.get("params")))
        if url.endswith("/tags"):
            return R(200, {"items": []})
        return R(200, {"items": [{"id": 7}]})

    def patch(url, **kw):
        calls.append(("PATCH", url, kw.get("json")))
        return R(200)

    monkeypatch.setattr(S.requests, "post", post)
    monkeypatch.setattr(S.requests, "get", get)
    monkeypatch.setattr(S.requests, "patch", patch)
    return S.Systeme(cfg, None), calls


def test_new_contact_gets_fields_and_tags(monkeypatch):
    s, calls = make(monkeypatch)
    assert s.add("a@b.co", "Ann", ["core-lead", "newsletter-optin"], {"score": "62", "site": "x.com", "fix_first": ""}) == "ok"
    body = calls[0][2]
    assert body["email"] == "a@b.co" and {"slug": "score", "value": "62"} in body["fields"]
    assert {"slug": "fix_first", "value": ""} not in body["fields"]
    assert sum(1 for c in calls if c[1].endswith("/contacts/7/tags")) == 2


def test_existing_contact_is_updated(monkeypatch):
    s, calls = make(monkeypatch, contact_status=422)
    assert s.add("a@b.co", "Ann", ["core-lead"], {"score": "1"}) == "ok"
    assert any(c[0] == "PATCH" for c in calls)


def test_not_configured():
    cfg = config.load() if hasattr(config, "load") else config.get()
    cfg["systeme"]["api_key"] = ""
    assert S.Systeme(cfg, None).add("a@b.co", "A", [], {}) == "not_configured"
