"""Audit V2: enter the website, see the C.O.R.E. percentages, give an email to unlock the full report.

The check runs before we have an email, so V2 keeps cost down:
  - the Claude copy-reading step (the only token cost) runs only AFTER someone unlocks;
  - the same site checked again within 7 days reuses the saved result;
  - limits: 3 per company per 30 days, 3 per email per 30 days, a daily cap per network and one for the whole service.
"""
import json
import random
import secrets
import time
from html import escape

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from coreaudit import theme
from coreaudit.models import Finding
from coreaudit.safety import UnsafeURL, normalize_url
from . import limits
from .scorecard import clean_src

NAMES = {"C": "Client", "O": "Offer", "R": "Route", "E": "Engine"}


def teaser(res: dict) -> dict:
    s, fs = res["scores"], res["findings"]
    bad = [f for f in fs if f["status"] in ("fail", "warn") and f.get("source") != "ai"]
    good = [f for f in fs if f["status"] == "pass" and f.get("source") != "ai"]
    mobile = next((x for x in res.get("speed") or [] if x.get("strategy") == "mobile" and x.get("score") is not None), None)
    return {"overall": s["overall"], "fix_first": s["fix_first"],
            "areas": [{"k": c, "name": NAMES[c], "score": s[c]["score"]} for c in "CORE"],
            "to_fix": len(bad), "high": len([f for f in bad if f["status"] == "fail" and f["severity"] == "high"]),
            "strength": good[0]["title"] if good else "", "mobile_speed": mobile["score"] if mobile else None,
            "host": limits.site_domain(res["url"])}


def default_ai_reader(url):
    """Fetch the homepage again and let Claude read the copy. Returns (findings, note)."""
    from coreaudit import judge
    from coreaudit.fetch import fetch
    from coreaudit.parse import parse
    page = fetch(url)
    if page.status != 200 or not page.html:
        return [], "page not readable"
    return judge.run(parse(page.html, page.final_url).text, page.final_url)


