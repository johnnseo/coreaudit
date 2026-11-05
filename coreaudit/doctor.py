"""Checks that the keys in GitHub Secrets work. Prints OK / FAIL only, never the keys."""
import os

import requests


def main():
    print("Key check (values are never printed)")
    for k in ("ANTHROPIC_API_KEY", "PAGESPEED_API_KEY", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"):
        print(f"  {k}: {'set' if os.getenv(k) else 'MISSING'}")
    # Anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        try:
            import anthropic
            from .judge import MODELS
            c = anthropic.Anthropic(api_key=key)
            for m in MODELS:
                try:
                    c.messages.create(model=m, max_tokens=5, messages=[{"role": "user", "content": "ok"}])
                    print(f"  Anthropic: OK (model {m})")
                    break
                except Exception as e:
                    print(f"  Anthropic model {m}: FAIL ({str(e)[:90]})")
        except Exception as e:
            print(f"  Anthropic: FAIL ({str(e)[:90]})")
    # PageSpeed
    try:
        from .pagespeed import run
        r = run("https://example.com", "mobile")
        print("  PageSpeed: OK" if r.get("score") is not None else f"  PageSpeed: FAIL ({r.get('error')})")
    except Exception as e:
        print(f"  PageSpeed: FAIL ({e})")
    # DataForSEO (this endpoint is free)
    u, p = os.getenv("DATAFORSEO_LOGIN"), os.getenv("DATAFORSEO_PASSWORD")
    if u and p:
        try:
            r = requests.get("https://api.dataforseo.com/v3/appendix/user_data", auth=(u, p), timeout=30)
            d = r.json()
            ok = d.get("status_code") == 20000
            bal = (d.get("tasks") or [{}])[0].get("result", [{}])[0].get("money", {}).get("balance") if ok else None
            print(f"  DataForSEO: OK (balance {bal})" if ok else f"  DataForSEO: FAIL ({d.get('status_message')})")
        except Exception as e:
            print(f"  DataForSEO: FAIL ({str(e)[:90]})")


if __name__ == "__main__":
    main()
