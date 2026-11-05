"""robots.txt, sitemap, https and redirect basics."""
import re
from urllib.parse import urlparse

from .fetch import fetch


def origin(url):
    p = urlparse(url)
    return f"{p.scheme}://{p.hostname}"


def check_robots(url) -> dict:
    page = fetch(origin(url) + "/robots.txt")
    out = {"found": False, "text": "", "sitemaps": [], "blocks_all": False, "status": page.status}
    if page.status == 200 and "<html" not in page.html[:200].lower():
        out["found"] = True
        out["text"] = page.html[:4000]
        out["sitemaps"] = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", page.html)
        groups = re.split(r"(?im)^\s*user-agent:", page.html)
        for g in groups[1:]:
            agent, _, rules = g.partition("\n")
            if agent.strip() == "*" and re.search(r"(?im)^\s*disallow:\s*/\s*$", rules):
                out["blocks_all"] = True
    return out


def check_sitemap(url, robots) -> dict:
    candidates = list(robots.get("sitemaps", [])) or []
    for c in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
        candidates.append(origin(url) + c)
    for c in dict.fromkeys(candidates):
        p = fetch(c)
        if p.status == 200 and ("<urlset" in p.html or "<sitemapindex" in p.html):
            return {"found": True, "url": c, "urls": len(re.findall(r"<loc>", p.html)),
                    "in_robots": c in robots.get("sitemaps", [])}
    return {"found": False}


def check_https(url) -> dict:
    http = fetch("http://" + urlparse(url).hostname + "/")
    return {"https_final": http.final_url.startswith("https://"), "status": http.status,
            "hops": len(http.redirects)}
