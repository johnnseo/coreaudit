"""All settings come from environment variables (set them in Render, never in code)."""
import os


def _list(name, default=""):
    return [x.strip().rstrip("/") for x in os.getenv(name, default).split(",") if x.strip()]


def get():
    e = os.getenv
    return {
        "public_base": e("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        "site_origins": _list("SITE_ORIGINS", "https://athanmarketing.com,https://www.athanmarketing.com"),
        "db_path": e("DB_PATH", "data/core.db"),
        "max_per_email": int(e("MAX_AUDITS_PER_EMAIL", "2")),
        "max_per_domain": int(e("MAX_AUDITS_PER_DOMAIN", "2")),
        "max_per_ip_day": int(e("MAX_AUDITS_PER_IP_DAY", "6")),
        "max_concurrent": int(e("MAX_CONCURRENT_AUDITS", "3")),
        "crawl_pages": int(e("CRAWL_PAGES", "15")),
        "admin_key": e("ADMIN_KEY", ""),
        "admin_emails": [x.lower() for x in _list("ADMIN_EMAILS")],   # unlimited tries, for testing
        "ip_salt": e("IP_SALT", "change-me"),
        "ab_scorecard_share": float(e("AB_SCORECARD_SHARE", "0.5")),
        "privacy_url": e("PRIVACY_URL", "https://athanmarketing.com/privacy-policy/"),
        "review_url": e("REVIEW_URL", "https://calendar.app.google/xkJUcqHrNDSCYwNi8"),
        "turnstile_site": e("TURNSTILE_SITEKEY", ""),
        "turnstile_secret": e("TURNSTILE_SECRET", ""),
        "alert_webhook": e("ALERT_WEBHOOK_URL", ""),
        "aweber": {"client_id": e("AWEBER_CLIENT_ID", ""), "client_secret": e("AWEBER_CLIENT_SECRET", ""),
                   "account_id": e("AWEBER_ACCOUNT_ID", ""), "list_id": e("AWEBER_LIST_ID", ""),
                   "refresh_token": e("AWEBER_REFRESH_TOKEN", "")},
    }
