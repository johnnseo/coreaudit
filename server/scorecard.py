"""The C.O.R.E. Scorecard (12-question self check) and the A/B split between it and the website check."""
import json
import re
import secrets
import time
from html import escape

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from coreaudit import theme
from . import limits

CRACKS = [
    {"k": "C", "name": "Client", "sub": "Who you serve",
     "why": "People cannot tell who your marketing is for, so they assume it is not for them.",
     "test": ["Show your homepage to a stranger for 5 seconds. Ask who it is for, what you do and what to do next.",
              "Finish this sentence without the word \"and\": I help ___ who are stuck on ___ get ___."]},
    {"k": "O", "name": "Offer", "sub": "What you sell",
     "why": "A long list of services makes the choice hard, and a hard choice becomes no choice.",
     "test": ["Count the services on your homepage. More than three means you are not leading with one.",
              "Pick the one that is easiest for a new customer to say yes to. That is your lead offer."]},
    {"k": "R", "name": "Route", "sub": "How they reach you",
     "why": "Interest leaks out between the first click and the booking.",
     "test": ["Walk your own path as a stranger: ad or post, page, form, thank-you page.",
              "Write down every point where someone must think, scroll, or fill in more than they have to."]},
    {"k": "E", "name": "Engine", "sub": "What you track and repeat",
     "why": "Without tracking and follow-up you are guessing, and you cannot fix what you cannot see.",
     "test": ["Write down where your last five clients came from. If you hesitate, you have found the crack.",
              "Add one question to every form and call: how did you hear about us?"]},
]
Q = [
    [0, "A stranger can tell who my marketing is for within 5 seconds.", "Read your homepage headline as if you had never seen it."],
    [0, "I can describe my ideal customer by their situation, not just their age or job.", "For example: \"owners who get visits but no bookings\"."],
    [0, "My ads, posts and website all talk to the same person.", "Mixed messages usually mean no one was chosen."],
    [1, "I can explain what I sell in one sentence.", "Without a list and without jargon."],
    [1, "I lead with one main offer, not a menu of services.", "The rest can follow after the first sale."],
    [1, "Customers can see what they get, and why now.", "A result, a timeframe, and a reason to act."],
    [2, "My website or profile has one clear next step.", "One main button, not five."],
    [2, "Someone can book or contact me in under two minutes.", "Time it yourself on a phone."],
    [2, "People know what happens after they submit a form or book.", "A thank-you message that says what comes next."],
    [3, "I know where my last five clients came from.", "Not a guess. You can name the source for each."],
    [3, "Someone who shows interest hears from me again within a day.", "A reply, a reminder, a last check."],
    [3, "I look at my numbers on a regular schedule and change one thing.", "Weekly or monthly, not whenever you remember."],
]


def score(answers):
    s, m = [0] * 4, [0] * 4
    for (area, _, _), a in zip(Q, answers):
        s[area] += a
        m[area] += 2
    low = sorted(range(4), key=lambda i: (s[i] / m[i], i))[0]
    return {"scores": s, "max": m, "total": sum(s), "max_total": sum(m), "fix_first": low}


def band(total, mx):
    p = total / mx
    return "high" if p >= 0.8 else "mid" if p >= 0.5 else "low"


def clean_src(v):
    v = re.sub(r"[^a-z0-9_-]", "", str(v or "").lower())[:30]
    return v or "direct"


