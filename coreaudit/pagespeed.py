"""Google PageSpeed Insights (free). Returns None values on failure rather than raising."""
import os

import requests

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def run(url: str, strategy: str = "mobile") -> dict:
    params = {"url": url, "strategy": strategy, "category": "performance"}
    key = os.getenv("PAGESPEED_API_KEY")
    if key:
        params["key"] = key
    try:
        r = requests.get(API, params=params, timeout=90)
        r.raise_for_status()
        lh = r.json()["lighthouseResult"]
        a = lh["audits"]

        def val(k):
            return a.get(k, {}).get("numericValue")
        return {
            "strategy": strategy,
            "score": round(lh["categories"]["performance"]["score"] * 100),
            "lcp_ms": val("largest-contentful-paint"),
            "fcp_ms": val("first-contentful-paint"),
            "cls": val("cumulative-layout-shift"),
            "tbt_ms": val("total-blocking-time"),
            "speed_index_ms": val("speed-index"),
        }
    except Exception as e:
        return {"strategy": strategy, "score": None, "error": str(e)[:160]}
