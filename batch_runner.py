#!/usr/bin/env python3
"""
batch_runner.py -- run the analyst-agent valuation across the full universe and
emit population diagnostics. This is the calibration harness: it tells us where
the model is SYSTEMATICALLY wrong (by sector, by size, by moat) so we fix
structural parameters instead of overfitting one stock at a time.

  python3 batch_runner.py            # all tickers in recommendations.csv
  python3 batch_runner.py 300        # first 300 (quick)

Outputs:
  FAIR_VALUE_ALL.csv     -- per-ticker valuation
  CALIBRATION_DIAGNOSTICS.md -- population biases to fix next
"""
import sys, os, csv, statistics
from data_loader import load_fundamentals, load_context, financial_history, _recs
from valuation import analyze

OUT_DIR = os.path.dirname(__file__)


def run(limit=None):
    tickers = list(_recs().keys())
    if limit:
        tickers = tickers[:limit]
    rows, errors = [], 0
    for t in tickers:
        try:
            fund = load_fundamentals(t)
            ctx = load_context(t)
            if not fund or not ctx:
                continue
            hist = financial_history(fund)
            if len(hist) < 3:
                continue
            res = analyze(t, ctx, hist)
            v = res["valuation"]
            rows.append({
                "ticker": t, "sector": ctx["sector"],
                "market_cap": ctx["market_cap"],
                "dcf_applicable": res["dcf_applicable"],
                "fair_value_equity": v["equity_value"],
                "fv_per_share": v["fv_per_share"],
                "price_to_fv": res["price_to_fv"],
                "stars": res["stars"],
                "moat": res["moat"], "moat_trend": res["moat_trend"],
                "uncertainty": res["uncertainty"],
                "implied_g": v["implied_g"], "base_g": v["g1"],
                "roic_median": res["norm"]["roic_median"],
                "wacc": v["wacc"],
                "engine_tier": ctx["engine_tier"],
                "engine_composite": ctx["engine_composite"],
                "rec_mean": ctx["rec_mean"],
            })
        except Exception as e:  # noqa
            errors += 1
            continue
    return rows, errors


