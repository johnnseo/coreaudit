"""Google PageSpeed Insights (free): lab data plus real-user Core Web Vitals when Google has them."""
import os
import time

import requests

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# (good, poor) thresholds from Google's Core Web Vitals guidance
LIMITS = {"lcp_ms": (2500, 4000), "cls": (0.1, 0.25), "tbt_ms": (200, 600), "fcp_ms": (1800, 3000),
          "inp_ms": (200, 500)}


def rate(metric, value):
    if value is None:
        return None
    good, poor = LIMITS[metric]
    return "good" if value <= good else ("ok" if value <= poor else "poor")


def _variants(url):
    """Same page, other spellings. Google's tester sometimes fails on one and works on another."""
    from urllib.parse import urlparse
    p = urlparse(url)
    host = p.hostname or ""
    alt = host.removeprefix("www.") if host.startswith("www.") else "www." + host
    out = [url, f"{p.scheme}://{alt}{p.path or '/'}"]
    if not url.endswith("/"):
        out.insert(1, url + "/")
    return list(dict.fromkeys(out))


def _err(r):
    try:
        e = r.json().get("error", {})
        reason = (e.get("errors") or [{}])[0].get("reason", "")
        return r.status_code, e.get("message", "")[:200], reason
    except Exception:
        return r.status_code, r.text[:200], ""


def run(url: str, strategy: str = "mobile") -> dict:
    key = os.getenv("PAGESPEED_API_KEY")
    notes, last = [], ""
    for target in _variants(url):
        use_key = key
        for attempt in range(3):
            params = {"url": target, "strategy": strategy, "category": "performance"}
            if use_key:
                params["key"] = use_key
            try:
                r = requests.get(API, params=params, timeout=120)
            except Exception as ex:
                last = f"network: {str(ex)[:120]}"
                time.sleep(3)
                continue
            if r.status_code == 200:
                out = _parse(r.json(), strategy)
                if notes:
                    out["note"] = "; ".join(dict.fromkeys(notes))
                return out
            code, msg, reason = _err(r)
            last = f"HTTP {code} {reason}: {msg}".strip()
            low = (msg + reason).lower()
            if code in (400, 403) and use_key and ("api key" in low or "keyinvalid" in low or "api_key" in low
                                                  or "not been used" in low or "blocked" in low
                                                  or "referer" in low or "ipaddress" in low):
                notes.append(f"Your PageSpeed key was rejected ({reason or code}); used the free anonymous quota")
                use_key = None            # anonymous requests are allowed, just rate limited
                continue
            if code in (429, 500, 503):
                time.sleep(5 * (attempt + 1))
                continue
            break                          # 400 on this spelling of the URL: try the next one
    hint = ""
    if "429" in last or "quota" in last.lower():
        hint = " Add or fix PAGESPEED_API_KEY (enable 'PageSpeed Insights API' for the key)."
    return {"strategy": strategy, "score": None, "error": last + hint}


def _parse(data, strategy):
    lh = data["lighthouseResult"]
    a = lh["audits"]

    def val(k):
        return a.get(k, {}).get("numericValue")
    out = {"strategy": strategy, "score": round(lh["categories"]["performance"]["score"] * 100),
           "lcp_ms": val("largest-contentful-paint"), "fcp_ms": val("first-contentful-paint"),
           "cls": val("cumulative-layout-shift"), "tbt_ms": val("total-blocking-time"),
           "speed_index_ms": val("speed-index"), "field": None}
    m = (data.get("loadingExperience") or {}).get("metrics") or {}
    if m:
        def p(k):
            return (m.get(k) or {}).get("percentile")
        cls = p("CUMULATIVE_LAYOUT_SHIFT_SCORE")
        out["field"] = {"verdict": data["loadingExperience"].get("overall_category"),
                        "lcp_ms": p("LARGEST_CONTENTFUL_PAINT_MS"), "inp_ms": p("INTERACTION_TO_NEXT_PAINT"),
                        "cls": (cls / 100) if cls is not None else None}
    return out
