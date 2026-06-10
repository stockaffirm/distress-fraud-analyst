#!/usr/bin/env python3
"""
state_db.py -- durable SQLite status table for the distress calibration loop.

This is the "know where to start / what to reprocess" store the loop needs. It survives
any stop (state is on disk), is queryable, and drives a self-starting runner. (Project rule
is "no Supabase writes", so the table is LOCAL SQLite -- functionally identical for
resumability; the schema below maps 1:1 to a Supabase table if that rule is ever lifted.)

Schema (table `tickers`):
  ticker PK · market_cap · sector · status(pending|done|error|skip)
  screen_bucket · effective_bucket · distress_type · verdict
  api_distress/api_fraud/api_high_short/api_recent_raise · short_dtc
  reasons · fraud_reasons · effective_reason · note
  logic_version · last_processed_utc · attempts

A ticker is DUE for (re)processing when:  status='pending'  OR  logic_version != current
  OR  last_processed older than its TTL (AVOID/WATCH/REC: 7d, CLEAR: 30d, SKIP: 30d).

  python3 state_db.py init           # create db, seed universe, import existing ledger
  python3 state_db.py stats          # status / bucket / due counts
  python3 state_db.py due 20         # list next 20 due tickers
"""
import os, sys, sqlite3, csv, json

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "calibration_state.db")
LEDGER = os.path.join(HERE, "CALIBRATION_LEDGER.csv")
LOGIC_VERSION = "v1-2026-06-09"     # bump on any screen/scan logic change -> forces re-validation
TTL_DAYS = {"AVOID": 7, "WATCH": 7, "DISTRESSED-RECOVERABLE": 7, "CLEAR": 30}
DEFAULT_TTL = 30

