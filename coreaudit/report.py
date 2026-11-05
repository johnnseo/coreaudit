"""Plain, self-contained HTML report (phase 0 preview of the on-screen report)."""
from html import escape

NAMES = {"C": "Client", "O": "Offer", "R": "Route", "E": "Engine"}


def to_html(res: dict) -> str:
    if not res.get("ok"):
        return f"<p>Audit failed: {escape(res.get('error', ''))}</p>"
    s = res["scores"]
    parts = [f"<h1>C.O.R.E. Audit: {escape(res['url'])}</h1><p>Overall {s['overall']}/100. "
             f"Fix first: <b>{NAMES[s['fix_first']]}</b>.</p>"]
    for c in "CORE":
        parts.append(f"<h2>{NAMES[c]} &mdash; {s[c]['score']}/100</h2>")
        for f in res["findings"]:
            if f["area"] != c or f["status"] == "pass":
                continue
            parts.append(f"<div class='f {f['status']}'><b>{escape(f['title'])}</b> <i>({f['severity']})</i>"
                         f"<br>Found: {escape(f['evidence'])}<br>Why: {escape(f['why'])}<br>Fix: {escape(f['fix'])}</div>")
    css = ("body{font:16px/1.5 system-ui;max-width:760px;margin:2rem auto;padding:0 1rem}"
           ".f{border-left:4px solid #e8590c;padding:.5rem .8rem;margin:.6rem 0;background:#f8f9fa}"
           ".warn{border-color:#f59f00}")
    return f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><style>{css}</style>" + "".join(parts)
