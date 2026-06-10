#!/usr/bin/env python3
"""
calibrate.py -- SEQUENTIAL, one-ticker-at-a-time calibration loop with DIRECT APIs.

For each ticker (largest market cap first), it:
  1. re-screens LIVE  (distress_screen.screen on cached fundamentals + cache news)
  2. pulls DIRECT-API ground truth (massive_api.event_scan: live news events,
     short interest / days-to-cover, recent capital raises)
  3. compares the bucket to the API evidence -> a validation VERDICT
  4. appends the result to CALIBRATION_LEDGER.csv and checkpoints CALIBRATION_PROGRESS.json

Resumable: it skips tickers already in the ledger, so any agent can stop/restart and
continue from where it left off. The human-in-the-loop calibration (reading the
disagreements, changing distress_screen.py, logging the why in CALIBRATION_LOG.md) is
driven from the verdicts this surfaces -- see CALIBRATION_LOG.md for the protocol.

  python3 calibrate.py --n 50            # process the next 50 undone tickers
  python3 calibrate.py --review          # summarise verdicts + disagreements so far
  python3 calibrate.py --ticker NVAX     # run one ticker verbosely (no ledger write)
"""
import os, sys, csv, json, time, traceback
from data_loader import _recs, load_fundamentals, load_context, full_history
from distress_screen import screen
try:
    from distress_news import scan_ticker
except Exception:
    scan_ticker = None
from massive_api import event_scan

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "CALIBRATION_LEDGER.csv")
PROGRESS = os.path.join(HERE, "CALIBRATION_PROGRESS.json")
COLS = ["ticker", "sector", "market_cap", "bucket", "effective_bucket", "distress_type",
        "fraud", "fraud_watchlist", "verdict", "api_distress", "api_fraud", "api_high_short",
        "api_recent_raise", "short_dtc", "n_news", "n_bk_events", "n_fraud_events",
        "effective_reason", "note"]


def effective_bucket(screen_bucket, verdict):
    """FINAL per-ticker answer = fundamentals screen OVERLAID with direct-API evidence.
    The screen can't see a Gotham short report or a just-closed equity raise; this can."""
    if verdict == "CORROBORATED":
        return "AVOID", "API event/short-interest confirms the fundamentals AVOID"
    if verdict in ("OVERFLAG_recent_raise", "OVERFLAG_review"):
        return "WATCH", "downgraded from AVOID — recent capital raise extends runway / no event found"
    if verdict == "UNDERFLAG_fraud_event":
        return ("AVOID" if screen_bucket == "AVOID" else "WATCH"), "promoted — ≥2 live fraud/SEC/short-seller news articles"
    if verdict == "UNDERFLAG_distress_event":
        return ("AVOID" if screen_bucket in ("AVOID", "WATCH", "DISTRESSED-RECOVERABLE") else "WATCH"), \
               "promoted — ≥2 live distress (going-concern/Ch11/default) news articles"
    if verdict == "NEWS_NOTE":
        return screen_bucket, "single news mention (kept screen bucket; investigate)"
    return screen_bucket, ""


def _mc(ctx):
    return (ctx or {}).get("market_cap") or 0.0


def ordered_tickers():
    """All universe tickers, largest market cap first (most consequential first)."""
    recs = _recs()
    def mc(t):
        v = recs[t].get("market_cap")
        try:
            return float(v) if v not in (None, "", "None") else 0.0
        except (TypeError, ValueError):
            return 0.0
    return sorted(recs.keys(), key=lambda t: -mc(t))


def done_set():
    if not os.path.exists(LEDGER):
        return set()
    return {r["ticker"] for r in csv.DictReader(open(LEDGER))}


def verdict_for(res, e):
    """Compare the screen bucket to the direct-API evidence."""
    bucket = res["bucket"]
    dt = res.get("distress_type")
    if bucket == "AVOID" and res["fraud"]:
        if e["api_fraud"] or e["api_high_short"]:
            return "CORROBORATED", "API fraud/short-interest confirms"
        if e["api_recent_raise"] and not e["api_fraud"]:
            return "OVERFLAG_review", "recent raise, no fraud event in news"
        return "AVOID_unconfirmed", "no API fraud/short signal (coverage may be thin)"
    if bucket == "AVOID":  # bankruptcy
        if e["api_distress"] or e["api_high_short"]:
            return "CORROBORATED", "API distress/short-interest confirms"
        if dt == "cash_burn" and e["api_recent_raise"]:
            return "OVERFLAG_recent_raise", "recent capital raise extends runway"
        return "AVOID_unconfirmed", "no API distress/short signal (coverage may be thin)"
    # CLEAR / WATCH / DISTRESSED-RECOVERABLE
    nbk, nfr = len(e["bankruptcy_events"]), len(e["fraud_events"])
    # >=2 corroborating articles = a real event the screen missed (actionable);
    # a single mention = a news note (surface, but not a screen error -- e.g. APP's
    # one short-report article while it stays fundamentally clean & profitable).
    if nbk >= 2:
        return "UNDERFLAG_distress_event", f"{nbk} live news articles show a distress event the screen missed"
    if nfr >= 2:
        return "UNDERFLAG_fraud_event", f"{nfr} live news articles show a fraud/SEC/restatement event the screen missed"
    if (nbk == 1 or nfr == 1):
        return "NEWS_NOTE", "single news mention of distress/fraud (investigate; not a screen error)"
    # NB: short interest alone does NOT create a flag -- days-to-cover is too noisy for
    # healthy low-volume names (REITs/banks/insurers). It only CORROBORATES an AVOID above.
    return "AGREE", ""


