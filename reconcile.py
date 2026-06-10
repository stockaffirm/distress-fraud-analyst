#!/usr/bin/env python3
"""
reconcile.py TICKER -- single-ticker reconciliation against Morningstar.

The per-ticker loop instrument: shows MY valuation vs Morningstar's for ONE
ticker, and reverse-solves WHICH assumption explains the gap, so calibration is
targeted (not guesswork). Use it to drive one name to a match before the next.

  python3 reconcile.py AAPL          # uses cached MS pull (or fetches live)
  python3 reconcile.py AAPL --live   # force a fresh logged-in Morningstar pull

Reads MS from ms_cache/TICKER.json; falls back to a one-off live fetch.
"""
import os, sys, json, re, subprocess
from data_loader import load_context, load_fundamentals, financial_history
from valuation import analyze, derive_economics, compute_wacc
from valuation import _equity_value, TERMINAL_GROWTH, _clamp

HERE = os.path.dirname(__file__)
MS_CACHE = os.path.join(HERE, "ms_cache")
FETCH = "/Users/prasadmenon/Claude/InvestmentHub/fetch_one.py"
# also look at the fresh single pulls written during this session
EXTRA_MS = ["/Users/prasadmenon/Claude/InvestmentHub/aapl_ms.json"]


def get_ms(ticker, live=False):
    cache = os.path.join(MS_CACHE, f"{ticker}.json")
    if not live and os.path.exists(cache):
        return json.load(open(cache))
    if not live:
        for p in EXTRA_MS:
            if os.path.exists(p):
                try:
                    d = json.load(open(p)) if p.endswith(".json") else None
                except Exception:
                    d = None
                # aapl_ms.json holds log lines + final JSON; handle both
                if d is None:
                    last = [l for l in open(p).read().splitlines() if l.strip()]
                    try:
                        d = json.loads(last[-1])
                    except Exception:
                        d = None
                if d and d.get("ticker", "").upper() == ticker:
                    return d
    # live fetch
    p = subprocess.run(["python3.11", FETCH, ticker, "0"],
                       capture_output=True, text=True, timeout=180)
    last = [l for l in p.stdout.splitlines() if l.strip()]
    d = json.loads(last[-1])
    os.makedirs(MS_CACHE, exist_ok=True)
    json.dump(d, open(cache, "w"))
    return d


def ms_fv(d):
    m = re.search(r"[\d.]+", str(d.get("fair_value"))) if d.get("fair_value") else None
    return float(m.group()) if m else None


def solve_for_target(ticker, ctx, hist, target_equity, knob):
    """Reverse-solve the assumption value (growth or mature margin) that makes
    our equity value == target_equity, holding the rest of the model fixed."""
    yrs, norm = derive_economics(hist)
    ctx2 = dict(ctx); ctx2["_yrs"] = yrs
    res = analyze(ticker, dict(ctx, _yrs=None) if False else ctx, hist)  # full assumptions
    v = res["valuation"]
    # reconstruct fixed inputs from the live model
    from valuation import compute_wacc as _cw
    wacc = v["wacc"]
    rev0 = yrs[0]["revenue"]; tax = yrs[0]["tax_rate"]
    net_debt = (norm["latest_debt"] or 0) - (norm["latest_cash"] or 0)
    fade_n = v["fade_years"]; moat = res["moat"]; explicit_n = 8 if v["g1"] >= 0.30 else 5
    margin_start = v["target_margin"]  # approx; ramp handled inside
    roic_norm = v["roic_norm"]
    shares = norm["latest_shares"]
    if not shares:
        return None
    target_eq = target_equity
    lo, hi = (-0.10, 0.60) if knob == "growth" else (0.02, 0.60)
    for _ in range(70):
        mid = (lo + hi) / 2
        if knob == "growth":
            _, eqv, *_ = _equity_value(rev0, margin_start, v["target_margin"], 1.0, tax,
                                       roic_norm, wacc, moat, mid, fade_n, net_debt,
                                       explicit_n=explicit_n)
        else:  # mature margin
            _, eqv, *_ = _equity_value(rev0, mid, mid, 1.0, tax, roic_norm, wacc, moat,
                                       v["g1"], fade_n, net_debt, explicit_n=explicit_n)
        if eqv > target_eq:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def main():
    args = sys.argv[1:]
    live = "--live" in args
    args = [a for a in args if a != "--live"]
    ticker = args[0].upper()

    d = get_ms(ticker, live=live)
    msf = ms_fv(d)
    ctx = load_context(ticker); fund = load_fundamentals(ticker)
    hist = financial_history(fund)
    res = analyze(ticker, ctx, hist)
    v = res["valuation"]; n = res["norm"]
    myf = v["fv_per_share"]
    shares = n["latest_shares"]

    print(f"\n===== RECONCILE {ticker}  ({ctx['sector']}) =====")
    print(f"  MORNINGSTAR : FV ${msf}  moat {d.get('moat')}  uncert {d.get('uncertainty')}  "
          f"star {d.get('star_rating')}  capalloc {d.get('capital_allocation')}")
    print(f"  MINE        : FV ${myf:.2f}  moat {res['moat']}  uncert {res['uncertainty']}  "
          f"star {res['stars']}" if myf else f"  MINE: FV n/a")
    if msf and myf:
        print(f"  RATIO mine/ms = {myf/msf:.2f}   ({'MATCH' if 0.85<=myf/msf<=1.18 else 'GAP'})")
    print(f"\n  MY ASSUMPTIONS:")
    print(f"    WACC {v['wacc']*100:.1f}%  (beta {v['beta']:.2f})   fade {v['fade_years']}y  moat {res['moat']}")
    print(f"    stage-1 growth {v['g1']*100:.1f}%   mature op margin {v['target_margin']*100:.1f}%")
    print(f"    normalized ROIC {v['roic_norm']*100:.1f}%   terminal {v['roic_terminal']*100:.1f}%")
    print(f"    10y rev CAGR {(n['rev_cagr_5'] or 0)*100:.1f}%  recent op margin "
          f"{(n['opm_recent'] or 0)*100:.1f}%  gross margin {(n['gm_median'] or 0)*100:.0f}%")

    if msf and shares:
        target_eq = msf * shares
        g_needed = solve_for_target(ticker, ctx, hist, target_eq, "growth")
        m_needed = solve_for_target(ticker, ctx, hist, target_eq, "margin")
        print(f"\n  TO MATCH MORNINGSTAR (${msf}, equity ${target_eq/1e9:.0f}B) I'd need ONE of:")
        if g_needed is not None:
            print(f"    - stage-1 growth = {g_needed*100:.1f}%   (currently {v['g1']*100:.1f}%)")
        if m_needed is not None:
            print(f"    - mature op margin = {m_needed*100:.1f}%   (currently {v['target_margin']*100:.1f}%)")
        print("  -> if the 'needed' value is realistic, that dial is mis-set (structural);")
        print("     if it's absurd, MS is pricing something fundamentals can't see (record override).")


if __name__ == "__main__":
    main()
