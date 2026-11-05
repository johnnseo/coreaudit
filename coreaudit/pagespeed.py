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


def run(url: str, strategy: str = "mobile") -> dict:
    params = {"url": url, "strategy": strategy, "category": "performance"}
    key = os.getenv("PAGESPEED_API_KEY")
    if key:
        params["key"] = key
    last = ""
    for attempt in range(3):
        try:
            r = requests.get(API, params=params, timeout=120)
            if r.status_code in (429, 500, 503):
                last = f"Google answered {r.status_code}"
                time.sleep(4 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
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
                                "lcp_ms": p("LARGEST_CONTENTFUL_PAINT_MS"),
                                "inp_ms": p("INTERACTION_TO_NEXT_PAINT"),
                                "cls": (cls / 100) if cls is not None else None}
            return out
        except Exception as e:
            last = str(e)[:160]
            time.sleep(3)
    return {"strategy": strategy, "score": None, "error": last}
