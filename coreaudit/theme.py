"""Brand theme (Athan Marketing). Change the values here to re-skin the tool and the report.

Colours and fonts were read from athanmarketing.com: Poppins headings, gold buttons with
near-black text, 15px rounded corners, light background.
"""
THEME = {
    "gold": "#E9B625",       # buttons, bars, highlights
    "gold_deep": "#8A6A00",  # gold used as TEXT on white (the bright gold is too pale to read)
    "ink": "#1C1708",        # headings, dark panels
    "text": "#050505",
    "muted": "#5A5646",
    "card": "#FAF6E8",       # warm tint behind cards
    "line": "#E8E2CC",
    "border": "#333331",     # button outline, same as the site
    "radius": "15px",
}


def css(assets: str = "") -> str:
    """CSS variables + self-hosted Poppins. `assets` is the base URL the font files are served from."""
    t = THEME
    faces = "".join(
        f"@font-face{{font-family:'Poppins';font-style:normal;font-weight:{w};font-display:swap;"
        f"src:url({assets}/static/fonts/poppins-latin-{w}-normal.woff2) format('woff2')}}"
        for w in (600, 700, 800))
    return (faces +
            f":root{{--gold:{t['gold']};--gold-deep:{t['gold_deep']};--ink:{t['ink']};--text:{t['text']};"
            f"--muted:{t['muted']};--card:{t['card']};--line:{t['line']};--border:{t['border']};--r:{t['radius']};"
            "--head:'Poppins',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;"
            "--body:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif}")


DARK = {"bg": "#343432", "card": "#3D3D3A", "line": "#4C4C47", "text": "#FFFFFF", "muted": "#CFCBBB",
        "alert": "#FF6B6B", "orange": "#FF9F43", "good": "#4CC38A"}

# The same reading scale as the audits Athan Marketing sends to clients
SCALE = [(0, 29, "lo", "Critical"), (30, 49, "lo", "Needs important improvements"),
         (50, 69, "mid", "Acceptable, but can improve"), (70, 84, "hi", "Good foundation"), (85, 100, "hi", "Solid and well set up")]


def band(score):
    for lo, hi, cls, label in SCALE:
        if lo <= score <= hi:
            return cls, label
    return "hi", SCALE[-1][3]


def scale_html() -> str:
    dot = {"lo": "&#128308;", "mid": "&#128992;", "hi": "&#128994;"}
    rows = "".join(f"<tr><td>{lo}&ndash;{hi}</td><td>{dot[c]} {l}</td></tr>" for lo, hi, c, l in SCALE)
    return f"<table class=scale><tr><th>Score</th><th>What it means</th></tr>{rows}</table>"


def dark_css() -> str:
    """Dark brand look: the grey from athanmarketing.com, gold headings, red/orange for what needs attention."""
    d = DARK
    return (f":root{{--bg:{d['bg']};--text:{d['text']};--ink:{d['text']};--muted:{d['muted']};--card:{d['card']};--line:{d['line']};"
            f"--gold-deep:{THEME['gold']};--alert:{d['alert']};--alert-text:{d['alert']};--orange:{d['orange']};--good:{d['good']};--r:{THEME['radius']}}}"
            f"body{{background:{d['bg']};color:{d['text']}}}"
            "h2{color:var(--gold);border-bottom:1px solid var(--gold);padding-bottom:.3rem}.cta h2,.bonus h2,.card h2{border:0}"
            ".rh{border-bottom:1px solid var(--gold);padding-bottom:.4rem;margin-bottom:1.4rem;font-size:.9rem;color:var(--muted)}.rh b{color:var(--gold)}"
            ".rf{border-top:1px solid var(--gold);margin-top:2.5rem;padding-top:1rem}.rf img{height:44px;width:auto;display:block}"
            "div.f{background:#3A3A37}div.f.fail{border-color:var(--alert)}div.f.good{border-color:var(--good)}.ev{color:var(--muted)}"
            ".cta{background:#2A2A28;border:1px solid var(--line)}.bonus{background:#2A2A28}"
            ".hero{background:transparent;border:1px solid var(--line);border-bottom:1px solid var(--line)}"
            ".hero.lo{border-color:var(--alert)}.hero.mid{border-color:var(--orange)}.hero.hi{border-color:var(--good)}"
            ".hero.lo .big{color:var(--alert)}.hero.mid .big{color:var(--orange)}.hero.hi .big{color:var(--good)}.lab{font-weight:600;margin-top:.2rem}"
            ".bar i.lo{background:var(--alert)}.bar i.mid{background:var(--orange)}.bar i.hi{background:var(--good)}"
            ".chip.r{background:var(--alert);color:#111}.chip.g{background:#2f9e44}.chip.a{background:var(--orange);color:#111}"
            ".fail .ic{background:var(--alert);color:#111}.good .ic{background:#2f9e44}"
            ".score.r{color:var(--alert)}.score.g{color:var(--good)}.score.a{color:var(--orange)}"
            "table{border:1px solid var(--line)}th{background:var(--gold);color:#050505}td{background:var(--card)}td,th{border-bottom:1px solid var(--line)}"
            "a{color:var(--gold-deep)}.btn,.cta a{color:#050505}.sp small,.small{color:var(--muted)}"
            ".q textarea,.small2 input{background:#fff;color:#050505}")
