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
