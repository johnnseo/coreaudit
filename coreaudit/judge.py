"""AI judge. Claude reads the page copy against a rubric. Code then verifies every quote."""
import json
import os
import re

from .models import Finding

MODEL = os.getenv("COREAUDIT_MODEL", "claude-sonnet-5-5")

RUBRIC = """You audit a small business website for a marketing consultant. Judge ONLY the text provided.
Score by C.O.R.E.:
C (Client): Is it clear who the business serves and what problem they have? Is the copy about the customer or about the company?
O (Offer): Is the main service/offer specific, with a clear result? Any proof (reviews, numbers, case studies)?
R (Route): Is the next step obvious and low-friction?
Return JSON only: {"findings":[{"area":"C|O|R","title":"short","status":"fail|warn|pass",
"severity":"high|medium|low","quote":"EXACT words copied from the text, max 25 words","why":"one sentence","fix":"one sentence"}]}
Rules: every finding MUST include a verbatim quote from the text. If you cannot quote it, do not report it.
Return at most 5 findings. Do not invent facts. Plain, direct language, no jargon."""


def _norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def verify(findings: list, page_text: str) -> list:
    hay = _norm(page_text)
    return [x for x in findings if x.get("quote") and _norm(x["quote"]) in hay]


def run(text: str, url: str):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return [], "skipped (no ANTHROPIC_API_KEY)"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(model=MODEL, max_tokens=1500, system=RUBRIC,
                                     messages=[{"role": "user", "content": f"URL: {url}\n\nPAGE TEXT:\n{text[:9000]}"}])
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        good = verify(data.get("findings", []), text)
        out = [Finding(id=f"AI-{i}", area=g["area"][:1].upper() if g.get("area") else "C", title=g["title"],
                       status=g.get("status", "warn"), severity=g.get("severity", "medium"),
                       evidence=f'"{g["quote"]}"', why=g.get("why", ""), fix=g.get("fix", ""),
                       source="ai", level=2) for i, g in enumerate(good)
               if g.get("area", "C")[:1].upper() in "COR"]
        return out, f"{len(out)} kept of {len(data.get('findings', []))} proposed"
    except Exception as e:
        return [], f"failed: {str(e)[:120]}"
