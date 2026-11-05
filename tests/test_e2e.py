"""End to end on a fake site (no network)."""
from coreaudit import audit, crawler, fetch as F, keywords, pagespeed, technical, site_checks
from coreaudit.fetch import Page
from coreaudit.report import to_html, meta_csv

HOME = """<html lang=en><head><title>Acme Plumbing | Chicago</title><meta name=viewport content=width>
<meta name=description content="Plumbers in Chicago who fix leaks the same day, with upfront prices and a one year guarantee.">
<link rel=canonical href="https://acme.test/"></head><body><nav><a href="/services">Services</a></nav>
<h1>Same-day plumbers for Chicago homeowners</h1><a href="tel:3125550100">Call 312-555-0100</a>
<a href="/services">Get a free quote</a><a href="/about">About</a><a href="/gone">Old page</a></body></html>"""
SERV = "<html><head><title>Services</title></head><body><h1>Welcome</h1><h4>x</h4><p>short</p></body></html>"
ABOUT = "<html><head><title>Services</title></head><body><p>No headline</p></body></html>"
SITE = {"https://acme.test/": HOME, "https://acme.test/services": SERV, "https://acme.test/about": ABOUT}


def fake_fetch(url, check_public=True):
    url = url if "://" in url else "https://" + url
    if url.endswith("/robots.txt") or "sitemap" in url:
        return Page(url, url, 404)
    if url in SITE:
        return Page(url, url, 200, SITE[url])
    if url.startswith("http://"):
        return Page(url, "https://acme.test/", 200, HOME, redirects=[(301, url, "https://acme.test/")])
    return Page(url, url, 404)


def test_full_run(monkeypatch):
    for mod in (audit, crawler, technical):
        monkeypatch.setattr(mod, "fetch", fake_fetch)
    monkeypatch.setattr(pagespeed, "run", lambda u, s: {"strategy": s, "score": 62, "lcp_ms": 4100})
    monkeypatch.setattr(keywords, "fetch", lambda d: {"ok": True, "total": 40, "backlinks": None, "items": [
        {"keyword": "emergency plumber chicago", "volume": 900, "position": 14, "url": "https://acme.test/services", "brand": False, "difficulty": 30},
        {"keyword": "acme plumbing", "volume": 50, "position": 1, "url": "https://acme.test/", "brand": True, "difficulty": 1}]})
    res = audit.run_audit("acme.test", use_ai=False)
    assert res["ok"] and res["crawl"]["pages_crawled"] == 3
    ids = {f["id"] for f in res["findings"]}
    assert {"C-pages-generic", "E-broken", "O-pages-duptitle", "E-kw-brandonly", "O-kw-headings"} <= ids
    assert any(f["status"] == "pass" for f in res["findings"])
    html = to_html(res)
    assert "What you are doing well" in html and "lead_route" not in html
    assert "acme.test" in meta_csv(res)
