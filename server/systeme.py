"""systeme.io: add the visitor as a contact with a tag and custom fields. Same job as aweber.py and the same
promise: it fails soft, because the lead is always saved in our own database first.

Written from systeme.io's public API docs (base https://api.systeme.io/api, header X-API-Key). Verify with ONE live
test: the `aweber` column in /admin/leads.csv shows `ok` or the exact error."""
import requests

API = "https://api.systeme.io/api"


class Systeme:
    def __init__(self, cfg, db):
        self.key = cfg["systeme"]["api_key"]
        self.db = db
        self._tags = {}

    @property
    def configured(self):
        return bool(self.key)

    def _h(self, extra=None):
        h = {"X-API-Key": self.key, "Accept": "application/json", "Content-Type": "application/json"}
        h.update(extra or {})
        return h

    def _tag_id(self, name):
        if name in self._tags:
            return self._tags[name]
        r = requests.get(f"{API}/tags", headers=self._h(), params={"limit": 100}, timeout=30)
        r.raise_for_status()
        for t in r.json().get("items", []):
            self._tags[t["name"]] = t["id"]
        if name not in self._tags:
            c = requests.post(f"{API}/tags", headers=self._h(), json={"name": name}, timeout=30)
            c.raise_for_status()
            self._tags[name] = c.json()["id"]
        return self._tags[name]

    def add(self, email, name, tags, fields, ip=None):
        if not self.configured:
            return "not_configured"
        flds = [{"slug": "first_name", "value": (name or "")[:60]}] if name else []
        flds += [{"slug": k, "value": str(v)} for k, v in (fields or {}).items() if v not in (None, "")]
        try:
            r = requests.post(f"{API}/contacts", headers=self._h(), timeout=30,
                              json={"email": email, "locale": "en", "fields": flds})
            if r.status_code in (200, 201):
                cid = r.json()["id"]
            else:                                   # already a contact: find it and update its fields
                f = requests.get(f"{API}/contacts", headers=self._h(), params={"email": email}, timeout=30)
                items = f.json().get("items", []) if f.status_code == 200 else []
                if not items:
                    return f"error {r.status_code}: {r.text[:120]}"
                cid = items[0]["id"]
                u = requests.patch(f"{API}/contacts/{cid}", timeout=30, json={"fields": flds},
                                   headers=self._h({"Content-Type": "application/merge-patch+json"}))
                if u.status_code not in (200, 201, 204):
                    return f"error {u.status_code}: {u.text[:120]}"
            for t in tags:
                tr = requests.post(f"{API}/contacts/{cid}/tags", headers=self._h(), json={"tagId": self._tag_id(t)}, timeout=30)
                if tr.status_code not in (200, 201, 204, 422):   # 422 = already has the tag
                    return f"error {tr.status_code}: {tr.text[:120]}"
            return "ok"
        except Exception as e:
            return f"error: {str(e)[:120]}"