def write_csv(rows):
    p = os.path.join(OUT_DIR, "FAIR_VALUE_ALL.csv")
    cols = ["ticker", "sector", "market_cap", "dcf_applicable", "fair_value_equity",
            "fv_per_share", "price_to_fv", "stars", "moat", "moat_trend",
            "uncertainty", "implied_g", "base_g", "roic_median", "wacc",
            "engine_tier", "engine_composite", "rec_mean"]
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def _dist(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "n/a"
    vals.sort()
    q = lambda p: vals[min(len(vals) - 1, int(p * len(vals)))]
    return (f"min {vals[0]:.2f} | p10 {q(.1):.2f} | median {q(.5):.2f} | "
            f"p90 {q(.9):.2f} | max {vals[-1]:.2f}")


def diagnostics(rows):
    L = ["# Calibration Diagnostics — Analyst Agent vs population\n"]
    L.append(f"Scored **{len(rows)}** tickers with usable fundamentals.\n")

    valid = [r for r in rows if r["dcf_applicable"] and r["price_to_fv"]]
    L.append(f"Enterprise-DCF-valid (non-financial): **{len(valid)}**\n")

    # star distribution -- the headline calibration signal
    L.append("## Star-rating distribution (1=overvalued .. 5=deep value)")
    from collections import Counter
    cs = Counter(r["stars"] for r in valid)
    tot = sum(cs.values()) or 1
    for s in (5, 4, 3, 2, 1):
        n = cs.get(s, 0)
        L.append(f"- {s}★: {n} ({n/tot*100:.0f}%)  {'█'*int(n/tot*40)}")
    skew = (cs.get(1, 0) + cs.get(2, 0)) / tot
    L.append(f"\n**Overvalued share (1-2★): {skew*100:.0f}%.** "
             f"A well-calibrated model centered on market ≈ ~40-50% here; "
             f"{'>>60% ⇒ model is systematically BEARISH (growth haircut/WACC too harsh).' if skew>0.6 else 'looks balanced.' if skew<0.55 else 'mild bearish tilt.'}\n")

    # price/FV distribution
    L.append("## price ÷ fair-value distribution")
    L.append(f"- all valid: {_dist([r['price_to_fv'] for r in valid])}")
    L.append("  (1.0 = fairly valued; >1 market above model; median far from 1.0 ⇒ bias)\n")

    # by sector
    L.append("## Median price/FV by sector  (systematic bias shows here)")
    bysec = {}
    for r in valid:
        bysec.setdefault(r["sector"], []).append(r["price_to_fv"])
    for sec, vs in sorted(bysec.items(), key=lambda kv: -statistics.median(kv[1])):
        L.append(f"- {sec}: median {statistics.median(vs):.2f}  (n={len(vs)})")
    L.append("")

    # moat distribution
    L.append("## Moat distribution")
    cm = Counter(r["moat"] for r in rows)
    for m in ("Wide", "Narrow", "None"):
        L.append(f"- {m}: {cm.get(m,0)} ({cm.get(m,0)/len(rows)*100:.0f}%)")
    L.append("\n_Morningstar coverage is ~10% Wide / ~40% Narrow / ~50% None. "
             "Large deviation ⇒ moat thresholds need tightening._\n")

    # implied vs base growth gap (reverse-DCF sanity)
    gaps = [r["implied_g"] - r["base_g"] for r in valid
            if r["implied_g"] is not None and r["base_g"] is not None]
    if gaps:
        L.append("## Reverse-DCF: market-implied minus model base growth")
        L.append(f"- {_dist(gaps)}")
        med = statistics.median(gaps)
        L.append(f"- median gap {med*100:+.1f}pp. {'Large positive ⇒ model base growth too LOW vs what market consistently prices (calibrate growth haircut up).' if med>0.03 else 'centered ⇒ growth assumption roughly right.'}\n")

    # agreement vs engine & street
    L.append("## Three-way agreement (where the value-add is)")
    def lab(r):  # analyst-agent label
        s = r["stars"]
        return "BUY" if s >= 4 else "HOLD" if s == 3 else "SELL"
    def street(r):
        rm = r["rec_mean"]
        return "BUY" if (rm and rm <= 2) else "SELL" if (rm and rm >= 3.5) else "HOLD" if rm else "n/a"
    agree_all = sum(1 for r in valid if lab(r) == r["engine_tier"][:3].replace("BUY","BUY").replace("HOL","HOLD").replace("SEL","SELL") )
    # simpler: count analyst BUY that engine SELLs and vice-versa
    a_buy_e_sell = sum(1 for r in valid if lab(r) == "BUY" and r["engine_tier"] == "SELL")
    a_sell_e_buy = sum(1 for r in valid if lab(r) == "SELL" and r["engine_tier"] == "BUY")
    L.append(f"- analyst-agent BUY while engine SELL: {a_buy_e_sell}")
    L.append(f"- analyst-agent SELL while engine BUY: {a_sell_e_buy}")
    L.append("  (these disagreements are the GAP-25 worklist — quality/price tension)\n")

    p = os.path.join(OUT_DIR, "CALIBRATION_DIAGNOSTICS.md")
    with open(p, "w") as f:
        f.write("\n".join(L) + "\n")
    return p, skew, (statistics.median(gaps) if gaps else None)


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows, errors = run(limit)
    csvp = write_csv(rows)
    diagp, skew, med_gap = diagnostics(rows)
    print(f"scored {len(rows)} tickers ({errors} errored/skipped)")
    print(f"-> {csvp}")
    print(f"-> {diagp}")
    print(f"overvalued(1-2*) share = {skew*100:.0f}% ; median implied-vs-base growth gap = "
          f"{(med_gap*100 if med_gap is not None else float('nan')):+.1f}pp")
