#!/usr/bin/env python3
"""
analyst.py -- Morningstar-style Analyst Agent CLI.

  python3 analyst.py AAPL                 # one report to stdout
  python3 analyst.py AAPL MSFT NKE ANET   # several
  python3 analyst.py --save AAPL          # also write reports/AAPL.md
  python3 analyst.py --batch FILE.txt     # one ticker per line

Produces a fair value estimate, economic moat, moat trend, uncertainty,
star rating, key DCF assumptions, and a verdict vs both price and the
StockAffirm engine + Street consensus.
"""
import sys
from data_loader import load_fundamentals, load_context, financial_history
from valuation import analyze

STAR = lambda n: ("★" * n + "☆" * (5 - n)) if n else "n/a"


def _b(x, d=0, suf="", pre="", na="n/a"):
    if x is None:
        return na
    if suf in ("%", "pp"):           # ratio -> percent / percentage-points
        return f"{pre}{x*100:.{d}f}{suf}"
    return f"{pre}{x:,.{d}f}{suf}"


def _money(x):
    if x is None:
        return "n/a"
    a = abs(x)
    for div, s in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if a >= div:
            return f"${x/div:,.1f}{s}"
    return f"${x:,.0f}"


def verdict(res):
    pf, stars, unc = res["price_to_fv"], res["stars"], res["uncertainty"]
    if not res.get("dcf_applicable", True):
        return "DCF N/A (financial)", "enterprise DCF invalid for this sector — see warning above"
    if pf is None:
        return "NO-VALUATION", "insufficient data for a reliable DCF"
    disc = (1 - pf) * 100
    if stars >= 5:
        call = "STRONG BUY"
    elif stars == 4:
        call = "BUY"
    elif stars == 3:
        call = "FAIRLY VALUED"
    elif stars == 2:
        call = "RICH / TRIM"
    else:
        call = "OVERVALUED"
    side = "below" if disc > 0 else "above"
    return call, f"trading ~{abs(disc):.0f}% {side} intrinsic fair value ({unc} uncertainty)"


