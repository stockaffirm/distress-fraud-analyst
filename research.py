#!/usr/bin/env python3
"""
research.py TICKER -- the analyst worksheet for working ONE name like a human.

Prints the 10-year trajectory (revenue, growth, gross/op margin, FCFF, ROIC) so I
can form an INDEPENDENT forward view, plus my current model output and Morningstar's
number for contrast. I read this, decide my forward growth/margin, write a verdict,
and enter the override.
"""
import sys, os, json, re
from data_loader import load_context, load_fundamentals, financial_history
from valuation import analyze, derive_economics

MS_CACHE = os.path.dirname(__file__) + "/ms_cache"


def ms_for(t):
    p = f"{MS_CACHE}/{t}.json"
    if os.path.exists(p):
        return json.load(open(p))
    local = json.load(open("/Users/prasadmenon/Claude/InvestmentHub/morningstar_data.json"))
    return local.get(t)


def main():
    t = sys.argv[1].upper()
    ctx = load_context(t); fund = load_fundamentals(t)
    yrs, norm = derive_economics(financial_history(fund))
    res = analyze(t, ctx, financial_history(fund)); v = res["valuation"]
    print(f"\n========== ANALYST WORKSHEET: {t} ({ctx['sector']}, mcap ${ctx['market_cap']/1e9:.0f}B) ==========")
    print(f"{'FY':>6} {'revenue':>12} {'growth':>8} {'gross%':>7} {'op%':>7} {'FCFF':>12} {'ROIC%':>7}")
    prev = None
    for y in yrs:
        g = (y['revenue']/prev - 1) if (prev and y['revenue']) else None
        prev = y['revenue']
        print(f"{y['fy']:>6} {y['revenue']/1e9:>11.1f}B {('%+.0f%%'%(g*100)) if g is not None else '   -':>8} "
              f"{(y['gross_margin'] or 0)*100:>6.0f}% {(y['op_margin'] or 0)*100:>6.0f}% "
              f"{(y['fcff']/1e9 if y['fcff'] else 0):>11.1f}B {(y['roic'] or 0)*100:>6.0f}%")
    print(f"\n  NORM: 5y CAGR {(norm['rev_cagr_5'] or 0)*100:.1f}%  3y CAGR {(norm['rev_cagr_3'] or 0)*100:.1f}%  "
          f"| op margin recent {(norm['opm_recent'] or 0)*100:.1f}% peak {(norm['opm_peak'] or 0)*100:.1f}% "
          f"| gross {(norm['gm_median'] or 0)*100:.0f}% | ROIC med {(norm['roic_median'] or 0)*100:.0f}%")
    print(f"\n  MY MODEL (baseline): FV ${v['fv_per_share'] and round(v['fv_per_share'],2)}  "
          f"g1 {v['g1']*100:.1f}%  mature margin {v['target_margin']*100:.1f}%  WACC {v['wacc']*100:.1f}%  "
          f"moat {res['moat']}  star {res['stars']}")
    if v.get("override"):
        print(f"  (override active: {v['override']})")
    d = ms_for(t)
    if d:
        print(f"  MORNINGSTAR: FV {d.get('fair_value')}  moat {d.get('moat')}  uncert {d.get('uncertainty')}  "
              f"star {d.get('star_rating')}")
    print(f"  STREET: rec_mean {ctx['rec_mean']}  PT upside {ctx['target_upside'] and round(ctx['target_upside']*100,1)}%  "
          f"({int(ctx['n_analysts'] or 0)} analysts)")


if __name__ == "__main__":
    main()
