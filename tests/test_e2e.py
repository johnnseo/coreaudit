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


HOME2 = """<html lang=en><head><title>Acme Plumbing | Chicago</title><meta name=viewport content=width>
<link rel=canonical href="https://acme.test/"></head><body>
<h1>Same-day plumbers for Chicago homeowners</h1><a class=btn href="/contact/">Schedule consultation</a>
<a href="/what-we-do/">What we do</a><a href="/what-we-do">What we do</a><a href="/category/tips/">Tips</a>
</body></html>"""
WWD = "<html><head><title>What we do - Acme</title></head><body><h1>What we do</h1><h2>A</h2><p>words</p></body></html>"
CAT = "<html><head><title>Tips Archives</title></head><body><h1>Tips</h1></body></html>"
SITE2 = {"https://acme.test/": HOME2, "https://acme.test/what-we-do/": WWD, "https://acme.test/what-we-do": WWD,
         "https://acme.test/category/tips/": CAT, "https://acme.test/contact/": "<html><head><title>Contact</title></head><body><form></form></body></html>"}


def test_realistic(monkeypatch):
    def ff(url, check_public=True):
        url = url if "://" in url else "https://" + url
        if url in SITE2:
            return Page(url, url, 200, SITE2[url])
        if url.startswith("http://"):
            return Page(url, "https://acme.test/", 200, HOME2)
        return Page(url, url, 404)
    for mod in (audit, crawler, technical):
        monkeypatch.setattr(mod, "fetch", ff)
    monkeypatch.setattr(pagespeed, "run", lambda u, s: {"strategy": s, "score": 40, "lcp_ms": 5200, "cls": 0.3, "tbt_ms": 700, "fcp_ms": 3500})
    res = audit.run_audit("acme.test", use_ai=False, use_keywords=False)
    ids = {f["id"] for f in res["findings"]}
    assert "R-contact-none" not in ids            # 'Schedule consultation' counts
    assert "O-pages-duptitle" not in ids           # /what-we-do and /what-we-do/ are one page
    assert not any("category" in (f["evidence"]) for f in res["findings"] if f["area"] in "O")
    assert {"E-cwv-lcp_ms", "E-cwv-cls", "E-speed-mobile"} <= ids
    html = to_html(res)
    assert "Speed and Core Web Vitals" in html and "Main content appears" in html
    open("/tmp/r2.html", "w").write(html)
