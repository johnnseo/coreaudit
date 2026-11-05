"""Keyword visibility from DataForSEO (pay as you go). Fails soft: no keys = section skipped."""
import os
import re

import requests

BASE = "https://api.dataforseo.com/v3"


def _auth():
    u, p = os.getenv("DATAFORSEO_LOGIN"), os.getenv("DATAFORSEO_PASSWORD")
    return (u, p) if u and p else None


def _post(path, payload):
    r = requests.post(f"{BASE}{path}", json=[payload], auth=_auth(), timeout=60)
    r.raise_for_status()
    task = r.json()["tasks"][0]
    if task.get("status_code") != 20000:
        raise RuntimeError(f"{task.get('status_code')}: {task.get('status_message')}")
    return task["result"][0]


def brand_stem(domain):
    label = domain.lower().removeprefix("www.").split(".")[0]
    return re.sub(r"[^a-z0-9]", "", label)


def fetch(domain: str, location_code=2840, language="en", limit=100) -> dict:
    if not _auth():
        return {"ok": False, "skipped": True, "error": "No DataForSEO keys"}
    domain = domain.removeprefix("www.")
    try:
        res = _post("/dataforseo_labs/google/ranked_keywords/live", {
            "target": domain, "location_code": location_code, "language_code": language, "limit": limit,
            "order_by": ["keyword_data.keyword_info.search_volume,desc"]})
        stem = brand_stem(domain)
        items = []
        for it in res.get("items") or []:
            kd = it.get("keyword_data", {})
            serp = it.get("ranked_serp_element", {}).get("serp_item", {})
            kw = kd.get("keyword", "")
            items.append({
                "keyword": kw,
                "volume": (kd.get("keyword_info") or {}).get("search_volume") or 0,
                "difficulty": (kd.get("keyword_properties") or {}).get("keyword_difficulty"),
                "position": serp.get("rank_group"),
                "url": serp.get("url") or serp.get("relative_url") or "",
                "brand": bool(stem) and stem in re.sub(r"[^a-z0-9]", "", kw.lower()),
            })
        out = {"ok": True, "total": res.get("total_count", len(items)), "items": items}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
    try:  # backlinks need a separate DataForSEO subscription; optional
        b = _post("/backlinks/summary/live", {"target": domain, "internal_list_limit": 1})
        out["backlinks"] = {"total": b.get("backlinks"), "referring_domains": b.get("referring_domains"),
                            "rank": b.get("rank")}
    except Exception:
        out["backlinks"] = None
    return out
