"""Client-facing report: plain language, honest about what works and what does not."""
import csv
import json
import io
import os
from html import escape as e
from urllib.parse import urlparse

from . import theme
from .pagespeed import rate
from .questions import QUESTIONS

NAMES = {"C": "Client", "O": "Offer", "R": "Route", "E": "Engine"}
ASKS = {"C": "Is it clear who you help and what problem you solve?",
        "O": "Is what you sell specific, and does Google understand it?",
        "R": "Is it easy for a visitor to take the next step?",
        "E": "Is the technical foundation solid: speed, indexing, tracking?"}
BOOK = os.getenv("REVIEW_URL", "https://calendar.app.google/xkJUcqHrNDSCYwNi8")


def label(score):
    return "Strong" if score >= 85 else "Good" if score >= 70 else "Can improve" if score >= 50 else "Fix this first"


HEIGHT_JS = ("<script>(function(){function p(){try{parent.postMessage({type:'core-audit-height',height:"
             "document.documentElement.scrollHeight},'*')}catch(e){}}window.addEventListener('load',p);"
             "if(window.ResizeObserver)new ResizeObserver(p).observe(document.body);})();</script>")


def meta_csv(res) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Page", "Title", "Title length", "Meta description", "Meta length", "H1", "H1 length"])
    for p in res["crawl"]["pages"]:
        h1 = p["h1"][0] if p["h1"] else ""
        w.writerow([p["url"], p["title"], len(p["title"]), p["meta_desc"], len(p["meta_desc"]), h1, len(h1)])
    return buf.getvalue()


CHIP = {"good": ("Good", "g"), "ok": ("Needs work", "a"), "poor": ("Poor", "r")}
METRICS = [("lcp_ms", "Main content appears (LCP)", lambda v: f"{v/1000:.1f} s", "Should be 2.5 s or less"),
           ("cls", "Page stays steady (CLS)", lambda v: f"{v:.2f}", "Should be 0.1 or less"),
           ("tbt_ms", "Responds to taps (blocking time)", lambda v: f"{v:.0f} ms", "Should be 200 ms or less"),
           ("fcp_ms", "First content appears (FCP)", lambda v: f"{v/1000:.1f} s", "Should be 1.8 s or less")]


def _chip(metric, v):
    r = rate(metric, v)
    if not r:
        return ""
    t, c = CHIP[r]
    return f"<span class='chip {c}'>{t}</span>"


def speed_section(res) -> str:
    sp = {s["strategy"]: s for s in res.get("speed", [])}
    if not sp or all(s.get("score") is None for s in sp.values()):
        err = next((s.get("error") for s in sp.values() if s.get("error")), "")
        return ("<h2>Speed and Core Web Vitals</h2><div class='f warn'><b>We could not measure speed this time</b>"
                f"<p class=ev>{e(err or 'Speed test was not run.')}</p><p>Run the check again in a minute.</p></div>")
    cols = []
    for k, name in (("mobile", "Mobile"), ("desktop", "Desktop")):
        s = sp.get(k) or {}
        if s.get("score") is None:
            cols.append(f"<div class=sp><h3>{name}</h3><p class=ev>Not measured: {e(s.get('error', ''))}</p></div>")
            continue
        sc = s["score"]
        c = "g" if sc >= 90 else "a" if sc >= 50 else "r"
        rows = "".join(f"<tr><td>{lab}<br><small>{hint}</small></td><td>{fmt(s[m]) if s.get(m) is not None else '-'}</td>"
                       f"<td>{_chip(m, s.get(m))}</td></tr>" for m, lab, fmt, hint in METRICS)
        cols.append(f"<div class=sp><h3>{name}</h3><div class='score {c}'>{sc}<small>/100</small></div>"
                    f"<table>{rows}</table></div>")
    fld = (sp.get("mobile") or {}).get("field")
    note = ""
    if fld and fld.get("verdict"):
        word = {"FAST": "passing", "AVERAGE": "needs improvement", "SLOW": "failing"}.get(fld["verdict"], fld["verdict"].lower())
        note = (f"<p class=sub>Real Chrome visitors over the last 28 days: Core Web Vitals are <b>{word}</b>.</p>")
    else:
        note = "<p class=sub>Google does not have enough real-visitor data for this site, so these are lab measurements.</p>"
    return ("<h2>Speed and Core Web Vitals</h2><p class=sub>Speed affects how visitors feel on your site, how many act, "
            "and whether you pass Google's Core Web Vitals.</p>" + note + f"<div class=cols>{''.join(cols)}</div>")


