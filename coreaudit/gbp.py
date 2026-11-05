"""Google Business Profile check via DataForSEO Business Data (pay as you go, about a cent per lookup).

We only call it for businesses that look local. We confirm the profile belongs to the site by matching the
website domain, so we never show someone else's reviews.
"""
import os
import re
from urllib.parse import urlparse

import requests

from .models import Finding


def _digits(s):
    return re.sub(r"\D", "", s or "")[-10:]


def lookup(name: str, city: str, domain: str) -> dict:
    u, p = os.getenv("DATAFORSEO_LOGIN"), os.getenv("DATAFORSEO_PASSWORD")
    if not (u and p):
        return {"ok": False, "error": "No DataForSEO keys"}
    if not name:
        return {"ok": False, "error": "Business name not found on the site"}
    try:
        r = requests.post("https://api.dataforseo.com/v3/business_data/google/my_business_info/live",
                          json=[{"keyword": f"{name} {city}".strip(), "location_name": "United States",
                                 "language_name": "English"}], auth=(u, p), timeout=60)
        r.raise_for_status()
        task = r.json()["tasks"][0]
        if task.get("status_code") != 20000:
            return {"ok": False, "error": f"{task.get('status_code')}: {task.get('status_message')}"}
        items = ((task.get("result") or [{}])[0].get("items")) or []
        host = domain.removeprefix("www.")
        for it in items:
            site = (it.get("domain") or urlparse(it.get("url") or "").hostname or "").removeprefix("www.")
            if site and host and (site == host or host.endswith(site) or site.endswith(host)):
                rt = it.get("rating") or {}
                return {"ok": True, "found": True, "name": it.get("title"), "rating": rt.get("value"),
                        "reviews": rt.get("votes_count") or 0, "claimed": it.get("is_claimed"),
                        "category": it.get("category"), "phone": it.get("phone"), "address": it.get("address"),
                        "hours": bool(it.get("work_time") or it.get("work_hours")),
                        "photos": it.get("total_photos"), "has_description": bool(it.get("description"))}
        return {"ok": True, "found": False}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def findings(g: dict, site_phone: str) -> list:
    out = []
    if not g.get("ok"):
        return out

    def F(**k):
        return Finding(area="E", source="gbp", **k)
    if not g["found"]:
        return [F(id="E-gbp-none", title="We could not find a Google Business Profile for this site", status="fail",
                  severity="high", evidence="No profile matching your website turned up in a Google Maps lookup.",
                  why="Local customers find businesses through Google Maps first. No profile means missing the map pack.",
                  fix="Create and verify a Google Business Profile, with the same name, address, phone and website as your site.")]
    out.append(F(id="ok-gbp", title="You have a Google Business Profile", status="pass",
                 evidence=f'{g.get("name")}' + (f' ({g.get("category")})' if g.get("category") else "")))
    n, rt = g["reviews"], g.get("rating")
    if n < 10:
        out.append(F(id="E-gbp-reviews", title="Very few Google reviews", status="warn", severity="medium",
                     evidence=f"{n} review(s)" + (f", rated {rt}" if rt else ""),
                     why="Reviews are one of the strongest trust and local ranking signals.",
                     fix="Ask every happy customer for a review with a direct link, and reply to each one."))
    else:
        out.append(F(id="ok-gbp-reviews", title=f"Good review base: {n} Google reviews", status="pass",
                     evidence=f"Rated {rt}"))
    if rt and rt < 4.2 and n >= 5:
        out.append(F(id="E-gbp-rating", title="Average rating is below 4.2", status="warn", severity="medium",
                     evidence=f"Rated {rt} from {n} reviews", why="Many people skip anything under 4 stars.",
                     fix="Reply to the low reviews and keep collecting new ones."))
    if g.get("claimed") is False:
        out.append(F(id="E-gbp-claimed", title="The profile is not claimed", status="fail", severity="high",
                     evidence="Google lists the profile as unclaimed.", why="Anyone can suggest edits and you cannot manage it.",
                     fix="Claim and verify the profile."))
    if g.get("phone") and site_phone and _digits(g["phone"]) != _digits(site_phone):
        out.append(F(id="E-gbp-nap", title="Phone on Google differs from the phone on your website", status="warn",
                     severity="medium", evidence=f"Google: {g['phone']}; website: {site_phone}",
                     why="Inconsistent name, address and phone weakens local rankings.",
                     fix="Use one phone number everywhere."))
    elif g.get("phone") and site_phone:
        out.append(F(id="ok-gbp-nap", title="Phone matches between Google and your website", status="pass", evidence=g["phone"]))
    if g.get("hours") is False:
        out.append(F(id="E-gbp-hours", title="No opening hours on the profile", status="warn", severity="low",
                     evidence="Hours missing.", why="Searchers filter by who is open now.", fix="Add your hours."))
    if g.get("photos") is not None and g["photos"] < 5:
        out.append(F(id="E-gbp-photos", title="Few photos on the profile", status="warn", severity="low",
                     evidence=f"{g['photos']} photo(s)", why="Profiles with photos get more calls and visits.",
                     fix="Add real photos of the team, work and location."))
    return out
