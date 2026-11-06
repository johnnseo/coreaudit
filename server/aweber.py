"""AWeber: add the visitor to your list with their results. Fails soft: a lead is never lost
(it is always saved in our own database first)."""
import base64
import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests

AUTH = "https://auth.aweber.com/oauth2/authorize"
TOKEN = "https://auth.aweber.com/oauth2/token"
API = "https://api.aweber.com/1.0"
SCOPES = "account.read list.read subscriber.read subscriber.write"


class AWeber:
    def __init__(self, cfg, db):
        self.cfg, self.db = cfg["aweber"], db
        self.base = cfg["public_base"]
        self.admin_key = cfg["admin_key"]
        self._access, self._exp = None, 0

    @property
    def configured(self):
        a = self.cfg
        return bool(a["client_id"] and a["client_secret"] and a["account_id"] and a["list_id"]
                    and (self.db.kv_get("aweber_refresh") or a["refresh_token"]))

    # ---- one-time connect (visit /admin/aweber/connect?key=ADMIN_KEY) ----
    def redirect_uri(self):
        return f"{self.base}/admin/aweber/callback"

    def _state(self):
        t = str(int(time.time()))
        sig = hmac.new(self.admin_key.encode(), t.encode(), hashlib.sha256).hexdigest()[:24]
        return f"{t}.{sig}"

    def state_ok(self, state):
        try:
            t, sig = state.split(".")
            good = hmac.new(self.admin_key.encode(), t.encode(), hashlib.sha256).hexdigest()[:24]
            return hmac.compare_digest(sig, good) and time.time() - int(t) < 900
        except Exception:
            return False

    def connect_url(self):
        q = {"response_type": "code", "client_id": self.cfg["client_id"], "redirect_uri": self.redirect_uri(),
             "scope": SCOPES, "state": self._state()}
        return f"{AUTH}?{urlencode(q)}"

    def _basic(self):
        raw = f'{self.cfg["client_id"]}:{self.cfg["client_secret"]}'.encode()
        return {"Authorization": "Basic " + base64.b64encode(raw).decode()}

    def exchange_code(self, code):
        r = requests.post(TOKEN, headers=self._basic(), timeout=30, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri()})
        r.raise_for_status()
        self._store(r.json())

    def _store(self, tok):
        self._access = tok["access_token"]
        self._exp = time.time() + int(tok.get("expires_in", 7200)) - 120
        if tok.get("refresh_token"):          # refresh tokens may rotate: always keep the newest
            self.db.kv_set("aweber_refresh", tok["refresh_token"])

    def _token(self):
        if self._access and time.time() < self._exp:
            return self._access
        refresh = self.db.kv_get("aweber_refresh") or self.cfg["refresh_token"]
        r = requests.post(TOKEN, headers=self._basic(), timeout=30,
                          data={"grant_type": "refresh_token", "refresh_token": refresh})
        r.raise_for_status()
        self._store(r.json())
        return self._access

    def _h(self):
        return {"Authorization": f"Bearer {self._token()}", "Accept": "application/json"}

    def lists(self):
        """For setup: shows your account id and list ids."""
        accts = requests.get(f"{API}/accounts", headers=self._h(), timeout=30).json().get("entries", [])
        out = []
        for a in accts:
            ls = requests.get(f"{API}/accounts/{a['id']}/lists", headers=self._h(), timeout=30).json().get("entries", [])
            out.append({"account_id": a["id"], "lists": [{"id": x["id"], "name": x.get("name")} for x in ls]})
        return out

    def add(self, email, name, tags, fields, ip=None):
        if not self.configured:
            return "not_configured"
        url = f'{API}/accounts/{self.cfg["account_id"]}/lists/{self.cfg["list_id"]}/subscribers'
        body = {"email": email, "name": (name or "")[:60] or None, "tags": tags, "custom_fields": fields,
                "misc_notes": "C.O.R.E. audit tool"}
        if ip:
            body["ip_address"] = ip
        body = {k: v for k, v in body.items() if v}
        try:
            r = requests.post(url, headers=self._h(), json=body, timeout=30)
            if r.status_code == 400 and "already" in r.text.lower():
                body.pop("ip_address", None)
                body["update_existing"] = "true"
                r = requests.post(url, headers=self._h(), json=body, timeout=30)
            return "ok" if r.status_code in (200, 201) else f"error {r.status_code}: {r.text[:120]}"
        except Exception as e:
            return f"error: {str(e)[:120]}"
