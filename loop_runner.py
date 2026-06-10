#!/usr/bin/env python3
"""
loop_runner.py -- the SELF-STARTING, resumable calibration runner (cron-callable).

Reads DUE tickers from the SQLite status table (state_db), processes each ONE BY ONE via
the direct-API per-ticker pipeline (calibrate.process_one), and writes results back. Time-
budgeted so a cron can call it every N minutes; it picks up exactly where it left off (state
is in the DB), so an accidental stop loses nothing. Idles (no-op) when nothing is due, and
re-activates automatically when rows pass their TTL (news refresh) or the logic_version bumps.

  python3 loop_runner.py --minutes 8         # process due tickers for up to 8 min, then exit
  python3 loop_runner.py --minutes 8 --once  # same, single pass (for cron)
  python3 loop_runner.py --export            # just rewrite CALIBRATION_LEDGER.csv from the DB

Designed to run head-less (no LLM, no interactive auth) -- ideal for a scheduled task.
"""
import os, sys, csv, time, datetime, traceback
import state_db as S
from calibrate import process_one

HERE = os.path.dirname(os.path.abspath(__file__))


def export_ledger(c):
    """Rewrite the human-readable CSV mirror from the DB (largest mcap first)."""
    rows = c.execute("SELECT * FROM tickers ORDER BY market_cap DESC").fetchall()
    cols = ["ticker", "sector", "market_cap", "bucket", "effective_bucket", "distress_type",
            "verdict", "status", "api_distress", "api_fraud", "api_high_short", "api_recent_raise",
            "short_dtc", "effective_reason", "note", "logic_version", "last_processed_utc"]
    with open(os.path.join(HERE, "CALIBRATION_LEDGER.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r["ticker"], r["sector"], r["market_cap"], r["screen_bucket"],
                        r["effective_bucket"], r["distress_type"], r["verdict"], r["status"],
                        r["api_distress"], r["api_fraud"], r["api_high_short"], r["api_recent_raise"],
                        r["short_dtc"], r["effective_reason"], r["note"], r["logic_version"],
                        r["last_processed_utc"]])


def run(minutes=8.0):
    c = S.init_db()                       # idempotent: ensures schema exists
    S.seed_universe(c)                    # pick up any newly-added tickers
    deadline = time.time() + minutes * 60
    processed, errors = 0, 0
    from collections import Counter
    vc = Counter()
    while time.time() < deadline:
        due = S.due_tickers(c, 20, time.time())
        if not due:
            break
        for t in due:
            if time.time() >= deadline:
                break
            now_utc = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                row = process_one(t)
            except Exception:
                row = {"ticker": t, "bucket": "ERROR", "verdict": "ERROR",
                       "note": traceback.format_exc().splitlines()[-1][:200]}
                errors += 1
            S.upsert_result(c, row, now_utc)
            vc[row.get("verdict")] += 1
            processed += 1
            if row.get("verdict") in ("UNDERFLAG_distress_event", "UNDERFLAG_fraud_event",
                                      "OVERFLAG_recent_raise", "OVERFLAG_review"):
                mc = row.get("market_cap") or 0
                print(f"  ⚑ {row['ticker']:6} {row.get('bucket'):22} -> {row.get('effective_bucket'):22} "
                      f"{row['verdict']:24} {str(row.get('note'))[:80]}")
            time.sleep(0.1)
    export_ledger(c)
    st = S.stats(c)
    due_left = len(S.due_tickers(c, 10**9, time.time()))
    print(f"\nprocessed {processed} ({errors} errors) this run; verdicts={dict(vc)}")
    print(f"status={st['status']}  due_remaining={due_left}  version={st['current_version']}")
    return due_left


def main():
    a = sys.argv[1:]
    if "--export" in a:
        export_ledger(S.init_db()); print("exported CALIBRATION_LEDGER.csv from DB"); return
    minutes = float(a[a.index("--minutes") + 1]) if "--minutes" in a else 8.0
    run(minutes=minutes)


if __name__ == "__main__":
    main()
