from server import config, aweber as A
from server.db import DB


class R:
    def __init__(self, code, body=None, text=""):
        self.status_code, self._b, self.text = code, body or {}, text

    def json(self):
        return self._b

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def mk(tmp_path):
    cfg = config.get()
    cfg["aweber"].update(client_id="id", client_secret="sec", account_id="1", list_id="2", refresh_token="seed")
    cfg["admin_key"] = "k"
    return A.AWeber(cfg, DB(str(tmp_path / "a.db"))), cfg


def test_refresh_rotates_and_adds_with_update(tmp_path, monkeypatch):
    aw, _ = mk(tmp_path)
    posts = []

    def post(url, **kw):
        posts.append((url, kw))
        if url == A.TOKEN:
            return R(200, {"access_token": "AT", "refresh_token": "NEW", "expires_in": 7200})
        if len(posts) == 2:
            return R(400, text="Subscriber already subscribed")
        return R(201)
    monkeypatch.setattr(A.requests, "post", post)
    assert aw.add("a@b.com", "Ann", ["core-audit"], {"score": "70"}, "8.8.8.8") == "ok"
    assert aw.db.kv_get("aweber_refresh") == "NEW"
    last = posts[-1][1]["json"]
    assert last["update_existing"] == "true" and "ip_address" not in last
    assert posts[-1][1]["headers"]["Authorization"] == "Bearer AT"


def test_not_configured_and_state(tmp_path):
    cfg = config.get()
    aw = A.AWeber(cfg, DB(str(tmp_path / "b.db")))
    assert aw.add("a@b.com", "A", [], {}) == "not_configured"
    aw2, _ = mk(tmp_path)
    assert aw2.state_ok(aw2._state()) and not aw2.state_ok("1.bad")
    assert "subscriber.write" in aw2.connect_url()
