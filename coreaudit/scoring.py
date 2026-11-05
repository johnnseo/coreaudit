from .models import AREAS, SEVERITY_WEIGHT

PENALTY = {"fail": 1.0, "warn": 0.5, "unknown": 0.0, "pass": 0.0}


def score(findings):
    """Each area starts at 100 and loses points by severity and status. Returns dict per area + overall."""
    res = {}
    for code, name in AREAS.items():
        items = [f for f in findings if f.area == code]
        loss = sum(SEVERITY_WEIGHT[f.severity] * PENALTY[f.status] * 6 for f in items)
        res[code] = {"name": name, "score": round(100 / (1 + loss / 45)),
                     "issues": len([f for f in items if f.status in ("fail", "warn")])}
    res["overall"] = round(sum(res[c]["score"] for c in AREAS) / 4)
    weakest = min(AREAS, key=lambda c: res[c]["score"])
    res["fix_first"] = weakest
    return res


def route_lead(scores, findings, answers=None):
    """done_for_you | strategy_session | nurture. Answers (from the questions step) outweigh the score."""
    a = answers or {}
    high = len([f for f in findings if f.status == "fail" and f.severity == "high"])
    goals = set(a.get("goals") or [])
    wants_results = bool(goals & {"leads", "conversions", "sales", "visibility"})
    if a.get("help") == "dfy" and (wants_results or high >= 2):
        return "done_for_you"
    if a.get("help") == "diy" or (wants_results and high >= 2) or high >= 4:
        return "strategy_session"
    return "nurture"
