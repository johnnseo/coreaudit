"""Run one audit end to end."""
import argparse
import re
import json
import sys
import time

from . import checks, crawler, gbp, judge, keywords, pagespeed, site_checks, technical
from .fetch import fetch
from .parse import parse
from .safety import UnsafeURL, normalize_url
from .scoring import route_lead, score


def run_audit(raw_url: str, use_speed=True, use_ai=True, use_keywords=True, max_pages=25, local=None, city="") -> dict:
    t0 = time.time()
    url = normalize_url(raw_url)
    page = fetch(url)
    if page.status != 200 or not page.html:
        return {"url": url, "ok": False, "error": page.error or f"Site returned status {page.status}"}
    facts = parse(page.html, page.final_url)
    robots = technical.check_robots(page.final_url)
    sitemap = technical.check_sitemap(page.final_url, robots)
    https = technical.check_https(page.final_url)
    speed = [pagespeed.run(page.final_url, s) for s in ("mobile", "desktop")] if use_speed else []
    findings = checks.run_rules(facts, robots, sitemap, https, speed, page.status)
    findings += checks.run_strengths(facts, https, speed)
    crawl = crawler.crawl(page.final_url, robots.get("text", ""), max_pages=max_pages)
    findings += site_checks.crawl_findings(crawl)
    g = {"ok": False, "skipped": True}
    is_local = local if local is not None else (facts.is_local or bool(facts.zips and (facts.phones or facts.tel_links)))
    if is_local:
        from urllib.parse import urlparse as _u
        name = facts.business_name or re.split(r"\s[|\-–—]\s", facts.title)[0]
        g = gbp.lookup(name, city or facts.schema_city, _u(page.final_url).hostname)
        findings += gbp.findings(g, (facts.tel_links or facts.phones or [facts.schema_phone])[0] if (facts.tel_links or facts.phones or facts.schema_phone) else "")
    kw = {"ok": False, "skipped": True}
    if use_keywords:
        from urllib.parse import urlparse
        kw = keywords.fetch(urlparse(page.final_url).hostname)
        findings += site_checks.keyword_findings(kw, facts, crawl["pages"])
    ai_note = "off"
    if use_ai:
        ai, ai_note = judge.run(facts.text, page.final_url)
        findings += ai
    js_heavy = facts.word_count < 60 and page.html.lower().count("<script") >= 5
    if js_heavy:  # content built by JavaScript: we cannot judge copy/headings fairly from raw HTML
        skip = {"C-h1-missing", "O-thin-home", "E-h2-missing", "R-cta-none", "R-contact-none", "C-h1-generic",
                "O-title-length", "O-keyword-heading", "E-pages-h1", "O-pages-thin", "R-cta-late"}
        findings = [f for f in findings if f.id not in skip]
        from .models import Finding
        findings.append(Finding(id="E-js-note", area="E", title="Your content loads through JavaScript", status="warn",
                                severity="low", evidence=f"Only {facts.word_count} words visible in the page code.",
                                why="Search engines and visitors on slow connections may see less than a browser shows.",
                                fix="Make sure key copy and headings are in the page's HTML, not added later by scripts."))
    scores = score(findings)
    order = {"fail": 0, "warn": 1, "unknown": 2, "pass": 3}
    sev = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.status], sev[f.severity]))
    return {"url": page.final_url, "ok": True, "seconds": round(time.time() - t0, 1),
            "scores": scores, "lead_route": route_lead(scores, findings),
            "ai_judge": ai_note, "speed": speed, "keywords": kw, "gbp": g, "is_local": bool(is_local),
            "crawl": {"pages_crawled": crawl["pages_crawled"], "pages": list(crawl["pages"].values())},
            "findings": [f.to_dict() for f in findings],
            "facts": {"title": facts.title, "h1": [t for l, t in facts.headings if l == 1],
                      "words": facts.word_count, "analytics": facts.analytics}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="C.O.R.E. audit")
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", default="reports/audit.json")
    ap.add_argument("--no-speed", action="store_true")
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--no-keywords", action="store_true")
    ap.add_argument("--local", action="store_true", help="force the Google Business Profile check")
    ap.add_argument("--city", default="")
    ap.add_argument("--pages", type=int, default=25)
    a = ap.parse_args(argv)
    try:
        res = run_audit(a.url, not a.no_speed, not a.no_ai, not a.no_keywords, a.pages, True if a.local else None, a.city)
    except UnsafeURL as e:
        print(f"Rejected: {e}")
        return 2
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=2)
    from .report import meta_csv, to_html
    with open(a.out.replace(".json", ".html"), "w") as fh:
        fh.write(to_html(res))
    if res.get("ok"):
        with open(a.out.replace(".json", "-pages.csv"), "w") as fh:
            fh.write(meta_csv(res))
    if res.get("ok"):
        s = res["scores"]
        print(f"{res['url']}  overall {s['overall']}  " + "  ".join(f"{c}:{s[c]['score']}" for c in 'CORE')
              + f"  fix first: {s['fix_first']}  route: {res['lead_route']}  ai: {res['ai_judge']}")
    else:
        print("Audit failed:", res["error"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