def questions_section(res, endpoint="") -> str:
    fix = res["scores"]["fix_first"]
    out = ["<h2>Before you book: tell us what you want</h2><p class=sub>Four quick questions so the call is about your goals.</p>"
           "<form id=goals class=q>"]
    for q in QUESTIONS:
        out.append(f"<fieldset><legend>{e(q['label'])}</legend>")
        if q["type"] == "text":
            out.append(f"<textarea name={q['id']} maxlength=400 rows=3></textarea>")
        else:
            kind = "checkbox" if q["type"] == "multi" else "radio"
            for val, lab in q["options"]:
                chk = " checked" if q["id"] == "weakest" and val == fix else ""
                out.append(f"<label><input type={kind} name={q['id']} value='{e(val)}'{chk}> {e(lab)}</label>")
        out.append("</fieldset>")
    out.append(f"<button type=submit class=btn>Continue</button></form>"
               f"<div id=book hidden><a class=btn href='{e(BOOK)}'>Book a free review call</a></div>"
               "<script>(function(){var f=document.getElementById('goals');f.addEventListener('submit',function(ev){"
               "ev.preventDefault();var a={goals:[],weakest:'',help:'',challenge:''};"
               "new FormData(f).forEach(function(v,k){if(k==='goals')a.goals.push(v);else a[k]=v;});"
               "var ep=" + json.dumps(endpoint) + ";if(ep){try{fetch(ep,{method:'POST',headers:{'Content-Type':'application/json'},"
               "body:JSON.stringify(a)});}catch(e){}}"
               "f.hidden=true;document.getElementById('book').hidden=false;});})();</script>")
    return "".join(out)


def _card(f, good=False):
    cls = "good" if good else f["status"]
    icon = {"good": "&#10003;", "fail": "&#10005;", "warn": "!"}.get(cls, "!")
    parts = [f"<div class='f {cls}'><b><span class=ic>{icon}</span>{e(f['title'])}</b>"]
    if f.get("evidence"):
        parts.append(f"<p class=ev>{'Found' if not good else 'Example'}: {e(f['evidence'])}</p>")
    if not good:
        if f.get("why"):
            parts.append(f"<p><b>Why it matters:</b> {e(f['why'])}</p>")
        if f.get("fix"):
            parts.append(f"<p><b>What to do:</b> {e(f['fix'])}</p>")
    return "".join(parts) + "</div>"