def add_routes(app, cfg, db, client_ip, frame_headers, NOINDEX, hooks, ctx):
    pool, runner, turnstile_ok, after_audit, ai_reader = (ctx[k] for k in ("pool", "runner", "turnstile_ok", "after_audit", "ai_reader"))

    @app.get("/get")
    def split(req: Request):
        v = req.cookies.get("core_ab")
        if v not in ("v1", "v2"):
            forced = req.query_params.get("v")
            v = forced if forced in ("v1", "v2") else ("v2" if random.random() < cfg["ab_v2_share"] else "v1")
        src = req.query_params.get("src")
        resp = RedirectResponse(("/v2" if v == "v2" else "/embed") + (f"?src={clean_src(src)}" if src else ""), 302)
        secure = cfg["public_base"].startswith("https")
        resp.set_cookie("core_ab", v, max_age=60 * 86400, httponly=True, secure=secure, samesite="none" if secure else "lax")
        if not req.cookies.get("core_vid"):
            resp.set_cookie("core_vid", secrets.token_urlsafe(9), max_age=60 * 86400, httponly=True, secure=secure,
                            samesite="none" if secure else "lax")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/v2", response_class=HTMLResponse)
    def page(req: Request):
        ts = ""
        if cfg["turnstile_site"]:
            ts = ('<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
                  f'<div class="cf-turnstile" data-sitekey="{cfg["turnstile_site"]}" data-theme="dark"></div>')
        html = (cfg["static"] / "v2.html").read_text()
        html = (html.replace("/*THEME*/", theme.css() + theme.dark_css()).replace("__PRIVACY__", escape(cfg["privacy_url"]))
                .replace("__REVIEW__", escape(cfg["review_url"])).replace("__TURNSTILE__", ts)
                .replace("__DOMAIN_LIMIT__", str(cfg["v2_domain_month"])))
        resp = HTMLResponse(html, headers=frame_headers())
        hooks["seen"](req, resp, "audit-v2")
        return resp

    def limit(code):
        msgs = {
            "domain_limit": ("This website has been checked 3 times this month",
                             "Each company gets 3 free checks a month. If this is your site, book a call and we will go deeper."),
            "email_limit": ("You have used your 3 free reports this month",
                            "Each person gets 3 free reports a month. The next step is a conversation about what to fix first."),
            "ip_limit": ("Too many checks from this network today", "Please try again tomorrow, or book a call and we will do it together."),
            "busy": ("We are very busy right now", "Please try again in a little while, or book a call and we will do it together."),
        }
        t, m = msgs[code]
        return JSONResponse({"limit": code, "title": t, "message": m}, 429)

    @app.post("/api/v2/audits")
    async def start(req: Request):
        try:
            b = await req.json()
        except Exception:
            return JSONResponse({"message": "Bad request"}, 400)
        ip = client_ip(req)
        if b.get("hp"):
            return JSONResponse({"message": "Something went wrong. Please try again."}, 400)
        try:
            url = normalize_url(b.get("url", ""))
        except UnsafeURL as ex:
            return JSONResponse({"message": str(ex)}, 400)
        if not turnstile_ok(b.get("turnstile"), ip):
            return JSONResponse({"message": "Please complete the human check and try again."}, 400)
        domain, iph = limits.site_domain(url), limits.hash_ip(ip, cfg["ip_salt"])
        vid, src = req.cookies.get("core_vid", ""), clean_src(b.get("src"))
        token = secrets.token_urlsafe(24)
        base = dict(token=token, url=url, domain=domain, ip_hash=iph, name="", email="", email_norm="", consent_privacy=0,
                    consent_marketing=0, city=(b.get("city") or "").strip()[:60], vid=vid, variant=src)

        cached = db.cached_result(url)                    # same site in the last 7 days: no new work, no cost
        if cached:
            res = json.loads(cached)
            res["findings"] = [f for f in res["findings"] if f.get("source") != "ai"]
            db.create(**base, status="done", stage="Done", result=json.dumps(res), route=res.get("lead_route"),
                      finished=time.time(), v="cache")
            db.log_event(vid, src, "audit-v2", "complete")
            return JSONResponse({"token": token, "status": "done"})

        if db.count_v2(domain=domain) >= cfg["v2_domain_month"]:
            return limit("domain_limit")
        if db.count_v2(ip_hash=iph, since_hours=24) >= cfg["max_per_ip_day"]:
            return limit("ip_limit")
        if db.count_v2(since_hours=24) >= cfg["max_audits_per_day"]:
            return limit("busy")
        db.create(**base, status="queued", stage="Reading your website", v="v2")
        pool.submit(work, token)
        return JSONResponse({"token": token, "status": "queued"}, 202)

    def work(token):
        row = db.get(token)
        db.update(token, status="running")
        try:
            res = runner(row["url"], city=row["city"], max_pages=cfg["crawl_pages"], use_ai=False,
                         progress=lambda s: db.update(token, stage=s))
            if not res.get("ok"):
                db.update(token, status="failed", error=res.get("error", "")[:200], finished=time.time())
                return
            db.update(token, status="done", result=json.dumps(res), route=res["lead_route"], finished=time.time())
        except Exception as ex:
            db.update(token, status="failed", error=str(ex)[:200], finished=time.time())
            return
        db.log_event(row.get("vid") or "", row.get("variant") or "direct", "audit-v2", "complete")

    @app.get("/api/v2/audits/{token}")
    def status(token: str):
        r = db.get(token)
        if not r or r.get("v") not in ("v2", "cache"):
            raise HTTPException(404)
        out = {"status": r["status"], "stage": r["stage"], "unlocked": bool(r["email"])}
        if r["status"] == "failed":
            out["message"] = "We could not read that website. Check the address, and make sure the site is public."
        elif r["result"]:
            out["teaser"] = teaser(json.loads(r["result"]))
        return JSONResponse(out, headers=NOINDEX)

    @app.post("/api/v2/audits/{token}/unlock")
    async def unlock(token: str, req: Request):
        r = db.get(token)
        if not r or r.get("v") not in ("v2", "cache") or not r["result"]:
            raise HTTPException(404)
        if r["email"]:
            return {"status": r["status"]}
        try:
            b = await req.json()
        except Exception:
            return JSONResponse({"message": "Bad request"}, 400)
        if b.get("hp"):
            return JSONResponse({"message": "Something went wrong. Please try again."}, 400)
        email, name = (b.get("email") or "").strip(), (b.get("name") or "").strip()[:60]
        if not limits.valid_email(email) or not name:
            return JSONResponse({"message": "Please enter a valid email (50 characters max) and your first name."}, 400)
        if not b.get("consent_privacy"):
            return JSONResponse({"message": "Please tick the privacy box so we can send your report."}, 400)
        en = limits.norm_email(email)
        if en not in cfg["admin_emails"] and db.count_audits(email_norm=en, since_hours=720) >= cfg["v2_email_month"]:
            return limit("email_limit")
        db.update(token, name=name, email=email, email_norm=en, consent_privacy=1,
                  consent_marketing=1 if b.get("consent_marketing") else 0, consent_at=time.time(), status="enriching",
                  stage="Reading your copy like a visitor would", v="v2")
        db.log_event(r.get("vid") or "", r.get("variant") or "direct", "audit-v2", "lead")
        pool.submit(enrich, token, client_ip(req))
        return JSONResponse({"status": "enriching"}, 202)

    def enrich(token, ip):
        row = db.get(token)
        res = json.loads(row["result"])
        try:                                                  # the only step that spends tokens
            ai, note = ai_reader(row["url"])
            res["findings"] += [f.to_dict() for f in ai]
            res["ai_judge"] = note
            order = {"fail": 0, "warn": 1, "unknown": 2, "pass": 3}
            sev = {"high": 0, "medium": 1, "low": 2}
            res["findings"].sort(key=lambda f: (order[f["status"]], sev[f["severity"]]))   # scores stay as the teaser showed
        except Exception as ex:
            res["ai_judge"] = f"failed: {str(ex)[:100]}"
        db.update(token, status="done", result=json.dumps(res))
        row = db.get(token)
        after_audit(token, row, res, ip, ["audit-v2"])
