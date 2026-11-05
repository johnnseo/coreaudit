"""Client-facing report: plain language, honest about what works and what does not."""
import csv
import io
import os
from html import escape as e
from urllib.parse import urlparse

NAMES = {"C": "Client", "O": "Offer", "R": "Route", "E": "Engine"}
ASKS = {"C": "Is it clear who you help and what problem you solve?",
        "O": "Is what you sell specific, and does Google understand it?",
        "R": "Is it easy for a visitor to take the next step?",
        "E": "Is the technical foundation solid: speed, indexing, tracking?"}
BOOK = os.getenv("REVIEW_URL", "https://calendar.app.google/xkJUcqHrNDSCYwNi8")


def label(score):
    return "Strong" if score >= 85 else "Needs work" if score >= 60 else "Fix this first"


def meta_csv(res) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Page", "Title", "Title length", "Meta description", "Meta length", "H1", "H1 length"])
    for p in res["crawl"]["pages"]:
        h1 = p["h1"][0] if p["h1"] else ""
        w.writerow([p["url"], p["title"], len(p["title"]), p["meta_desc"], len(p["meta_desc"]), h1, len(h1)])
    return buf.getvalue()


def _card(f, good=False):
    cls = "good" if good else f["status"]
    parts = [f"<div class='f {cls}'><b>{e(f['title'])}</b>"]
    if f.get("evidence"):
        parts.append(f"<p class=ev>{'Found' if not good else 'Example'}: {e(f['evidence'])}</p>")
    if not good:
        if f.get("why"):
            parts.append(f"<p><b>Why it matters:</b> {e(f['why'])}</p>")
        if f.get("fix"):
            parts.append(f"<p><b>What to do:</b> {e(f['fix'])}</p>")
    return "".join(parts) + "</div>"


def to_html(res: dict) -> str:
    if not res.get("ok"):
        return f"<p>We could not check this site: {e(res.get('error', ''))}</p>"
    s, fs = res["scores"], res["findings"]
    host = urlparse(res["url"]).hostname
    good = [f for f in fs if f["status"] == "pass"]
    bad = [f for f in fs if f["status"] in ("fail", "warn")]
    top = [f for f in bad][:4]
    h = [f"<h1>Website health check</h1><p class=sub>{e(host)}</p>",
         f"<div class=hero><div class=big>{s['overall']}<small>/100</small></div>"
         f"<div>Start with <b>{NAMES[s['fix_first']]}</b>. {e(ASKS[s['fix_first']])}</div></div>",
         "<div class=grid>"]
    for c in "CORE":
        sc = s[c]["score"]
        h.append(f"<div class=area><b>{NAMES[c]}</b><div class=bar><i style='width:{sc}%'></i></div>"
                 f"<span>{sc}/100 &middot; {label(sc)}</span></div>")
    h.append("</div>")
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
    h.append(f"<div class=cta><h2>Want help fixing this?</h2><p>This check shows what is visible from the outside. "
             f"A strategy session goes deeper: your traffic, your search data and a plan in the right order.</p>"
             f"<a href='{e(BOOK)}'>Book a free review call</a></div>")
    css = ("body{font:16px/1.55 system-ui,sans-serif;max-width:760px;margin:0 auto;padding:1.5rem 16px;color:#1c2330;background:#fff}"
           "h1{margin:0}h2{margin:2rem 0 .5rem}.sub{color:#5b6573;margin:.2rem 0 1rem}"
           ".hero{display:flex;gap:1.2rem;align-items:center;background:#f4f6f9;border-radius:14px;padding:1rem 1.2rem}"
           ".big{font-size:3rem;font-weight:800;line-height:1}.big small{font-size:1rem;color:#5b6573}"
           ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.8rem;margin-top:1rem}"
           ".area{background:#f4f6f9;border-radius:12px;padding:.8rem}.bar{height:8px;background:#dde2ea;border-radius:9px;margin:.4rem 0}"
           ".bar i{display:block;height:100%;background:#e8590c;border-radius:9px}.area span{font-size:.85rem;color:#5b6573}"
           ".f{border-left:4px solid #f59f00;background:#fafbfc;padding:.6rem .9rem;margin:.6rem 0;border-radius:0 10px 10px 0}"
           ".f.fail{border-color:#e03131}.f.good{border-color:#2f9e44}.f p{margin:.3rem 0}.ev{color:#5b6573;font-size:.92rem}"
           "table{width:100%;border-collapse:collapse;font-size:.92rem}td,th{text-align:left;padding:.4rem;border-bottom:1px solid #e3e7ee}"
           ".cta{margin-top:2rem;background:#1c2330;color:#fff;border-radius:14px;padding:1rem 1.4rem}"
           ".cta a{display:inline-block;background:#e8590c;color:#fff;padding:.7rem 1.2rem;border-radius:10px;text-decoration:none;font-weight:700}"
           "@media(prefers-color-scheme:dark){body{background:#12161d;color:#e8ecf2}.hero,.area{background:#1c222c}.f{background:#181d26}"
           ".sub,.ev,.area span,.big small{color:#9aa5b5}td,th{border-color:#2a3240}}")
    return ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Website health check</title><style>{css}</style><body>" + "".join(h) + "</body></html>")
