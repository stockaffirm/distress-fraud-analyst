#!/usr/bin/env python3
"""
value_batch.py -- batch valuer for the workflow workers (ONE process per batch,
so the zip-index is built once, not per ticker).

  python3 value_batch.py --range 0 25         # baseline worksheet for universe[0:25]
  python3 value_batch.py --tickers NKE KO AAPL # baseline for an explicit list
  python3 value_batch.py --overrides "NKE:0.04:0.14,KO:0.06:0.30"  # FV under trial overrides

Emits one JSON line per ticker (same shape as value_with.py). Unknown/!data tickers
emit an {error} line. Exit 0.
"""
import sys, json, os, re
import valuation as V
from data_loader import load_context, load_fundamentals, financial_history

HERE = os.path.dirname(__file__)
MS_CACHE = HERE + "/ms_cache"
MS_LOCAL = "/Users/prasadmenon/Claude/InvestmentHub/morningstar_data.json"
_ms_local = None


def ms_fv(t):
    global _ms_local
    p = f"{MS_CACHE}/{t}.json"
    d = None
    if os.path.exists(p):
        try: d = json.load(open(p))
        except Exception: d = None
    if d is None:
        if _ms_local is None:
            try: _ms_local = json.load(open(MS_LOCAL))
            except Exception: _ms_local = {}
        d = _ms_local.get(t)
    if not d:
        return None, None, None
    m = re.search(r"[\d.]+", str(d.get("fair_value"))) if d.get("fair_value") else None
    return (float(m.group()) if m else None), d.get("moat"), d.get("star_rating")


def value(t, g=None, m=None, u=None):
    ctx = load_context(t); fund = load_fundamentals(t)
    if not ctx or not fund:
        return {"ticker": t, "error": "no fundamentals/context"}
    hist = financial_history(fund)
    if len(hist) < 3:
        return {"ticker": t, "error": "<3y history"}
    if g is not None or m is not None or u is not None:
        V.RUNTIME_OVERRIDES[t] = {"g1": g, "target_margin": m, "uncertainty": u}
    res = V.analyze(t, ctx, hist)
    V.RUNTIME_OVERRIDES.pop(t, None)
    v = res["valuation"]; n = res["norm"]
    mfv, mmoat, mstar = ms_fv(t)
    return {
        "ticker": t, "sector": ctx["sector"], "mcap_B": round((ctx["market_cap"] or 0)/1e9, 1),
        "my_fv": round(v["fv_per_share"], 2) if v["fv_per_share"] else None,
        "g1": round(v["g1"], 3), "mature_margin": round(v["target_margin"], 3),
        "moat": res["moat"], "moat_trend": res["moat_trend"], "star": res["stars"],
        "uncertainty": res["uncertainty"], "dcf_applicable": res["dcf_applicable"],
        "out_of_model": res["out_of_model"], "oom_reasons": res["out_of_model_reasons"],
        "ms_fv": mfv, "ms_moat": mmoat, "ms_star": mstar,
        "ratio_vs_ms": round(v["fv_per_share"]/mfv, 2) if (v["fv_per_share"] and mfv) else None,
        "rev_cagr_5": round(n["rev_cagr_5"] or 0, 3), "rev_cagr_3": round(n["rev_cagr_3"] or 0, 3),
        "opm_recent": round(n["opm_recent"] or 0, 3), "opm_peak": round(n["opm_peak"] or 0, 3),
        "gross_margin": round(n["gm_median"] or 0, 3), "roic_median": round(n["roic_median"] or 0, 3),
    }


def main():
    a = sys.argv[1:]
    tickers = []
    if a and a[0] == "--range":
        lo, hi = int(a[1]), int(a[2])
        uni = [x.strip() for x in open(HERE + "/universe_1500.txt") if x.strip()]
        for t in uni[lo:hi]:
            print(json.dumps(value(t.upper())))
        return
    if a and a[0] == "--overrides":
        for spec in a[1].split(","):
            if not spec.strip(): continue
            parts = spec.split(":")
            t = parts[0].upper()
            g = float(parts[1]) if len(parts) > 1 and parts[1] not in ("", "-") else None
            m = float(parts[2]) if len(parts) > 2 and parts[2] not in ("", "-") else None
            u = parts[3].strip() if len(parts) > 3 and parts[3].strip() not in ("", "-") else None
            print(json.dumps(value(t, g, m, u)))      # spec: TICKER:GROWTH:MARGIN:UNCERTAINTY
        return
    if a and a[0] == "--tickers":
        tickers = [x.upper() for x in a[1:]]
    else:
        tickers = [x.upper() for x in a]
    for t in tickers:
        print(json.dumps(value(t)))


if __name__ == "__main__":
    main()
