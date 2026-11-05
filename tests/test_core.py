from coreaudit import checks, judge
from coreaudit.parse import parse
from coreaudit.safety import UnsafeURL, normalize_url
from coreaudit.scoring import score

HTML = """<html lang=en><head><title>Hi</title></head><body>
<h1>Welcome to Acme Plumbing</h1><h2>Services</h2><h4>Skipped</h4>
<p>Welcome to Acme Plumbing, we are a company. Call 312-555-0100, Chicago 60601.</p>
<a href="/contact">Learn more</a><form><input type=submit value=Submit></form></body></html>"""


def run():
    f = parse(HTML, "https://acme.test/")
    return f, checks.run_rules(f, {"found": False, "status": 404, "blocks_all": False, "sitemaps": []},
                               {"found": False}, {"https_final": True}, [], 200)


def test_generic_headline_and_weak_cta():
    _, fs = run()
    ids = {x.id: x for x in fs}
    assert ids["C-h1-generic"].status == "fail"
    assert "Welcome" in ids["C-h1-generic"].evidence
    assert ids["R-cta-weak"].status == "warn"
    assert ids["E-heading-skips"].status == "warn"
    assert ids["E-robots"].status == "fail"


def test_scoring_bounds():
    _, fs = run()
    s = score(fs)
    assert 0 <= s["overall"] <= 100 and s["fix_first"] in "CORE"


def test_ssrf_blocked():
    for bad in ("http://localhost/", "http://127.0.0.1/", "ftp://x.com", "http://user:pw@a.com/"):
        try:
            from coreaudit.safety import assert_public
            assert_public(normalize_url(bad))
            assert False, bad
        except UnsafeURL:
            pass


def test_ai_quotes_must_exist():
    text = "We help busy dentists get more patients."
    good = {"quote": "help busy dentists get more patients"}
    bad = {"quote": "award-winning team since 1990"}
    assert judge.verify([good, bad], text) == [good]
