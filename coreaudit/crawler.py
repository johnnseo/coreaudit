"""Small polite crawler: same-site pages only, public addresses only, capped page count.

Adapted from the original tool's crawler (BFS, metas, headings, broken links) and routed through
the safe fetcher so it can never be pointed at internal addresses.
"""
import re
import time
import urllib.robotparser
from collections import deque, defaultdict
from urllib.parse import urldefrag, urlparse

from .fetch import fetch, UA
from .parse import parse

SKIP_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".zip", ".mp4", ".mp3", ".css",
            ".js", ".xml", ".ico", ".doc", ".docx", ".xls", ".xlsx")


ARCHIVE_RE = re.compile(r"/(category|categories|tag|tags|author|authors|archive|archives|feed)(/|$)|/page/\d+", re.I)
UTILITY_RE = re.compile(r"/(contact|thank|privacy|terms|cookie|login|log-in|cart|checkout|my-account|search|404|"
                        r"disclaimer|policy|sitemap|unsubscribe|wp-)", re.I)


def norm(u):
    p = urlparse(u)
    host = (p.hostname or "").lower().removeprefix("www.")
    return f"{host}{(p.path or '/').rstrip('/') or '/'}".lower()


def kind(u):
    path = urlparse(u).path
    if ARCHIVE_RE.search(path):
        return "archive"
    if UTILITY_RE.search(path):
        return "utility"
    return "content"


def _host(u):
    return (urlparse(u).hostname or "").lower().removeprefix("www.")


def crawl(start_url: str, robots_text: str = "", max_pages: int = 25, delay: float = 0.2,
          budget_seconds: int = 90) -> dict:
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_text.splitlines() if robots_text else [])
    root = _host(start_url)
    queue, seen = deque([start_url]), {norm(start_url)}
    done = set()
    aliases = 0
    pages, broken, inlinks = {}, [], defaultdict(int)
    t0 = time.time()
    while queue and len(pages) < max_pages and time.time() - t0 < budget_seconds:
        url = queue.popleft()
        try:
            if robots_text and not rp.can_fetch(UA, url):
                continue
        except Exception:
            pass
        p = fetch(url)
        time.sleep(delay)
        if p.status >= 400 or p.status == 0:
            broken.append({"url": url, "status": p.status or "no response"})
            continue
        if "<html" not in p.html[:2000].lower() and "<!doctype" not in p.html[:200].lower():
            continue
        key = norm(p.final_url)
        if key in done:          # same page reached by another address (slash, www, redirect)
            aliases += 1
            continue
        done.add(key)
        f = parse(p.html, p.final_url)
        if f.canonical and norm(f.canonical) != key and _host(f.canonical) == root:
            aliases += 1          # this address just points to another page; graded there
            pending = f.canonical
            if norm(pending) not in seen and len(seen) < max_pages * 4:
                seen.add(norm(pending))
                queue.append(pending)
            continue
        h = f.headings
        pages[url] = {"kind": kind(p.final_url),
            "url": url, "title": f.title, "meta_desc": f.meta_desc, "word_count": f.word_count,
            "h1": [t for l, t in h if l == 1], "h2": [t for l, t in h if l == 2],
            "levels": [l for l, _ in h], "noindex": "noindex" in f.robots_meta,
            "canonical": f.canonical,
        }
        for link in f.internal_links:
            link = urldefrag(link)[0]
            if not link or link.lower().endswith(SKIP_EXT) or "?" in link or _host(link) != root:
                continue
            inlinks[link] += 1
            if norm(link) not in seen and len(seen) < max_pages * 4:
                seen.add(norm(link))
                queue.append(link)
    return {"pages": pages, "broken": broken, "pages_crawled": len(pages),
            "aliases_skipped": aliases, "hit_limit": bool(queue) and len(pages) >= max_pages,
            "inlinks": dict(inlinks)}