FIELDS = ["ticker", "market_cap", "sector", "status", "screen_bucket", "effective_bucket",
          "distress_type", "verdict", "api_distress", "api_fraud", "api_high_short",
          "api_recent_raise", "short_dtc", "edgar_gc", "edgar_mw", "edgar_cov",
          "reasons", "fraud_reasons", "effective_reason",
          "note", "logic_version", "last_processed_utc", "attempts"]


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()
    c.execute(f"""CREATE TABLE IF NOT EXISTS tickers (
        ticker TEXT PRIMARY KEY, market_cap REAL, sector TEXT, status TEXT,
        screen_bucket TEXT, effective_bucket TEXT, distress_type TEXT, verdict TEXT,
        api_distress INT, api_fraud INT, api_high_short INT, api_recent_raise INT,
        short_dtc REAL, reasons TEXT, fraud_reasons TEXT, effective_reason TEXT, note TEXT,
        logic_version TEXT, last_processed_utc TEXT, attempts INT DEFAULT 0)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_status ON tickers(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_mc ON tickers(market_cap)")
    # Add EDGAR columns to existing databases (ALTER TABLE ... ADD COLUMN is idempotent via try/except)
    for col_def in ("edgar_gc INT", "edgar_mw INT", "edgar_cov INT"):
        try:
            c.execute(f"ALTER TABLE tickers ADD COLUMN {col_def}")
        except Exception:
            pass   # column already exists
    c.commit()
    return c


def seed_universe(c):
    """Insert every universe ticker as pending (idempotent -- never clobbers existing rows)."""
    from data_loader import _recs
    recs = _recs()
    n = 0
    for t, r in recs.items():
        try:
            mc = float(r.get("market_cap")) if r.get("market_cap") not in (None, "", "None") else 0.0
        except (TypeError, ValueError):
            mc = 0.0
        cur = c.execute("INSERT OR IGNORE INTO tickers(ticker,market_cap,sector,status,attempts) "
                        "VALUES(?,?,?,'pending',0)", (t, mc, r.get("sector") or ""))
        n += cur.rowcount
    c.commit()
    return n


def import_ledger(c, now_utc):
    """Backfill processed results from the existing CSV ledger so we don't redo finished work."""
    if not os.path.exists(LEDGER):
        return 0
    n = 0
    for r in csv.DictReader(open(LEDGER)):
        status = "skip" if r["bucket"].startswith("SKIP") else ("error" if r["verdict"] == "ERROR" else "done")
        c.execute("""UPDATE tickers SET status=?, screen_bucket=?, effective_bucket=?, distress_type=?,
                     verdict=?, api_distress=?, api_fraud=?, api_high_short=?, api_recent_raise=?,
                     short_dtc=?, reasons=?, fraud_reasons=?, effective_reason=?, note=?,
                     logic_version=?, last_processed_utc=? WHERE ticker=?""",
                  (status, r.get("bucket"), r.get("effective_bucket"), r.get("distress_type"),
                   r.get("verdict"), _i(r.get("api_distress")), _i(r.get("api_fraud")),
                   _i(r.get("api_high_short")), _i(r.get("api_recent_raise")), _f(r.get("short_dtc")),
                   r.get("reasons"), r.get("fraud_reasons"), r.get("effective_reason"), r.get("note"),
                   LOGIC_VERSION, now_utc, r["ticker"]))
        n += 1
    c.commit()
    return n


def _i(v):
    try: return int(v)
    except (TypeError, ValueError): return None

def _f(v):
    try: return float(v)
    except (TypeError, ValueError): return None


def due_tickers(c, limit, now_ts, ttl_days=None):
    """Tickers needing (re)processing: pending, logic-version mismatch, or past their TTL.
    Largest market cap first. now_ts is a unix timestamp passed in (scripts can't call time)."""
    ttl = ttl_days or TTL_DAYS
    rows = c.execute("SELECT * FROM tickers ORDER BY market_cap DESC").fetchall()
    out = []
    for r in rows:
        if r["status"] in (None, "pending") or r["logic_version"] != LOGIC_VERSION:
            out.append(r["ticker"])
        elif r["last_processed_utc"]:
            age_days = (now_ts - _parse_ts(r["last_processed_utc"])) / 86400.0
            if age_days >= ttl.get(r["effective_bucket"] or r["screen_bucket"], DEFAULT_TTL):
                out.append(r["ticker"])
        if len(out) >= limit:
            break
    return out


def _parse_ts(s):
    # stored as "YYYY-MM-DDTHH:MM:SSZ" or epoch; tolerate both
    try:
        return float(s)
    except (TypeError, ValueError):
        pass
    import datetime
    try:
        return datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
    except Exception:
        return 0.0


def upsert_result(c, row, now_utc):
    status = "skip" if str(row.get("bucket", "")).startswith("SKIP") else (
        "error" if row.get("verdict") == "ERROR" else "done")
    c.execute("""UPDATE tickers SET market_cap=?, sector=?, status=?, screen_bucket=?, effective_bucket=?,
                 distress_type=?, verdict=?, api_distress=?, api_fraud=?, api_high_short=?,
                 api_recent_raise=?, short_dtc=?, edgar_gc=?, edgar_mw=?, edgar_cov=?,
                 reasons=?, fraud_reasons=?, effective_reason=?,
                 note=?, logic_version=?, last_processed_utc=?, attempts=COALESCE(attempts,0)+1
                 WHERE ticker=?""",
              (_f(row.get("market_cap")), row.get("sector"), status, row.get("bucket"),
               row.get("effective_bucket"), row.get("distress_type"), row.get("verdict"),
               _i(row.get("api_distress")), _i(row.get("api_fraud")), _i(row.get("api_high_short")),
               _i(row.get("api_recent_raise")), _f(row.get("short_dtc")),
               _i(row.get("edgar_gc")), _i(row.get("edgar_mw")), _i(row.get("edgar_cov")),
               row.get("reasons"), row.get("fraud_reasons"), row.get("effective_reason"),
               row.get("note"), LOGIC_VERSION, now_utc, row["ticker"]))
    c.commit()


def stats(c):
    from collections import Counter
    rows = c.execute("SELECT status, screen_bucket, effective_bucket, logic_version, last_processed_utc FROM tickers").fetchall()
    st = Counter(r["status"] for r in rows)
    eb = Counter(r["effective_bucket"] for r in rows if r["status"] == "done")
    stale_ver = sum(1 for r in rows if r["logic_version"] != LOGIC_VERSION)
    return {"total": len(rows), "status": dict(st), "effective_bucket": dict(eb),
            "logic_version_mismatch": stale_ver, "current_version": LOGIC_VERSION}


def main():
    import datetime
    now_utc = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    a = sys.argv[1:]
    if not a or a[0] == "init":
        c = init_db()
        seeded = seed_universe(c)
        imported = import_ledger(c, now_utc)
        print(f"init: seeded {seeded} new tickers, imported {imported} ledger rows")
        print("stats:", json.dumps(stats(c), indent=2))
    elif a[0] == "stats":
        print(json.dumps(stats(conn()), indent=2))
    elif a[0] == "due":
        import time as _t
        n = int(a[1]) if len(a) > 1 else 20
        d = due_tickers(conn(), n, _t.time())
        print(f"{len(d)} due (showing {n}):", d)


if __name__ == "__main__":
    main()
