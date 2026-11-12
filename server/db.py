"""SQLite storage. On Render, put the file on the persistent disk (DB_PATH=/data/core.db)."""
import json
import os
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS audits(
  token TEXT PRIMARY KEY, created REAL, finished REAL, status TEXT, stage TEXT, error TEXT,
  name TEXT, email TEXT, email_norm TEXT, url TEXT, domain TEXT, city TEXT, ip_hash TEXT,
  consent_privacy INTEGER, consent_marketing INTEGER, consent_at REAL,
  result TEXT, route TEXT, answers TEXT, aweber TEXT);
CREATE INDEX IF NOT EXISTS i_email ON audits(email_norm);
CREATE INDEX IF NOT EXISTS i_domain ON audits(domain);
CREATE INDEX IF NOT EXISTS i_ip ON audits(ip_hash, created);
CREATE TABLE IF NOT EXISTS scorecards(
  token TEXT PRIMARY KEY, created REAL, name TEXT, email TEXT, email_norm TEXT, ip_hash TEXT,
  consent_privacy INTEGER, consent_marketing INTEGER, consent_at REAL, vid TEXT, variant TEXT,
  done REAL, scores TEXT, answers TEXT, aweber TEXT);
CREATE INDEX IF NOT EXISTS i_sc_email ON scorecards(email_norm);
CREATE TABLE IF NOT EXISTS checklist_leads(
  created REAL, name TEXT, email TEXT, email_norm TEXT, consent_marketing INTEGER, consent_at REAL, variant TEXT, vid TEXT, aweber TEXT);
CREATE INDEX IF NOT EXISTS i_cl_email ON checklist_leads(email_norm);
CREATE TABLE IF NOT EXISTS events(ts REAL, vid TEXT, variant TEXT, magnet TEXT, event TEXT);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""


class DB:
    def __init__(self, path):
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.c.executescript(SCHEMA)
            for col in ("vid", "variant"):                  # older databases: add the A/B columns
                try:
                    self.c.execute(f"ALTER TABLE audits ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass
            self.c.commit()

    def _x(self, sql, args=()):
        with self.lock:
            cur = self.c.execute(sql, args)
            self.c.commit()
            return cur

    def create(self, **k):
        k.setdefault("created", time.time())
        cols = ",".join(k)
        self._x(f"INSERT INTO audits({cols}) VALUES({','.join('?' * len(k))})", tuple(k.values()))

    def update(self, token, **k):
        sets = ",".join(f"{c}=?" for c in k)
        self._x(f"UPDATE audits SET {sets} WHERE token=?", (*k.values(), token))

    def get(self, token):
        with self.lock:
            r = self.c.execute("SELECT * FROM audits WHERE token=?", (token,)).fetchone()
        return dict(r) if r else None

    def count_audits(self, email_norm=None, domain=None, ip_hash=None, since_hours=None):
        where, args = ["status!='failed'"], []
        for col, val in (("email_norm", email_norm), ("domain", domain), ("ip_hash", ip_hash)):
            if val is not None:
                where.append(f"{col}=?")
                args.append(val)
        if since_hours:
            where.append("created>?")
            args.append(time.time() - since_hours * 3600)
        with self.lock:
            return self.c.execute(f"SELECT COUNT(*) FROM audits WHERE {' AND '.join(where)}", args).fetchone()[0]

    def recent_same(self, email_norm, domain, days=30):
        with self.lock:
            r = self.c.execute("SELECT token FROM audits WHERE email_norm=? AND domain=? AND status='done' AND created>? "
                               "ORDER BY created DESC LIMIT 1", (email_norm, domain, time.time() - days * 86400)).fetchone()
        return r["token"] if r else None

    def leads(self):
        with self.lock:
            return [dict(r) for r in self.c.execute(
                "SELECT created,name,email,url,city,status,route,consent_marketing,aweber,answers,result,variant FROM audits "
                "ORDER BY created DESC")]

    def kv_get(self, k):
        with self.lock:
            r = self.c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return r["v"] if r else None

    def kv_set(self, k, v):
        self._x("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    # ---- scorecard + A/B ----
    def create_scorecard(self, **k):
        self._x(f"INSERT INTO scorecards({','.join(k)}) VALUES({','.join('?' * len(k))})", tuple(k.values()))

    def get_scorecard(self, token):
        with self.lock:
            r = self.c.execute("SELECT * FROM scorecards WHERE token=?", (token,)).fetchone()
        return dict(r) if r else None

    def scorecard_for_email(self, email_norm):
        with self.lock:
            r = self.c.execute("SELECT * FROM scorecards WHERE email_norm=? ORDER BY created DESC LIMIT 1", (email_norm,)).fetchone()
        return dict(r) if r else None

    def finish_scorecard(self, token, scores, answers, aweber):
        self._x("UPDATE scorecards SET done=?, scores=?, answers=?, aweber=? WHERE token=?",
                (time.time(), scores, answers, aweber, token))

    def count_scorecards(self, ip_hash, since_hours):
        with self.lock:
            return self.c.execute("SELECT COUNT(*) FROM scorecards WHERE ip_hash=? AND created>?",
                                  (ip_hash, time.time() - since_hours * 3600)).fetchone()[0]

    def log_event(self, vid, variant, magnet, event):
        self._x("INSERT INTO events VALUES(?,?,?,?,?)", (time.time(), vid, variant, magnet, event))

    def ab_summary(self):
        with self.lock:
            rows = self.c.execute(
                "SELECT variant, magnet, COUNT(DISTINCT CASE WHEN event='view' THEN vid END) views, "
                "COUNT(DISTINCT CASE WHEN event='lead' THEN vid END) leads, "
                "COUNT(DISTINCT CASE WHEN event='complete' THEN vid END) done "
                "FROM events GROUP BY variant, magnet ORDER BY variant, magnet").fetchall()
        return [dict(r) for r in rows]

    def scorecards(self):
        with self.lock:
            return [dict(r) for r in self.c.execute(
                "SELECT created,name,email,consent_marketing,aweber,scores,done,variant FROM scorecards ORDER BY created DESC")]

    def add_checklist_lead(self, **k):
        self._x(f"INSERT INTO checklist_leads({','.join(k)}) VALUES({','.join('?' * len(k))})", tuple(k.values()))

    def checklist_leads(self):
        with self.lock:
            return [dict(r) for r in self.c.execute("SELECT * FROM checklist_leads ORDER BY created DESC")]
