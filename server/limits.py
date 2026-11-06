"""Who may run an audit: 2 per person (email) and 2 per company (site), plus a daily cap per network."""
import hashlib
import re
from urllib.parse import urlparse

TWO_PART = {"co.uk", "org.uk", "com.au", "co.nz", "com.co", "co.za", "com.br", "com.mx", "co.in", "com.ar",
            "com.es", "co.jp", "com.sg", "com.tr", "com.pe", "com.ec", "com.ve", "com.cn", "com.hk"}


def norm_email(email: str) -> str:
    email = (email or "").strip().lower()
    local, _, dom = email.partition("@")
    if dom in ("gmail.com", "googlemail.com"):
        local = local.split("+")[0].replace(".", "")
        dom = "gmail.com"
    else:
        local = local.split("+")[0]
    return f"{local}@{dom}"


def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+", (email or "").strip())) \
        and len(email) <= 50      # AWeber's own limit


def site_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in TWO_PART:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def hash_ip(ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:24]


def check(db, cfg, email_norm: str, domain: str, ip_hash: str):
    """Returns (allowed, code). Codes: ok, email_limit, domain_limit, ip_limit."""
    if email_norm in cfg["admin_emails"]:
        return True, "ok"
    if db.count_audits(email_norm=email_norm) >= cfg["max_per_email"]:
        return False, "email_limit"
    if db.count_audits(domain=domain) >= cfg["max_per_domain"]:
        return False, "domain_limit"
    if db.count_audits(ip_hash=ip_hash, since_hours=24) >= cfg["max_per_ip_day"]:
        return False, "ip_limit"
    return True, "ok"