def render(res):
    c, n, v = res["ctx"], res["norm"], res["valuation"]
    moat, trend, unc = res["moat"], res["moat_trend"], res["uncertainty"]
    call, why = verdict(res)
    L = []
    L.append(f"# {res['ticker']} — Analyst Agent (Morningstar-style intrinsic valuation)")
    L.append(f"_{c['sector']} · market cap {_money(c['market_cap'])} · {n['n_years']}y financial history_\n")

    if res.get("out_of_model"):
        L.append("> 🚩 **OUT-OF-MODEL — a fundamentals DCF can't reliably value this name.** "
                 + "; ".join(res["out_of_model_reasons"]) +
                 ". Treat the fair value below as a floor/reference only; Morningstar/market "
                 "are pricing optionality or a structural change beyond the financials.\n")

    if not res.get("dcf_applicable", True):
        L.append("> ⚠️ **Enterprise DCF NOT valid for this sector "
                 f"({c['sector']}).** For banks/insurers/REITs, debt & float are the "
                 "operating model, so an FCFF-to-firm DCF is meaningless. The fair value "
                 "below is **suppressed** — value these on **excess-return / DDM / "
                 "P-B×ROE** instead. Moat, uncertainty, and the engine/Street cross-check "
                 "below remain valid.\n")

    L.append("## Verdict")
    L.append(f"**{call}** — {why}")
    if res.get("dcf_applicable", True):
        L.append(f"- **Fair Value (equity):** {_money(v['equity_value'])}  "
                 f"vs market cap {_money(c['market_cap'])}")
        if v["fv_per_share"]:
            L.append(f"- **Fair Value / share:** ${v['fv_per_share']:,.2f}  "
                     f"({_b(v['shares']/1e9,2,'B')} dil. shares)")
        L.append(f"- **Star rating:** {STAR(res['stars'])}  "
                 f"(price/fair-value = {_b(res['price_to_fv'],0,'%') if res['price_to_fv'] else 'n/a'})")
    else:
        L.append("- **Fair Value / Star rating:** _suppressed — DCF invalid for financials "
                 "(see warning above)_")
    L.append(f"- **Economic Moat:** {moat}   |   **Moat Trend:** {trend}   |   "
             f"**Uncertainty:** {unc} (MoS {_b(res['margin_of_safety'],0,'%')})\n")

    L.append("## Economic Moat")
    L.append(f"**{moat}** — {res['moat_reason']}")
    L.append(f"Trend **{trend}**: {res['moat_trend_reason']}\n")

    L.append("## Key DCF Assumptions (all auditable)")
    L.append(f"- WACC **{_b(v['wacc'],1,'%')}**  (beta {v['beta']:.2f}, cost of equity {_b(v['ke'],1,'%')}, "
             f"after-tax cost of debt {_b(v['kd'],1,'%')})")
    L.append(f"- Stage-1 revenue growth **{_b(v['g1'],1,'%')}/yr** for 5y "
             f"(from 5y CAGR {_b(n['rev_cagr_5'],1,'%')}, haircut 15%)")
    L.append(f"- Moat-governed fade window: **{v['fade_years']} years** ({moat} moat)")
    L.append(f"- Target operating margin **{_b(v['target_margin'],1,'%')}**  "
             f"(recent {_b(n['opm_recent'],1,'%')}, 10y median {_b(n['opm_median'],1,'%')})")
    L.append(f"- Normalized ROIC **{_b(v['roic_norm'],1,'%')}** → terminal ROIC {_b(v['roic_terminal'],1,'%')}")
    L.append(f"- Terminal growth {_b(0.025,1,'%')}; terminal value = "
             f"**{_b(v['terminal_pct'],0,'%')}** of enterprise value\n")

    L.append("## Reverse DCF — what is the market actually pricing in?")
    if v["implied_g"] is not None:
        ig, og = v["implied_g"], v["g1"]
        gap = ig - og
        read = ("market demands materially FASTER growth than the 10y trend — "
                "rich unless a reacceleration story is real" if gap > 0.03 else
                "market is pricing growth ROUGHLY in line with history — "
                "valuation hinges on margins/moat durability" if abs(gap) <= 0.03 else
                "market is pricing growth BELOW the historical trend — "
                "potential value if the franchise holds")
        L.append(f"- Today's market cap implies **{_b(ig,1,'%')}/yr** stage-1 revenue growth "
                 f"vs our **{_b(og,1,'%')}** base case (10y trend-based).")
        L.append(f"- **Read:** {read}.\n")
    else:
        L.append("- (no market cap available)\n")

    L.append("## Sensitivity — equity fair value ($) by growth × WACC")
    L.append("| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |")
    L.append("|---|---|---|---|")
    for dg, g, row in v["sensitivity"]:
        lbl = "base case" if abs(dg) < 1e-9 else f"{dg*100:+.0f}pp vs base"
        L.append(f"| {g*100:.1f}% ({lbl}) | {_money(row[0])} | {_money(row[1])} | {_money(row[2])} |")
    L.append(f"_(compare every cell to market cap {_money(c['market_cap'])})_\n")

    L.append("## Normalized Economics (10y)")
    L.append(f"- Revenue CAGR: 3y {_b(n['rev_cagr_3'],1,'%')}, 5y {_b(n['rev_cagr_5'],1,'%')}")
    L.append(f"- ROIC: median {_b(n['roic_median'],1,'%')}, recent {_b(n['roic_recent'],1,'%')}, "
             f"older {_b(n['roic_old'],1,'%')}")
    L.append(f"- Operating margin: median {_b(n['opm_median'],1,'%')}, stdev {_b(n['opm_stdev'],1,'pp')}")
    L.append(f"- Gross margin median {_b(n['gm_median'],0,'%')}; "
             f"revenue-growth volatility {_b(n['rev_growth_stdev'],1,'pp')}\n")

    L.append("## Cross-check vs StockAffirm engine & the Street")
    L.append(f"- Engine composite **{_b(c['engine_composite'],1)}** → tier **{c['engine_tier']}**  "
             f"(Piotroski {_b(c['piotroski_f'],0)}, Altman-Z {_b(c['altman_z'],1)})")
    if c["rec_mean"]:
        st = "Buy" if c["rec_mean"] <= 2 else "Hold" if c["rec_mean"] < 3.5 else "Sell"
        L.append(f"- Street: rec_mean {c['rec_mean']:.2f} ({st}, {int(c['n_analysts'] or 0)} analysts), "
                 f"PT upside {_b(c['target_upside'],0,'%')}")
    else:
        L.append("- Street: no analyst coverage")
    # three-way agreement read
    L.append(f"- **Three-way read:** analyst-agent says _{call}_; engine says _{c['engine_tier']}_; "
             f"Street says _{('Buy' if (c['rec_mean'] or 9)<=2 else 'Hold' if (c['rec_mean'] or 9)<3.5 else 'Sell' if c['rec_mean'] else 'n/a')}_.")

    L.append("\n## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is "
             "NOPAT + D&A − capex_proxy − ΔWC)")
    L.append("| FY | Revenue | Op margin | ROIC | FCFF |")
    L.append("|----|---------|-----------|------|------|")
    for y in res["yrs"][:6]:
        L.append(f"| {y['fy']} | {_money(y['revenue'])} | {_b(y['op_margin'],1,'%')} | "
                 f"{_b(y['roic'],1,'%')} | {_money(y['fcff'])} |")

    L.append("\n> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); "
             "moat & uncertainty are quantitative proxies for what a Morningstar analyst judges "
             "qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the "
             "qualitative read (moat narrative, management guidance, risk factors)._")
    return "\n".join(L)


def run_one(ticker, save=False):
    fund = load_fundamentals(ticker)
    ctx = load_context(ticker)
    if not fund or not ctx:
        print(f"\n# {ticker.upper()}: no cached fundamentals/context — skipped\n")
        return
    hist = financial_history(fund)
    if len(hist) < 3:
        print(f"\n# {ticker.upper()}: <3y history — DCF not reliable\n")
        return
    res = analyze(ticker.upper(), ctx, hist)
    out = render(res)
    print("\n" + out + "\n")
    if save:
        import os
        d = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{ticker.upper()}.md"), "w") as f:
            f.write(out + "\n")
        print(f"[saved reports/{ticker.upper()}.md]")


def main():
    args = sys.argv[1:]
    save = "--save" in args
    args = [a for a in args if a != "--save"]
    if args and args[0] == "--batch":
        with open(args[1]) as f:
            tickers = [l.strip() for l in f if l.strip()]
    else:
        tickers = args or ["AAPL"]
    for t in tickers:
        run_one(t, save=save)


if __name__ == "__main__":
    main()