def to_html(res: dict, endpoint: str = "", share_url: str = "", assets: str = "", bonus_url: str = "", dark: bool = False) -> str:
    if not res.get("ok"):
        return f"<p>We could not check this site: {e(res.get('error', ''))}</p>"
    s, fs = res["scores"], res["findings"]
    host = urlparse(res["url"]).hostname
    good = [f for f in fs if f["status"] == "pass"]
    bad = [f for f in fs if f["status"] in ("fail", "warn")]
    top = [f for f in bad][:4]
    h = [f"<h1>Website health check</h1><p class=sub>{e(host)}</p>",
         f"<div class='hero {theme.band(s['overall'])[0]}'><div><div class=big>{s['overall']}<small>/100</small></div><div class=lab>{theme.band(s['overall'])[1]}</div></div>"
         f"<div>Start with <b>{NAMES[s['fix_first']]}</b>. {e(ASKS[s['fix_first']])}</div></div>",
         "<div class=grid>"]
    for c in "CORE":
        sc = s[c]["score"]
        h.append(f"<div class=area><b>{NAMES[c]}</b><div class=bar><i class='{theme.band(sc)[0]}' style='width:{sc}%'></i></div>"
                 f"<span>{sc}/100 &middot; {label(sc)}</span></div>")
    h.append("</div>")
    h.append(f"<p class=chips><span class='chip g'>{len(good)} working</span> "
             f"<span class='chip a'>{len([f for f in bad if f['status']=='warn'])} to improve</span> "
             f"<span class='chip r'>{len([f for f in bad if f['status']=='fail'])} to fix</span></p>")
    if share_url:
        h.append(f"<p class=small2>Your private report link (save it): <input id=lk readonly value='{e(share_url)}'> "
                 "<button type=button onclick=\"var i=document.getElementById('lk');i.select();document.execCommand('copy');this.textContent='Copied'\">Copy</button></p>")
    h.append(speed_section(res))
    if good:
        h.append(f"<h2>What you are doing well</h2>" + "".join(_card(f, True) for f in good[:8]))
    if top:
        h.append("<h2>The cracks to fix first</h2>" + "".join(_card(f) for f in top))
    for c in "CORE":
        rest = [f for f in bad if f["area"] == c and f not in top]
        if rest:
            h.append(f"<h2>{NAMES[c]}: more to improve</h2><p class=sub>{e(ASKS[c])}</p>" + "".join(_card(f) for f in rest))
    kw = res.get("keywords", {})
    if kw.get("ok") and kw.get("items"):
        rows = "".join(f"<tr><td>{e(i['keyword'])}</td><td>{i['position']}</td><td>{i['volume']}</td></tr>"
                       for i in sorted([x for x in kw["items"] if x["position"]], key=lambda x: (x["position"], -x["volume"]))[:10])
        h.append(f"<h2>How people find you on Google</h2><p class=sub>{kw['total']} searches show your site. Your best positions:</p>"
                 f"<table><tr><th>Search</th><th>Position</th><th>Searches / month</th></tr>{rows}</table>")
    pages = res["crawl"]["pages"][:10]
    if pages:
        rows = "".join(f"<tr><td>{e(urlparse(p['url']).path or '/')}</td><td>{e(p['title'][:70]) or '<i>missing</i>'}</td>"
                       f"<td>{e((p['h1'] or [''])[0][:60]) or '<i>missing</i>'}</td></tr>" for p in pages)
        h.append(f"<details><summary>Page titles and headlines we checked ({res['crawl']['pages_crawled']} pages)</summary>"
                 f"<table><tr><th>Page</th><th>Title</th><th>Main headline</th></tr>{rows}</table></details>")
    h.append("<h2>How to read your score</h2>" + theme.scale_html() +
             "<details><summary>How the score is calculated</summary><p>Each of the four areas starts at 100 and loses points for every crack we find, "
             "more for the ones that hurt most. The overall score is the average of the four. It measures how well your website is set up "
             "to be found and to turn visitors into enquiries. It does not measure how good your business is.</p></details>")
    if bonus_url:
        h.append("<div class=bonus><span class=badge>Bonus</span><h2>The C.O.R.E. Scorecard</h2>"
                 "<p>The check above looks at your website from the outside. The scorecard looks at what only you know: "
                 "who you serve, what you sell, how people reach you and what you track. Twelve questions, about 3 minutes, "
                 "and you see which part to fix first.</p>"
                 f"<a class=btn href='{e(bonus_url)}'>Take the scorecard</a></div>")
    h.append("<div class=cta>" + questions_section(res, endpoint) + "<p class=small>This check shows what is visible from the outside. "
             "A strategy session goes deeper: your traffic, your search data and a plan in the right order.</p></div>")
    css = ("body{font:16px/1.55 var(--body);max-width:760px;margin:0 auto;padding:1.5rem 16px;color:var(--text);background:#fff}"
           "h1,h2,h3,.big,.score,.btn,.cta a,.chip,summary{font-family:var(--head)}"
           ".logo{display:block;margin:0 0 1.2rem}.logo img{height:34px;width:auto}"
           "h1{margin:0;color:var(--ink);font-weight:700}h2{margin:2rem 0 .5rem;color:var(--ink);font-weight:600}.sub{color:var(--muted);margin:.2rem 0 1rem}"
           ".hero{display:flex;gap:1.2rem;align-items:center;background:var(--card);border-radius:var(--r);padding:1rem 1.2rem;border-bottom:4px solid var(--gold)}"
           ".big{font-size:3rem;font-weight:800;line-height:1;color:var(--ink)}.big small{font-size:1rem;color:var(--muted);font-weight:600}"
           ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.8rem;margin-top:1rem}"
           ".area{background:var(--card);border-radius:12px;padding:.8rem}.bar{height:8px;background:var(--line);border-radius:9px;margin:.4rem 0}"
           ".bar i{display:block;height:100%;background:var(--gold);border-radius:9px}.bar i.lo{background:#e03131}.bar i.mid{background:#e8890c}.bar i.hi{background:#2f9e44}.area span{font-size:.85rem;color:var(--muted)}"
           ".f{border-left:4px solid var(--gold);background:#fffdf5;padding:.6rem .9rem;margin:.6rem 0;border-radius:0 10px 10px 0}"
           ".f.fail{border-color:#e03131}.f.good{border-color:#2f9e44}.f p{margin:.3rem 0}.ev{color:var(--muted);font-size:.92rem}"
           "table{width:100%;border-collapse:collapse;font-size:.92rem}td,th{text-align:left;padding:.4rem;border-bottom:1px solid var(--line)}"
           "details{background:var(--card);border-radius:12px;padding:.7rem 1rem;margin-top:.7rem}summary{cursor:pointer;font-weight:600}"
           ".bonus{margin-top:2rem;border:2px solid var(--gold);border-radius:var(--r);padding:1rem 1.4rem}.bonus h2{margin:.3rem 0 .5rem}.badge{display:inline-block;background:var(--gold);color:var(--text);font:600 .75rem var(--head);padding:.15rem .6rem;border-radius:99px;text-transform:uppercase;letter-spacing:.05em}"
           ".cta{margin-top:2rem;background:var(--ink);color:#fff;border-radius:var(--r);padding:1rem 1.4rem}"
           ".q fieldset{border:0;padding:0;margin:0 0 1rem}.q legend{font-weight:700;margin-bottom:.4rem}"
           ".q label{display:block;padding:.35rem 0}.q input{accent-color:var(--gold)}.q textarea{width:100%;border-radius:10px;border:0;padding:.6rem;font:inherit;box-sizing:border-box}"
           ".cta .sub{color:#d9d3bd}.small{font-size:.85rem;color:#d9d3bd;margin-top:1rem}button.btn{border:1px solid var(--border);cursor:pointer;font:inherit;font-family:var(--head)}"
           ".btn,.cta a{display:inline-block;background:var(--gold);color:var(--text);padding:.7rem 1.3rem;border-radius:var(--r);border:1px solid var(--border);text-decoration:none;font-weight:600}"
           ".small2{font-size:.9rem;color:#d9d3bd}.small2 input{width:60%;max-width:100%;padding:.3rem;border-radius:8px;border:1px solid #cfc8ad;font:inherit}.small2 button{padding:.3rem .8rem;border-radius:8px;border:0;background:var(--gold);color:var(--text);cursor:pointer}"
           ".chips{margin:1rem 0 0}.chip{display:inline-block;font-size:.8rem;font-weight:600;padding:.15rem .6rem;border-radius:99px;color:#fff}"
           ".chip.g{background:#2f9e44}.chip.a{background:#b45f06}.chip.r{background:#e03131}"
           ".ic{display:inline-block;width:1.4rem;height:1.4rem;line-height:1.4rem;text-align:center;border-radius:50%;color:#fff;margin-right:.5rem;font-size:.8rem;background:#b45f06}"
           ".good .ic{background:#2f9e44}.fail .ic{background:#e03131}"
           ".cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}.sp{background:var(--card);border-radius:var(--r);padding:1rem}"
           ".sp h3{margin:0 0 .4rem;color:var(--ink)}.score{font-size:2.6rem;font-weight:800;line-height:1}.score small{font-size:1rem;opacity:.6}"
           ".score.g{color:#2f9e44}.score.a{color:#b45f06}.score.r{color:#e03131}.sp small{color:var(--muted)}")
    if dark:
        h.insert(0, f"<div class=rh><b>C.O.R.E. WEBSITE CHECK</b> | {e(host)}</div>")
        h.append(f"<div class=rf><a href='https://athanmarketing.com' target=_blank rel=noopener>"
                 f"<img src='{assets}/static/athan-logo-dark.png' alt='Athan Marketing'></a></div>")
    else:
        h.insert(0, "<a class=logo href='https://athanmarketing.com' target=_blank rel=noopener>"
                    "<img src='https://athanmarketing.com/wp-content/uploads/2025/01/cropped-ATHAN-180x60.webp' alt='Athan Marketing'></a>")
    return ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Website health check</title><meta name=robots content=noindex><link rel=icon href='{assets}/static/favicon-32.png' type='image/png'><link rel=apple-touch-icon href='{assets}/static/apple-touch-icon.png'><style>{theme.css(assets)}{css}{theme.dark_css() if dark else ''}</style><body>" + "".join(h) +
            HEIGHT_JS + "</body></html>")