def process_one(ticker, write=True):
    ctx = load_context(ticker)
    fund = load_fundamentals(ticker)
    if not ctx or not fund:
        return {"ticker": ticker, "sector": (ctx or {}).get("sector", ""), "market_cap": _mc(ctx),
                "bucket": "SKIP_no_data", "verdict": "SKIP", "note": "no cached fundamentals/context"}
    hist = full_history(fund)
    if len(hist) < 2 or hist[0].get("revenue") in (None, 0):
        return {"ticker": ticker, "sector": ctx.get("sector", ""), "market_cap": _mc(ctx),
                "bucket": "SKIP_lt2y", "verdict": "SKIP", "note": "<2y data"}
    news = scan_ticker(ticker) if scan_ticker else None
    res = screen(ticker, ctx, hist, news=news)
    e = event_scan(ticker)
    verdict, note = verdict_for(res, e)
    eff_bucket, eff_reason = effective_bucket(res["bucket"], verdict)
    top = ""
    if e["bankruptcy_events"]:
        top = "BK:" + e["bankruptcy_events"][0]["title"]
    elif e["fraud_events"]:
        top = "FR:" + e["fraud_events"][0]["title"]
    elif e["capital_raises"]:
        top = "RAISE:" + e["capital_raises"][0]["title"]
    return {
        "ticker": ticker, "sector": res["sector"], "market_cap": res["market_cap"],
        "bucket": res["bucket"], "effective_bucket": eff_bucket,
        "distress_type": res.get("distress_type") or "",
        "fraud": int(res["fraud"]), "fraud_watchlist": int(bool(res.get("fraud_watchlist"))),
        "verdict": verdict, "api_distress": int(e["api_distress"]), "api_fraud": int(e["api_fraud"]),
        "api_high_short": int(e["api_high_short"]), "api_recent_raise": int(e["api_recent_raise"]),
        "short_dtc": e["short_days_to_cover"], "n_news": e["n_news"],
        "n_bk_events": len(e["bankruptcy_events"]), "n_fraud_events": len(e["fraud_events"]),
        "effective_reason": eff_reason,
        "note": (note + (" | " + top if top else ""))[:240],
        # forwarded for LLM investigation layer
        "growth_stage":            res.get("growth_stage", "UNKNOWN"),
        "growth_cagr_3y":          res.get("growth_cagr_3y"),
        "growth_cagr_1y":          res.get("growth_cagr_1y"),
        "beneish_components":      res.get("beneish_components") or {},
        "beneish_growth_artifact": bool(res.get("beneish_growth_artifact")),
    }


def run(n=50, throttle=0.1):
    done = done_set()
    new = not os.path.exists(LEDGER)
    order = ordered_tickers()
    todo = [t for t in order if t not in done]
    print(f"universe={len(order)} done={len(done)} remaining={len(todo)}  processing next {min(n, len(todo))}")
    f = open(LEDGER, "a", newline="")
    w = csv.DictWriter(f, fieldnames=COLS)
    if new:
        w.writeheader()
    processed = 0
    from collections import Counter
    vc = Counter()
    for t in todo[:n]:
        try:
            row = process_one(t)
        except Exception:
            row = {"ticker": t, "bucket": "ERROR", "verdict": "ERROR",
                   "note": traceback.format_exc().splitlines()[-1][:200]}
        w.writerow({k: row.get(k) for k in COLS})
        f.flush()
        vc[row.get("verdict")] += 1
        processed += 1
        # surface actionable disagreements live
        if row.get("verdict") in ("UNDERFLAG_distress_event", "UNDERFLAG_fraud_event",
                                   "OVERFLAG_recent_raise", "OVERFLAG_review"):
            mc = row.get("market_cap") or 0
            print(f"  ⚑ {row['ticker']:6} {('$%.1fB'%(mc/1e9)) if mc>1e9 else ('$%.0fM'%(mc/1e6)):>8} "
                  f"{row['bucket']:24} {row['verdict']:24} {row['note'][:90]}")
        time.sleep(throttle)
    json.dump({"done": len(done) + processed, "universe": len(order),
               "remaining": len(todo) - processed}, open(PROGRESS, "w"), indent=2)
    print(f"\nverdicts this batch: {dict(vc)}")
    print(f"progress: {len(done)+processed}/{len(order)}  ({len(todo)-processed} remaining)")


def review():
    if not os.path.exists(LEDGER):
        print("no ledger yet"); return
    rows = list(csv.DictReader(open(LEDGER)))
    from collections import Counter
    print(f"=== CALIBRATION LEDGER: {len(rows)} tickers processed ===")
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    print("buckets :", dict(Counter(r["bucket"] for r in rows)))
    act = [r for r in rows if r["verdict"] in ("UNDERFLAG_distress_event", "UNDERFLAG_fraud_event",
                                               "OVERFLAG_recent_raise", "OVERFLAG_review")]
    print(f"\n--- {len(act)} actionable disagreements (calibration candidates) ---")
    def mc(r):
        try: return float(r["market_cap"])
        except: return 0.0
    for r in sorted(act, key=lambda r: -mc(r)):
        m = mc(r)
        print(f"  {r['ticker']:6} {('$%.1fB'%(m/1e9)) if m>1e9 else ('$%.0fM'%(m/1e6)):>8} "
              f"{r['bucket']:22} {r['verdict']:24} {r['note'][:88]}")


def main():
    a = sys.argv[1:]
    if "--review" in a:
        return review()
    if "--ticker" in a:
        t = a[a.index("--ticker") + 1].upper()
        print(json.dumps(process_one(t, write=False), indent=2, default=str))
        return
    n = int(a[a.index("--n") + 1]) if "--n" in a else 50
    run(n=n)


if __name__ == "__main__":
    main()
