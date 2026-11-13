"""The page the 11-minute video lives on, plus the printable checklist."""
import re
import time
from html import escape
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from coreaudit import theme
from . import limits
from .scorecard import CRACKS, clean_src


def add_routes(app, cfg, db, aw, client_ip, NOINDEX, hooks, requests_mod):
    static = cfg["static"]
    hits = {}

    def video_html():
        vid = re.sub(r"[^A-Za-z0-9_-]", "", cfg["video_id"])
        if not vid:
            return '<div class="soon">The video goes here. Set VIDEO_ID in Render to show it.</div>'
        return (f'<iframe src="https://www.youtube-nocookie.com/embed/{vid}?rel=0" title="Find the cracks in your marketing in 11 minutes" '
                'allow="accelerometer; encrypted-media; picture-in-picture; fullscreen" allowfullscreen loading="lazy"></iframe>')

    def tests_html():
        out = []
        for c in CRACKS:
            items = "".join(f'<label class="t"><input type="checkbox"><span>{escape(t)}</span></label>' for t in c["test"])
            out.append(f'<div class="area"><b class="k">{c["k"]}</b><div><h3>{escape(c["name"])}: {escape(c["sub"])}</h3>'
                       f'<p class="why">{escape(c["why"])}</p>{items}</div></div>')
        return "".join(out)

    @app.get("/watch", response_class=HTMLResponse)
    def watch(req: Request):
        html = (static / "watch.html").read_text()
        wl = (f'<p class="quiet">If you would rather fix these with someone next to you, there is a 60-minute workshop: '
              f'<a href="{escape(cfg["workshop_url"])}">Fix Your Marketing in 60 Minutes</a>.</p>') if cfg["workshop_url"] else ""
        html = (html.replace("/*THEME*/", theme.css() + theme.dark_css()).replace("__VIDEO__", video_html()).replace("__TESTS__", tests_html())
                .replace("__PRIVACY__", escape(cfg["privacy_url"])).replace("__WORKSHOP__", wl))
        resp = HTMLResponse(html, headers=NOINDEX)
        hooks["seen"](req, resp, "watch")
        return resp

    @app.get("/checklist", response_class=HTMLResponse)
    def checklist():
        html = (static / "checklist.html").read_text().replace("/*THEME*/", theme.css())
        areas = "".join(
            f'<section><h2><span>{c["k"]}</span> {escape(c["name"])}: {escape(c["sub"])}</h2><p>{escape(c["why"])}</p>'
            + "".join(f'<div class="t"><i></i><div>{escape(t)}</div></div>' for t in c["test"])
            + '<div class="line">What I found:</div><div class="line"></div></section>' for c in CRACKS)
        return HTMLResponse(html.replace("__AREAS__", areas), headers=NOINDEX)

    @app.get("/checklist.pdf")
    def checklist_pdf():
        f = Path(static) / "core-checklist.pdf"
        return FileResponse(f, media_type="application/pdf", filename="CORE-checklist.pdf", headers=NOINDEX)

    @app.post("/api/checklist")
    async def checklist_signup(req: Request):
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
            return JSONResponse({"message": "Please tick the privacy box so we can send the checklist."}, 400)
        ip = client_ip(req)
        iph = limits.hash_ip(ip, cfg["ip_salt"])
        now = time.time()
        recent = [t for t in hits.get(iph, []) if now - t < 3600]
        if len(recent) >= 10:
            return JSONResponse({"message": "Too many requests from this network. Please try again later."}, 429)
        hits[iph] = recent + [now]
        src, vid = clean_src(b.get("src")), req.cookies.get("core_vid", "")
        tags = ["core-checklist"] + (["newsletter-optin"] if b.get("consent_marketing") else [])
        status = aw.add(email, name, tags, {}, None)
        db.add_checklist_lead(created=now, name=name, email=email, email_norm=limits.norm_email(email),
                              consent_marketing=1 if b.get("consent_marketing") else 0, consent_at=now,
                              variant=src, vid=vid, aweber=status)
        db.log_event(vid, src, "watch", "lead")
        return {"ok": True, "url": "/checklist.pdf"}
