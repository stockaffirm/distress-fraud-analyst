#!/usr/bin/env python3
"""
live_validate.py -- fetch Morningstar fair values LIVE (logged-in scrape) and
validate the analyst agent against them, building a sector-stratified ground
truth set. Resumable: caches each fresh MS pull so an interrupted run continues.

  python3 live_validate.py                 # auto sector-stratified ~48 names
  python3 live_validate.py AAPL MSFT KO    # explicit tickers
  python3 live_validate.py --per 6         # N largest per sector

Each fresh Morningstar JSON -> ms_cache/TICKER.json ; ledger -> MS_VALIDATION_LIVE.csv
"""
import os, sys, json, csv, subprocess, re, statistics, time
from data_loader import load_context, load_fundamentals, financial_history, _recs
from valuation import analyze

HERE = os.path.dirname(__file__)
MS_CACHE = os.path.join(HERE, "ms_cache")
FETCH = "/Users/prasadmenon/Claude/InvestmentHub/fetch_one.py"
LEDGER = os.path.join(HERE, "MS_VALIDATION_LIVE.csv")
os.makedirs(MS_CACHE, exist_ok=True)


def stratified(per=4):
    """Largest `per` names per sector (MS coverage skews large-cap)."""
    bysec = {}
    for t, r in _recs().items():
        try:
            mc = float(r.get("market_cap") or 0)
        except ValueError:
            mc = 0
        bysec.setdefault(r.get("sector") or "Unknown", []).append((mc, t))
    out = []
    for sec, lst in bysec.items():
        if sec in ("Unknown",):
            continue
        lst.sort(reverse=True)
        out += [t for _, t in lst[:per]]
    return out


def fetch_live(ticker, worker=0):
    """Run the logged-in scraper for one ticker; return parsed MS dict (cached)."""
    cache = os.path.join(MS_CACHE, f"{ticker}.json")
    if os.path.exists(cache):
        try:
            return json.load(open(cache))
        except json.JSONDecodeError:
            pass
    try:
        p = subprocess.run(["python3.11", FETCH, ticker, str(worker)],
                           capture_output=True, text=True, timeout=180)
        last = [l for l in p.stdout.splitlines() if l.strip()]
        if not last:
            return {"ticker": ticker, "error": "no stdout"}
        data = json.loads(last[-1])           # contract: JSON is the last stdout line
        json.dump(data, open(cache, "w"))
        return data
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {"ticker": ticker, "error": str(e)}


def parse_ms(d):
    fv = d.get("fair_value")
    m = re.search(r"[\d.]+", str(fv)) if fv else None
    return {"ms_fv": float(m.group()) if m else None,
            "ms_moat": d.get("moat"), "ms_star": d.get("star_rating"),
            "ms_unc": d.get("uncertainty")}


def run(tickers):
    rows = []
    for i, t in enumerate(tickers, 1):
        t = t.upper()
        print(f"[{i}/{len(tickers)}] {t} fetching live...", flush=True)
        d = fetch_live(t)
        if d.get("error"):
            print(f"   ! {t}: {d['error']}", flush=True)
            continue
        ms = parse_ms(d)
        ctx, fund = load_context(t), load_fundamentals(t)
        if not ctx or not fund:
            print(f"   ! {t}: no local fundamentals to value", flush=True)
            continue
        hist = financial_history(fund)
        if len(hist) < 3:
            continue
        res = analyze(t, ctx, hist)
        v = res["valuation"]
        ratio = (v["fv_per_share"] / ms["ms_fv"]) if (v["fv_per_share"] and ms["ms_fv"]) else None
        row = {"t": t, "sector": ctx["sector"], "dcf_ok": res["dcf_applicable"],
               "my_fv": round(v["fv_per_share"], 2) if v["fv_per_share"] else None,
               "ms_fv": ms["ms_fv"], "ratio": round(ratio, 3) if ratio else None,
               "my_moat": res["moat"], "ms_moat": ms["ms_moat"],
               "my_star": res["stars"], "ms_star": ms["ms_star"]}
        rows.append(row)
        mo = "OK" if row["my_moat"] == row["ms_moat"] else "x"
        print(f"   {t}: my {row['my_fv']} / ms {row['ms_fv']}  ratio {row['ratio']}  "
              f"moat {row['my_moat']}/{row['ms_moat']} {mo}  star {row['my_star']}/{row['ms_star']}",
              flush=True)
    return rows


def report(rows):
    with open(LEDGER, "w", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    valid = [r for r in rows if r["dcf_ok"] and r["ratio"]]
    ratios = [r["ratio"] for r in valid]
    print("\n===== LIVE VALIDATION SUMMARY =====")
    print(f"validated {len(rows)} names ({len(valid)} non-financial w/ ratio)")
    if ratios:
        within30 = sum(1 for x in ratios if 0.7 <= x <= 1.43)
        print(f"my/ms ratio: median {statistics.median(ratios):.2f} mean {statistics.mean(ratios):.2f} "
              f"| within +/-30%: {within30}/{len(ratios)} ({within30/len(ratios)*100:.0f}%)")
    mo = sum(1 for r in rows if r["my_moat"] == r["ms_moat"])
    print(f"moat agreement: {mo}/{len(rows)} ({mo/len(rows)*100:.0f}%)")
    st = [(r["my_star"], r["ms_star"]) for r in valid if r["my_star"] and r["ms_star"]]
    if st:
        w1 = sum(1 for a, b in st if abs(a - b) <= 1)
        print(f"star within +/-1: {w1}/{len(st)} ({w1/len(st)*100:.0f}%)")
    print(f"[ledger -> {LEDGER}]")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    per = 4
    if "--per" in args:
        i = args.index("--per"); per = int(args[i + 1]); del args[i:i + 2]
    tickers = args if args else stratified(per)
    print(f"validating {len(tickers)} tickers live\n")
    rows = run(tickers)
    report(rows)