def add_routes(app, cfg, db, aw, client_ip, frame_headers, NOINDEX, requests_mod, hooks):
    secure = cfg["public_base"].startswith("https")

    def cookie(resp, k, v):
        resp.set_cookie(k, v, max_age=60 * 86400, httponly=True, secure=secure, samesite="none" if secure else "lax")

    def who(req):
        return req.cookies.get("core_vid", "")

    src_of = clean_src

    def seen(req, resp, magnet):
        vid = who(req)
        if not vid:
            vid = secrets.token_urlsafe(9)
            cookie(resp, "core_vid", vid)
        db.log_event(vid, src_of(req.query_params.get("src") or ("audit-bonus" if req.query_params.get("from") else "")), magnet, "view")

    hooks["seen"] = seen

    # ---------- pages ----------
    def page(token=""):
        html = (cfg["static"] / "scorecard.html").read_text()
        data = {"cracks": CRACKS, "q": Q, "review": cfg["review_url"], "token": token}
        return (html.replace("/*THEME*/", theme.css()).replace("__PRIVACY__", escape(cfg["privacy_url"]))
                .replace("__DATA__", json.dumps(data).replace("</", "<\\/")))

    @app.get("/scorecard", response_class=HTMLResponse)
    def scorecard_page(req: Request):
        resp = HTMLResponse(page(), headers=frame_headers())
        seen(req, resp, "scorecard")
        return resp

    @app.get("/s/{token}", response_class=HTMLResponse)
    def scorecard_result_page(token: str):
        if not db.get_scorecard(token):
            raise HTTPException(404)
        return HTMLResponse(page(token), headers=frame_headers())

    # ---------- API ----------
    @app.post("/api/scorecard")
    async def sc_start(req: Request):
        try:
            b = await req.json()
        except Exception:
            return JSONResponse({"message": "Bad request"}, 400)
        if b.get("hp"):
            return JSONResponse({"message": "Something went wrong. Please try again."}, 400)
        src, bonus = src_of(b.get("src")), None
        if b.get("from"):                                   # bonus from the website check: reuse what they already gave us
            bonus = db.get(str(b["from"]))
            if not bonus or bonus["status"] != "done":
                return JSONResponse({"message": "That report link is not valid."}, 400)
            b = {"name": bonus["name"], "email": bonus["email"], "consent_privacy": bonus["consent_privacy"],
                 "consent_marketing": bonus["consent_marketing"], "hp": ""}
            src = "audit-bonus"
        email, name = (b.get("email") or "").strip(), (b.get("name") or "").strip()[:60]
        if not limits.valid_email(email) or not name:
            return JSONResponse({"message": "Please enter a valid email (50 characters max) and your first name."}, 400)
        if not b.get("consent_privacy"):
            return JSONResponse({"message": "Please tick the privacy box so we can send your results."}, 400)
        ip = client_ip(req)
        iph = limits.hash_ip(ip, cfg["ip_salt"])
        if db.count_scorecards(ip_hash=iph, since_hours=24) >= 10:
            return JSONResponse({"message": "Too many from this network today. Please try again tomorrow."}, 429)
        en = limits.norm_email(email)
        vid, variant = who(req), src
        prior = db.scorecard_for_email(en)                 # same person again: take them to their result
        if prior and prior["done"]:
            return {"token": prior["token"], "done": True}
        token = prior["token"] if prior else secrets.token_urlsafe(24)
        if not prior:
            db.create_scorecard(token=token, created=time.time(), name=name, email=email, email_norm=en, ip_hash=iph,
                                consent_privacy=1, consent_marketing=1 if b.get("consent_marketing") else 0,
                                consent_at=time.time(), vid=vid, variant=variant)
            db.log_event(vid, variant, "scorecard", "lead")
        return {"token": token, "done": False}

    @app.post("/api/scorecard/{token}/answers")
    async def sc_answers(token: str, req: Request):
        row = db.get_scorecard(token)
        if not row:
            raise HTTPException(404)
        if row["done"]:
            return JSONResponse(json.loads(row["scores"]), headers=NOINDEX)
        b = await req.json()
        a = b.get("answers")
        if not (isinstance(a, list) and len(a) == len(Q) and all(isinstance(x, int) and 0 <= x <= 2 for x in a)):
            return JSONResponse({"message": "Please answer all twelve questions."}, 400)
        res = score(a)
        names = [c["name"] for c in CRACKS]
        report_url = f'{cfg["public_base"]}/s/{token}'
        tags = ["core-scorecard", f"fix-first-{CRACKS[res['fix_first']]['k']}", f"scorecard-{band(res['total'], res['max_total'])}"]
        if row["consent_marketing"]:
            tags.append("newsletter-optin")
        status = aw.add(row["email"], row["name"], tags, {
            "score": f"{res['total']}/{res['max_total']}", "fix_first": names[res["fix_first"]], "report_url": report_url})
        db.finish_scorecard(token, json.dumps(res), json.dumps(a), status)
        db.log_event(row["vid"] or "", row["variant"] or "direct", "scorecard", "complete")
        if cfg["alert_webhook"]:
            try:
                requests_mod.post(cfg["alert_webhook"], json={"text": (
                    f"New C.O.R.E. scorecard: {row['name']} <{row['email']}> / {res['total']}/{res['max_total']} "
                    f"/ fix first {names[res['fix_first']]}\n{report_url}")}, timeout=10)
            except Exception:
                pass
        return JSONResponse(res, headers=NOINDEX)

    @app.get("/api/scorecard/{token}")
    def sc_get(token: str):
        row = db.get_scorecard(token)
        if not row:
            raise HTTPException(404)
        return JSONResponse({"done": bool(row["done"]), "result": json.loads(row["scores"]) if row["done"] else None},
                            headers=NOINDEX)

    # ---------- admin: how the two magnets compare ----------
    @app.get("/admin/ab")
    def ab_report(req: Request):
        key = req.query_params.get("key", "")
        import secrets as _s
        if not cfg["admin_key"] or not _s.compare_digest(key, cfg["admin_key"]):
            raise HTTPException(404)
        rows = db.ab_summary()
        pct = lambda a, b: f"{round(100 * a / b)}%" if b else "-"
        per100 = lambda a, b: f"{round(100 * a / b, 1)}" if b else "-"
        tr = "".join(
            f"<tr><td>{escape(r['variant'])}</td><td>{escape(r['magnet'])}</td><td>{r['views']}</td><td>{r['leads']}</td>"
            f"<td>{r['done']}</td><td>{per100(r['leads'], r['views'])}</td></tr>" for r in rows)
        tot = "".join(
            f"<tr><td><b>{escape(r['magnet'])}</b></td><td>{r['views']}</td><td>{r['leads']}</td><td>{r['done']}</td>"
            f"<td><b>{per100(r['leads'], r['views'])}</b></td></tr>" for r in db.ab_totals())
        html = ("<!doctype html><meta name=robots content=noindex><meta charset=utf-8><title>Lead magnet test</title>"
                "<style>body{font:16px system-ui;max-width:820px;margin:2rem auto;padding:0 1rem}td,th{padding:.5rem;border-bottom:1px solid #ddd;text-align:left}</style>"
                "<h1>Lead magnet test</h1><h2>All sources together</h2>"
                "<table><tr><th>Page</th><th>Visitors</th><th>Gave email</th><th>Finished a check</th><th>Emails per 100 visitors</th></tr>" + tot + "</table>"
                "<p><b>audit</b> is version 1 (email first). <b>audit-v2</b> is version 2 (score first, email to unlock). "
                "In version 2, &quot;finished a check&quot; happens before the email.</p><h2>By source</h2><p>Variant is the group a visitor was put in by <code>/get</code>. "
                "<b>direct</b> means they opened that page without going through the split.</p>"
                "<table><tr><th>Variant</th><th>Page</th><th>Visitors</th><th>Gave email</th><th>Finished</th>"
                "<th>Emails per 100 visitors</th></tr>" + tr + "</table>"
                "<p>Wait for roughly 100 visitors in each group before picking a winner. Fewer than that is mostly luck.</p>")
        return HTMLResponse(html, headers=NOINDEX)
