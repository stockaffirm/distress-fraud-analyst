#!/usr/bin/env python3
"""
value_with.py TICKER [GROWTH] [MARGIN] -- compute fair value under a trial
assumption set WITHOUT touching analyst_overrides.csv. For workflow workers to
test a forward growth / mature margin and read back the resulting fair value.

  python3 value_with.py NKE              # baseline (current overrides apply)
  python3 value_with.py NKE 0.04 0.14    # trial: 4% growth, 14% mature margin

Prints one JSON line: fair value, moat, star, uncertainty, out-of-model flag,
plus Morningstar FV if cached. Exit 0.
"""
import sys, json, os, re
import valuation as V
from data_loader import load_context, load_fundamentals, financial_history

MS_CACHE = os.path.dirname(__file__) + "/ms_cache"
MS_LOCAL = "/Users/prasadmenon/Claude/InvestmentHub/morningstar_data.json"


def ms_fv(t):
    p = f"{MS_CACHE}/{t}.json"
    d = None
    if os.path.exists(p):
        d = json.load(open(p))
    else:
        try:
            d = json.load(open(MS_LOCAL)).get(t)
        except Exception:
            d = None
    if not d:
        return None, None, None
    m = re.search(r"[\d.]+", str(d.get("fair_value"))) if d.get("fair_value") else None
    return (float(m.group()) if m else None), d.get("moat"), d.get("star_rating")


def main():
    t = sys.argv[1].upper()
    g = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] not in ("-", "none") else None
    m = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] not in ("-", "none") else None
    ctx = load_context(t); fund = load_fundamentals(t)
    if not ctx or not fund:
        print(json.dumps({"ticker": t, "error": "no fundamentals/context"})); return
    hist = financial_history(fund)
    if len(hist) < 3:
        print(json.dumps({"ticker": t, "error": "<3y history"})); return
    if g is not None or m is not None:
        V.RUNTIME_OVERRIDES[t] = {"g1": g, "target_margin": m}
    res = V.analyze(t, ctx, hist)
    V.RUNTIME_OVERRIDES.pop(t, None)
    v = res["valuation"]
    mfv, mmoat, mstar = ms_fv(t)
    out = {
        "ticker": t, "sector": ctx["sector"], "mcap_B": round((ctx["market_cap"] or 0) / 1e9, 1),
        "my_fv": round(v["fv_per_share"], 2) if v["fv_per_share"] else None,
        "g1": round(v["g1"], 3), "mature_margin": round(v["target_margin"], 3),
        "moat": res["moat"], "star": res["stars"], "uncertainty": res["uncertainty"],
        "dcf_applicable": res["dcf_applicable"], "out_of_model": res["out_of_model"],
        "ms_fv": mfv, "ms_moat": mmoat, "ms_star": mstar,
        "ratio_vs_ms": round(v["fv_per_share"] / mfv, 2) if (v["fv_per_share"] and mfv) else None,
        "rev_cagr_5": round(res["norm"]["rev_cagr_5"] or 0, 3),
        "opm_recent": round(res["norm"]["opm_recent"] or 0, 3),
        "gross_margin": round(res["norm"]["gm_median"] or 0, 3),
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
