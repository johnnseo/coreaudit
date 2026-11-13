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
        "alert": "#FF5A36", "alert_text": "#FF8A6B", "good": "#4CC38A"}


def dark_css() -> str:
    """V2 look: dark grey page, white and yellow text, red/orange for what needs attention."""
    d = DARK
    return (f":root{{--bg:{d['bg']};--text:{d['text']};--ink:{d['text']};--muted:{d['muted']};--card:{d['card']};--line:{d['line']};"
            f"--gold-deep:{THEME['gold']};--alert:{d['alert']};--alert-text:{d['alert_text']};--good:{d['good']};--r:{THEME['radius']}}}"
            f"body{{background:{d['bg']};color:{d['text']}}}"
            ".logo{display:inline-block;background:#fff;border-radius:10px;padding:6px 12px}"
            ".f{background:#3A3A37}.f.fail{border-color:var(--alert)}.f.good{border-color:var(--good)}.ev{color:var(--muted)}"
            ".cta{background:#262624;border:1px solid var(--line)}.bonus{background:#3A3A37}"
            ".chip.r{background:var(--alert)}.chip.g{background:#2f9e44}.fail .ic{background:var(--alert)}.good .ic{background:#2f9e44}"
            ".score.r{color:var(--alert-text)}.score.g{color:var(--good)}.score.a{color:var(--gold-deep)}"
            ".bar i.lo{background:var(--alert)}td,th{border-bottom-color:var(--line)}a{color:var(--gold-deep)}.btn,.cta a{color:#050505}.sp small,.small{color:var(--muted)}"
            ".q textarea,.small2 input{background:#fff;color:#050505}")
