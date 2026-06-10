#!/usr/bin/env python3
"""
validate_vs_morningstar.py -- ground-truth the analyst agent against REAL
Morningstar fair values (scraped, logged-in) from InvestmentHub.

For every ticker Morningstar covers locally:
  - run our agent
  - compare FAIR VALUE / SHARE, ECONOMIC MOAT, STAR rating
  - report per-name error + population bias (are we systematically high/low?)

This is the per-ticker validation loop the calibration is driven by.

  python3 validate_vs_morningstar.py
"""
import os, json, statistics, re
from data_loader import load_fundamentals, load_context, financial_history
from valuation import analyze

MS_FILE = "/Users/prasadmenon/Claude/InvestmentHub/morningstar_data.json"
MOAT_RANK = {"None": 0, "Narrow": 1, "Wide": 2}


def load_ms():
    d = json.load(open(MS_FILE))
    items = d if all(isinstance(v, dict) for v in d.values()) else d.get("data", d)
    out = {}
    for t, r in items.items():
        fv = r.get("fair_value")
        m = re.search(r"[\d.]+", str(fv)) if fv else None
        out[t.upper()] = {
            "ms_fv": float(m.group()) if m else None,
            "ms_moat": r.get("moat"),
            "ms_star": r.get("star_rating"),
            "ms_unc": r.get("uncertainty"),
        }
    return out


def main():
    ms = load_ms()
    rows = []
    for t, m in sorted(ms.items()):
        if m["ms_fv"] is None:
            continue
        fund = load_fundamentals(t)
        ctx = load_context(t)
        if not fund or not ctx:
            continue
        hist = financial_history(fund)
        if len(hist) < 3:
            continue
        res = analyze(t, ctx, hist)
        v = res["valuation"]
        my_fv = v["fv_per_share"]
        ratio = (my_fv / m["ms_fv"]) if (my_fv and m["ms_fv"]) else None
        rows.append({
            "t": t, "sector": ctx["sector"],
            "dcf_ok": res["dcf_applicable"],
            "my_fv": my_fv, "ms_fv": m["ms_fv"],
            "ratio": ratio,
            "my_moat": res["moat"], "ms_moat": m["ms_moat"],
            "my_star": res["stars"], "ms_star": m["ms_star"],
        })

    # ---- report -----------------------------------------------------------
    print(f"\n{'TKR':5} {'sec':22} {'myFV':>9} {'msFV':>9} {'my/ms':>6}  "
          f"{'myMoat':7}/{'msMoat':7} {'my*':>3}/{'ms*':>3}")
    print("-" * 86)
    valid = [r for r in rows if r["dcf_ok"]]
    for r in rows:
        flag = "" if r["dcf_ok"] else " (DCF-NA fin.)"
        mo = "✓" if r["my_moat"] == r["ms_moat"] else "✗"
        print(f"{r['t']:5} {r['sector'][:22]:22} "
              f"{(r['my_fv'] or 0):9.2f} {r['ms_fv']:9.2f} "
              f"{(r['ratio'] or 0):6.2f}  "
              f"{r['my_moat']:7}/{str(r['ms_moat']):7}{mo} "
              f"{str(r['my_star']):>3}/{str(r['ms_star']):>3}{flag}")

    ratios = [r["ratio"] for r in valid if r["ratio"]]
    if ratios:
        print("\n--- FAIR-VALUE/SHARE accuracy (non-financial) ---")
        print(f"  my/ms ratio: median {statistics.median(ratios):.2f}  "
              f"mean {statistics.mean(ratios):.2f}  "
              f"min {min(ratios):.2f}  max {max(ratios):.2f}")
        within30 = sum(1 for x in ratios if 0.7 <= x <= 1.43)
        print(f"  within ±30% of Morningstar: {within30}/{len(ratios)} "
              f"({within30/len(ratios)*100:.0f}%)")
        med = statistics.median(ratios)
        bias = ("we are LOW vs MS (too bearish)" if med < 0.85 else
                "we are HIGH vs MS (too bullish)" if med > 1.15 else "well centered")
        print(f"  -> population bias: {bias}")

    moat_match = sum(1 for r in rows if r["my_moat"] == r["ms_moat"])
    print(f"\n--- MOAT agreement: {moat_match}/{len(rows)} "
          f"({moat_match/len(rows)*100:.0f}%) ---")
    # moat confusion
    off = [(r["t"], r["my_moat"], r["ms_moat"]) for r in rows if r["my_moat"] != r["ms_moat"]]
    if off:
        print("  mismatches (ours/MS):", ", ".join(f"{t}:{a}/{b}" for t, a, b in off))

    stars = [(r["my_star"], r["ms_star"]) for r in valid if r["my_star"] and r["ms_star"]]
    if stars:
        exact = sum(1 for a, b in stars if a == b)
        within1 = sum(1 for a, b in stars if abs(a - b) <= 1)
        print(f"\n--- STAR rating: exact {exact}/{len(stars)}, "
              f"within±1 {within1}/{len(stars)} ---")

    # save ledger
    p = os.path.join(os.path.dirname(__file__), "MS_VALIDATION.csv")
    import csv
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\n[saved {p}]")


if __name__ == "__main__":
    main()
