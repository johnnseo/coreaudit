from server import limits


class DB:
    def __init__(self, day):
        self.day = day

    def count_audits(self, email_norm=None, domain=None, ip_hash=None, since_hours=None):
        return self.day if (since_hours and not ip_hash) else 0


def test_daily_cap_blocks_everyone_but_admins():
    cfg = {"admin_emails": ["me@x.co"], "max_per_email": 2, "max_per_domain": 2, "max_per_ip_day": 4, "max_audits_per_day": 60}
    assert limits.check(DB(60), cfg, "a@b.co", "b.co", "h") == (False, "busy")
    assert limits.check(DB(59), cfg, "a@b.co", "b.co", "h") == (True, "ok")
    assert limits.check(DB(99), cfg, "me@x.co", "b.co", "h") == (True, "ok")
