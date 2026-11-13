"""C.O.R.E. Audit web service: embeddable page, email gate, 2-try limits, reports, AWeber."""
import csv
import io
import json
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from ipaddress import ip_address
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

from coreaudit import audit as audit_mod
from coreaudit.models import Finding
from coreaudit import theme
from coreaudit.report import to_html
from coreaudit.safety import UnsafeURL, normalize_url
from coreaudit.scoring import route_lead, score

from . import config as config_mod
from . import limits
from . import scorecard as scorecard_mod
from . import watch as watch_mod
from . import v2 as v2_mod
from .aweber import AWeber
from .db import DB

STATIC = Path(__file__).parent / "static"
NOINDEX = {"X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"}


def create_app(cfg=None, run_audit=None, ai_reader=None):
    cfg = cfg or config_mod.get()
    db = DB(cfg["db_path"])
    aw = AWeber(cfg, db)
    pool = ThreadPoolExecutor(max_workers=cfg["max_concurrent"])
    runner = run_audit or audit_mod.run_audit
    cfg["static"] = STATIC
    hooks = {}
    app = FastAPI(title="C.O.R.E. Audit", docs_url=None, redoc_url=None, openapi_url=None)

    def frame_headers():
        anc = " ".join(["'self'"] + cfg["site_origins"])
        return {**NOINDEX, "Content-Security-Policy": f"frame-ancestors {anc}"}

    def client_ip(req: Request) -> str:
        fwd = req.headers.get("x-forwarded-for", "")
        return (fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else "")) or "0.0.0.0"

    def turnstile_ok(token, ip):
        if not cfg["turnstile_secret"]:
            return True
        try:
            r = requests.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                              data={"secret": cfg["turnstile_secret"], "response": token or "", "remoteip": ip}, timeout=10)
            return bool(r.json().get("success"))
        except Exception:
            return False

    @app.get("/healthz")
    def health():
        return {"ok": True}

    @app.get("/", response_class=HTMLResponse)
    @app.get("/embed", response_class=HTMLResponse)
    def embed(req: Request):
        ts = ""
        if cfg["turnstile_site"]:
            ts = ('<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
                  f'<div class="cf-turnstile" data-sitekey="{cfg["turnstile_site"]}"></div>')
        html = (STATIC / "embed.html").read_text()
        html = html.replace("__PRIVACY__", cfg["privacy_url"]).replace("__REVIEW__", cfg["review_url"]).replace("__TURNSTILE__", ts)
        html = html.replace("/*THEME*/", theme.css() + theme.dark_css())
        resp = HTMLResponse(html, headers=frame_headers())
        hooks["seen"](req, resp, "audit")
        return resp

    app.mount("/static/fonts", StaticFiles(directory=STATIC / "fonts"), name="fonts")

    @app.get("/static/athan-logo-dark.png")
    def logo():
        return Response((STATIC / "athan-logo-dark.png").read_bytes(), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/widget.js")
    def widget():
        return Response((STATIC / "widget.js").read_text(), media_type="application/javascript",
                        headers={"Cache-Control": "public, max-age=300"})

    # ---------------- start an audit ----------------
    @app.post("/api/audits")
    async def start(req: Request):
        try:
            b = await req.json()
        except Exception:
            return JSONResponse({"message": "Bad request"}, 400)
        ip = client_ip(req)
        if b.get("hp"):                                   # honeypot: bots fill hidden fields
            return JSONResponse({"message": "Something went wrong. Please try again."}, 400)
        email, name = (b.get("email") or "").strip(), (b.get("name") or "").strip()[:60]
        if not limits.valid_email(email) or not name:
            return JSONResponse({"message": "Please enter a valid email (50 characters max) and your first name."}, 400)
        if not b.get("consent_privacy"):
            return JSONResponse({"message": "Please tick the privacy box so we can send your report."}, 400)
        try:
            url = normalize_url(b.get("url", ""))
        except UnsafeURL as ex:
            return JSONResponse({"message": str(ex)}, 400)
        if not turnstile_ok(b.get("turnstile"), ip):
            return JSONResponse({"message": "Please complete the human check and try again."}, 400)

        en, domain, iph = limits.norm_email(email), limits.site_domain(url), limits.hash_ip(ip, cfg["ip_salt"])
        prior = db.recent_same(en, domain)                 # same person, same site: show the report again, free
        if prior:
            return {"token": prior, "status": "done"}
        ok, code = limits.check(db, cfg, en, domain, iph)
        if not ok:
            msgs = {
                "email_limit": ("You have used your 2 free checks", "Each person gets 2 free checks. The next step is a conversation about what to fix first."),
                "domain_limit": ("This website has already been checked twice", "Each company gets 2 free checks. If this is your site, book a call and we will go deeper."),
                "ip_limit": ("Too many checks from this network today", "Please try again tomorrow, or book a call and we will do it together."),
            }
            t, m = msgs[code]
            return JSONResponse({"limit": code, "title": t, "message": m}, 429)

        token = secrets.token_urlsafe(24)
        db.create(token=token, status="queued", stage="Reading your website", name=name, email=email, email_norm=en,
                  url=url, domain=domain, city=(b.get("city") or "").strip()[:60], ip_hash=iph,
                  consent_privacy=1, consent_marketing=1 if b.get("consent_marketing") else 0, consent_at=time.time(),
                  vid=req.cookies.get("core_vid", ""), variant=scorecard_mod.clean_src(b.get("src")))
        db.log_event(req.cookies.get("core_vid", ""), scorecard_mod.clean_src(b.get("src")), "audit", "lead")
        pool.submit(work, token, ip)
        return JSONResponse({"token": token, "status": "queued"}, 202)

    def work(token, ip):
        row = db.get(token)
        db.update(token, status="running")
        try:
            res = runner(row["url"], city=row["city"], max_pages=cfg["crawl_pages"],
                         progress=lambda s: db.update(token, stage=s))
            if not res.get("ok"):
                db.update(token, status="failed", error=res.get("error", "")[:200], finished=time.time())
                return
            db.update(token, status="done", result=json.dumps(res), route=res["lead_route"], finished=time.time())
        except Exception as ex:
            db.update(token, status="failed", error=str(ex)[:200], finished=time.time())
            return
        db.log_event(row.get("vid") or "", row.get("variant") or "direct", "audit", "complete")
        after_audit(token, row, res, ip)

    def after_audit(token, row, res, ip, extra_tags=()):
        s = res["scores"]
        report_url = f'{cfg["public_base"]}/r/{token}'
        tags = ["core-audit", f"fix-first-{s['fix_first']}", f"route-{res['lead_route']}", *extra_tags]
        if row["consent_marketing"]:
            tags.append("newsletter-optin")
        try:
            public = not (ip_address(ip).is_private or ip_address(ip).is_loopback)
        except ValueError:
            public = False
        status = aw.add(row["email"], row["name"], tags, {
            "site": row["domain"], "score": str(s["overall"]), "fix_first": {"C": "Client", "O": "Offer", "R": "Route", "E": "Engine"}[s["fix_first"]],
            "report_url": report_url}, ip if public else None)
        db.update(token, aweber=status)
        if cfg["alert_webhook"]:
            try:
                requests.post(cfg["alert_webhook"], json={"text": (
                    f"New C.O.R.E. check: {row['name']} <{row['email']}> / {row['domain']} / score {s['overall']} "
                    f"/ fix first {s['fix_first']} / route {res['lead_route']}\n{report_url}")}, timeout=10)
            except Exception:
                pass

    @app.get("/api/audits/{token}")
    def status(token: str):
        r = db.get(token)
        if not r:
            raise HTTPException(404)
        out = {"status": r["status"], "stage": r["stage"]}
        if r["status"] == "failed":
            out["message"] = "We could not read that website. Check the address, and make sure the site is public."
        return JSONResponse(out, headers=NOINDEX)

    # ---------------- report ----------------
    @app.get("/r/{token}", response_class=HTMLResponse)
    def report(token: str):
        r = db.get(token)
        if r and r.get("v") in ("v2", "cache") and r["status"] != "done":
            return RedirectResponse(f"/v2?t={token}", 302)      # not unlocked yet, or still being written
        if not r or r["status"] != "done" or (r.get("v") in ("v2", "cache") and not r["email"]):
            if r and r.get("v") in ("v2", "cache"):
                return RedirectResponse(f"/v2?t={token}", 302)
            raise HTTPException(404)
        res = json.loads(r["result"])
        html = to_html(res, endpoint=f"/api/reports/{token}/answers", share_url=f'{cfg["public_base"]}/r/{token}', assets=cfg["public_base"],
                       bonus_url=f'{cfg["public_base"]}/scorecard?from={token}',
                       dark=True)
        return HTMLResponse(html, headers=frame_headers())

    @app.post("/api/reports/{token}/answers")
    async def answers(token: str, req: Request):
        r = db.get(token)
        if not r or r["status"] != "done":
            raise HTTPException(404)
        b = await req.json()
        a = {"goals": [str(x)[:20] for x in (b.get("goals") or [])][:6], "weakest": str(b.get("weakest", ""))[:10],
             "help": str(b.get("help", ""))[:10], "challenge": str(b.get("challenge", ""))[:400]}
        res = json.loads(r["result"])
        findings = [Finding(**{k: v for k, v in f.items() if k in Finding.__dataclass_fields__}) for f in res["findings"]]
        route = route_lead(res["scores"], findings, a)
        db.update(token, answers=json.dumps(a), route=route)
        if aw.configured:
            aw.add(r["email"], r["name"], [f"route-{route}", f"wants-{a['help'] or 'unsure'}"] + [f"goal-{g}" for g in a["goals"]],
                   {"site": r["domain"], "score": str(res["scores"]["overall"]),
                    "fix_first": {"C": "Client", "O": "Offer", "R": "Route", "E": "Engine"}[res["scores"]["fix_first"]],
                    "report_url": f'{cfg["public_base"]}/r/{token}'})
        if cfg["alert_webhook"]:
            try:
                requests.post(cfg["alert_webhook"], json={"text": (
                    f"Answers from {r['name']} ({r['domain']}): goals {a['goals']}, weakest {a['weakest']}, help {a['help']}, "
                    f"route {route}. {a['challenge']}")}, timeout=10)
            except Exception:
                pass
        return {"ok": True}

    # ---------------- admin (needs ADMIN_KEY) ----------------
    def admin(req: Request):
        key = req.query_params.get("key", "")
        if not cfg["admin_key"] or not secrets.compare_digest(key, cfg["admin_key"]):
            raise HTTPException(404)

    @app.get("/admin/leads.csv")
    def leads_csv(req: Request):
        admin(req)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["date", "name", "email", "site", "city", "status", "route", "newsletter_optin", "aweber", "answers", "score", "magnet", "source"])
        for r in db.leads():
            sc = ""
            if r["result"]:
                sc = json.loads(r["result"])["scores"]["overall"]
            w.writerow([time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["created"])), r["name"], r["email"], r["url"], r["city"],
                        r["status"], r["route"], r["consent_marketing"], r["aweber"], r["answers"], sc, "audit-v2" if r.get("v") in ("v2", "cache") else "audit", r.get("variant") or ""])
        for r in db.checklist_leads():
            w.writerow([time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["created"])), r["name"], r["email"], "", "", "signed up", "",
                        r["consent_marketing"], r["aweber"], "", "", "checklist", r["variant"] or ""])
        for r in db.scorecards():
            sc = json.loads(r["scores"])["total"] if r["scores"] else ""
            w.writerow([time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["created"])), r["name"], r["email"], "", "",
                        "done" if r["done"] else "started", "", r["consent_marketing"], r["aweber"], "", sc, "scorecard", r.get("variant") or ""])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")

    @app.get("/admin/aweber/connect")
    def aw_connect(req: Request):
        admin(req)
        return RedirectResponse(aw.connect_url())

    @app.get("/admin/aweber/callback")
    def aw_callback(req: Request):
        if not aw.state_ok(req.query_params.get("state", "")):
            raise HTTPException(400, "Bad state")
        aw.exchange_code(req.query_params.get("code", ""))
        return HTMLResponse("<p>AWeber connected. Open <code>/admin/aweber/lists?key=YOUR_ADMIN_KEY</code> "
                            "to see your account id and list ids.</p>")

    @app.get("/admin/aweber/lists")
    def aw_lists(req: Request):
        admin(req)
        return aw.lists()

    scorecard_mod.add_routes(app, cfg, db, aw, client_ip, frame_headers, NOINDEX, requests, hooks)
    v2_mod.add_routes(app, cfg, db, client_ip, frame_headers, NOINDEX, hooks,
                      {"pool": pool, "runner": runner, "turnstile_ok": turnstile_ok, "after_audit": after_audit,
                       "ai_reader": ai_reader or v2_mod.default_ai_reader})
    watch_mod.add_routes(app, cfg, db, aw, client_ip, NOINDEX, hooks, requests)
    return app


try:                                    # `uvicorn server.app:app`
    app = create_app()
except Exception:                       # keeps imports safe in tooling/tests
    app = None
