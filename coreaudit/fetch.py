"""Polite page fetching with safety checks and redirect re-validation."""
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import requests

from .safety import assert_public, normalize_url

UA = "COREAuditBot/0.1 (+https://athanmarketing.com)"
TIMEOUT = 15
MAX_BYTES = 3_000_000


@dataclass
class Page:
    url: str
    final_url: str
    status: int
    html: str = ""
    headers: dict = field(default_factory=dict)
    seconds: float = 0.0
    redirects: list = field(default_factory=list)
    error: str = ""


def fetch(url: str, check_public: bool = True) -> Page:
    url = normalize_url(url)
    current, hops = url, []
    start = time.time()
    try:
        for _ in range(6):
            if check_public:
                assert_public(current)
            r = requests.get(current, headers={"User-Agent": UA}, timeout=TIMEOUT,
                             allow_redirects=False, stream=True)
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                nxt = urljoin(current, r.headers["Location"])
                hops.append((r.status_code, current, nxt))
                current = normalize_url(nxt)
                continue
            body = r.raw.read(MAX_BYTES, decode_content=True)
            text = body.decode(r.encoding or "utf-8", errors="replace")
            return Page(url, current, r.status_code, text, dict(r.headers),
                        time.time() - start, hops)
        return Page(url, current, 0, error="Too many redirects", redirects=hops)
    except Exception as e:  # network errors become findings, not crashes
        return Page(url, current, 0, error=str(e)[:200], redirects=hops)


def fetch_text(url: str, check_public: bool = True):
    p = fetch(url, check_public)
    return p.status, p.html
