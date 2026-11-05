"""Turn raw HTML into the facts the checks need."""
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

CTA_WORDS = re.compile(r"\b(book|call|contact|get (a |your )?(free |quote|started|estimate|audit)|schedule|"
                       r"request|start|buy|shop|sign ?up|subscribe|download|try|talk|apply|order|reserve|"
                       r"consult|demo|quote)\b", re.I)
CONTACT_RE = re.compile(r"contact|consult|schedule|book|appointment|quote|get-in-touch|get in touch|reach us|talk to|free (call|review|audit)", re.I)
WEAK_CTA = {"submit", "click here", "learn more", "read more", "send", "go", "more", "here"}
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{8,}\d)")
ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
SOCIAL = ("facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com",
          "tiktok.com", "pinterest.com")
GENERIC_H = re.compile(r"^\s*(welcome( to)?|home|hello|hi there|about us|our (company|website))\b", re.I)


@dataclass
class Facts:
    url: str
    title: str = ""
    meta_desc: str = ""
    canonical: str = ""
    robots_meta: str = ""
    lang: str = ""
    viewport: bool = False
    headings: list = field(default_factory=list)      # [(level, text)]
    ctas: list = field(default_factory=list)          # [(text, href, position_index)]
    buttons_weak: list = field(default_factory=list)
    forms: int = 0
    tel_links: list = field(default_factory=list)
    mailto_links: list = field(default_factory=list)
    social_links: list = field(default_factory=list)
    schema_types: list = field(default_factory=list)
    schema_raw: list = field(default_factory=list)
    og: dict = field(default_factory=dict)
    images_total: int = 0
    images_no_alt: int = 0
    text: str = ""
    first_text: str = ""        # roughly the first screen of copy
    phones: list = field(default_factory=list)
    zips: list = field(default_factory=list)
    has_map_or_gbp: bool = False
    analytics: list = field(default_factory=list)
    internal_links: list = field(default_factory=list)
    nav_links: list = field(default_factory=list)
    contact_links: list = field(default_factory=list)
    word_count: int = 0


def _types(node, out):
    if isinstance(node, dict):
        t = node.get("@type")
        if t:
            out.extend(t if isinstance(t, list) else [t])
        for v in node.values():
            _types(v, out)
    elif isinstance(node, list):
        for v in node:
            _types(v, out)


def parse(html: str, url: str) -> Facts:
    soup = BeautifulSoup(html, "lxml")
    f = Facts(url=url)
    host = urlparse(url).hostname or ""

    f.title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    f.meta_desc = (md.get("content") or "").strip() if md else ""
    can = soup.find("link", rel="canonical")
    f.canonical = can.get("href", "").strip() if can else ""
    rb = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    f.robots_meta = (rb.get("content") or "").lower() if rb else ""
    f.lang = (soup.html.get("lang") or "") if soup.html else ""
    f.viewport = bool(soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}))
    for m in soup.find_all("meta", property=re.compile("^og:")):
        f.og[m["property"]] = m.get("content", "")

    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
            f.schema_raw.append(data)
            _types(data, f.schema_types)
        except Exception:
            pass

    html_low = html.lower()
    for name, needle in (("Google Analytics/GTM", "googletagmanager.com"), ("GA4", "gtag("),
                         ("Meta Pixel", "fbevents.js"), ("Google Analytics", "google-analytics.com")):
        if needle in html_low:
            f.analytics.append(name)
    f.has_map_or_gbp = any(k in html_low for k in ("google.com/maps", "maps.google", "g.page", "goo.gl/maps"))

    for h in soup.find_all(re.compile("^h[1-6]$")):
        txt = " ".join(h.get_text(" ", strip=True).split())
        f.headings.append((int(h.name[1]), txt))

    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()

    f.images_total = len(soup.find_all("img"))
    f.images_no_alt = len([i for i in soup.find_all("img") if not (i.get("alt") or "").strip()])
    f.forms = len(soup.find_all("form"))

    nav = soup.find("nav")
    if nav:
        f.nav_links = [" ".join(a.get_text(" ", strip=True).split()) for a in nav.find_all("a")][:20]

    body = soup.body or soup
    f.text = " ".join(body.get_text(" ", strip=True).split())
    f.word_count = len(f.text.split())
    f.first_text = " ".join(f.text.split()[:120])
    f.phones = list(dict.fromkeys(PHONE_RE.findall(f.text)))[:5]
    f.zips = list(dict.fromkeys(ZIP_RE.findall(f.text)))[:5]

    for i, a in enumerate(body.find_all(["a", "button"])):
        label = " ".join(a.get_text(" ", strip=True).split())
        href = a.get("href", "") if a.name == "a" else ""
        if href.startswith("tel:"):
            f.tel_links.append(href[4:])
        elif href.startswith("mailto:"):
            f.mailto_links.append(href[7:])
        elif href:
            full = urljoin(url, href)
            h = urlparse(full).hostname or ""
            if any(s in h for s in SOCIAL):
                f.social_links.append(full)
            elif h.replace("www.", "") == host.replace("www.", ""):
                f.internal_links.append(full)
                if CONTACT_RE.search(label) or CONTACT_RE.search(urlparse(full).path):
                    f.contact_links.append((label, full))
        if label and len(label) < 60 and (CTA_WORDS.search(label) or label.lower() in WEAK_CTA):
            f.ctas.append((label, href, i))
            if label.lower() in WEAK_CTA:
                f.buttons_weak.append(label)
    for inp in soup.find_all("input", type=re.compile("^(submit|button)$", re.I)):
        v = (inp.get("value") or "").strip()
        if v.lower() in WEAK_CTA:
            f.buttons_weak.append(v)
    f.social_links = list(dict.fromkeys(f.social_links))
    return f
