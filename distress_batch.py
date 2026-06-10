#!/usr/bin/env python3
"""
distress_batch.py -- run the distress/fraud screen across the WHOLE universe
(the ~5,022 tickers in recommendations.csv) and emit the ranked lists.

Outputs (written here, in analyst_agent/):
  * DISTRESS_SCREEN.csv   -- every screenable ticker, its bucket + key metrics
  * DISTRESS_REPORT.md    -- the human-readable answer:
        - counts per bucket
        - AVOID / BANKRUPTCY-RISK list  (ranked by severity)
        - AVOID / FRAUD-RISK list       (ranked by Beneish M)
        - DISTRESSED-but-RECOVERABLE    (ranked: most distressed yet recovering)

  python3 distress_batch.py              # full universe
  python3 distress_batch.py --limit 300  # quick sample (first 300 tickers)
"""
import os, sys, csv, json, traceback
from data_loader import _recs, load_fundamentals, load_context, full_history
from distress_screen import screen
try:
    from distress_news import scan_ticker, news_window
except Exception:
    scan_ticker = None
    def news_window():
        return (None, None)

HERE = os.path.dirname(os.path.abspath(__file__))


def _num(r, k):
    v = r.get(k)
    try:
        return float(v) if v not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def run(limit=None):
    tickers = sorted(_recs().keys())
    if limit:
        tickers = tickers[:limit]
    rows, errors, skipped = [], 0, 0
    for i, t in enumerate(tickers):
        try:
            fund = load_fundamentals(t)
            ctx = load_context(t)
            if not fund or not ctx:
                skipped += 1
                continue
            hist = full_history(fund)
            if len(hist) < 2 or hist[0]["revenue"] in (None, 0):
                skipped += 1
                continue
            news = scan_ticker(t) if scan_ticker else None
            res = screen(t, ctx, hist, news=news)
            a, b, o, ac, m, s = (res["altman"], res["beneish"], res["ohlson"],
                                 res["accruals"], res["montier"], res["solvency"])
            rows.append({
                "ticker": t, "sector": res["sector"], "market_cap": res["market_cap"],
                "bucket": res["bucket"], "headline": res["headline"],
                "bankruptcy": int(res["bankruptcy"]), "distress_type": res.get("distress_type") or "",
                "fraud": int(res["fraud"]), "fraud_watchlist": int(bool(res.get("fraud_watchlist"))),
                "recoverable": int(res["recoverable"]),
                "news_bk_event": int(bool(res.get("news_bk_event"))),
                "news_fraud_event": int(bool(res.get("news_fraud_event"))),
                "bankruptcy_severity": res["bankruptcy_severity"],
                "fraud_severity": res["fraud_severity"],
                "recovery_score": res["recovery_score"],
                "altman_z2": a["z2"], "altman_zone": a["zone"], "altman_z_orig": a["z_orig"],
                "beneish_m": b.get("m"), "ohlson_p": o.get("p"),
                "accrual_ratio": ac.get("accrual_ratio"), "montier_c": m.get("c"),
                "nd_ebitda": s["nd_ebitda"], "current_ratio": s["current_ratio"],
                "neg_equity": int(bool(s["neg_equity"])), "fcf_neg": int(bool(s["fcf_neg"])),
                "cfo_neg": int(bool(s["cfo_neg"])),
                "cash_runway_months": s["cash_runway_months"],
                "earnings_quality_flag": int(bool(res.get("earnings_quality_flag"))),
                "reasons": "; ".join(res["reasons"]),
                "fraud_reasons": "; ".join(res["fraud_reasons"]),
                "fin_sector_caveat": int(res["fin_sector_caveat"]),
                "float_distortion": int(bool(res.get("float_distortion"))),
            })
        except Exception:
            errors += 1
            if errors <= 5:
                print(f"  [err] {t}: {traceback.format_exc().splitlines()[-1]}")
        if (i + 1) % 500 == 0:
            print(f"  ...{i+1}/{len(tickers)} processed ({len(rows)} scored)")

    # ---- write CSV ----
    cols = ["ticker", "sector", "market_cap", "bucket", "bankruptcy", "distress_type",
            "fraud", "fraud_watchlist", "recoverable", "news_bk_event", "news_fraud_event",
            "bankruptcy_severity", "fraud_severity", "recovery_score", "earnings_quality_flag",
            "altman_z2", "altman_zone", "altman_z_orig", "beneish_m", "ohlson_p",
            "accrual_ratio", "montier_c", "nd_ebitda", "current_ratio", "neg_equity",
            "fcf_neg", "cfo_neg", "cash_runway_months", "reasons", "fraud_reasons",
            "fin_sector_caveat", "float_distortion", "headline"]
    csv_path = os.path.join(HERE, "DISTRESS_SCREEN.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})

    write_report(rows, scored=len(rows), skipped=skipped, errors=errors, total=len(tickers))
    print(f"\nDone. {len(rows)} scored, {skipped} skipped (no data/<2y), {errors} errors.")
    print(f"  -> {csv_path}")
    print(f"  -> {os.path.join(HERE, 'DISTRESS_REPORT.md')}")
    return rows


def _cap(x):
    if not x:
        return "n/a"
    return f"${x/1e9:.1f}B" if x >= 1e9 else f"${x/1e6:.0f}M"

def _f(x, d=2):
    return "n/a" if x is None else f"{x:.{d}f}"

def _pct(x, d=0):
    return "n/a" if x is None else f"{x*100:.{d}f}%"


TOPN = 60   # cap each displayed list (full data is in the CSV)

def _mc(r):
    try:
        return float(r["market_cap"]) if r["market_cap"] not in (None, "", "None") else 0.0
    except (TypeError, ValueError):
        return 0.0

def write_report(rows, scored, skipped, errors, total):
    # rank by severity then SIZE so recognizable names you might actually hold
    # surface first within a severity tier (micro-cap zombies sink down the list)
    avoid_bk = sorted([r for r in rows if r["bankruptcy"]],
                      key=lambda r: (-r["bankruptcy_severity"], -_mc(r)))
    avoid_fr = sorted([r for r in rows if r["fraud"]],
                      key=lambda r: (-r["fraud_severity"], -_mc(r)))
    recover = sorted([r for r in rows if r["bucket"] == "DISTRESSED-RECOVERABLE"],
                     key=lambda r: -_mc(r))
    # forensic earnings-quality watchlist: fundamentals-suspicious but cash-backed /
    # one-time (demoted from AVOID-fraud), or otherwise elevated Beneish/accruals
    eq_watch = sorted([r for r in rows if (r.get("fraud_watchlist") == 1
                       or (r["earnings_quality_flag"] == 1 and not r["fraud"]))],
                      key=lambda r: -_mc(r))
    news_hits = sorted([r for r in rows if r.get("news_bk_event") == 1 or r.get("news_fraud_event") == 1],
                       key=lambda r: -_mc(r))
    watch = [r for r in rows if r["bucket"] == "WATCH"]
    clear = [r for r in rows if r["bucket"] == "CLEAR"]
    nlo, nhi = news_window()

    L = []
    L.append("# Distress & Fraud Screen — full universe\n")
    L.append("_Subagent of the Analyst Agent. Composes Altman Z''/Z, Beneish M, Ohlson O, "
             "Sloan accruals, Montier C, hard liquidity/leverage/cash-runway signals, and a "
             "NEWS/EVENT layer (going-concern, Chapter 11, SEC, short-seller, restatement). A "
             "name is bucketed AVOID only when multiple corroborating signals agree; cash "
             "runway + capital access decide near-term bankruptcy (not backward-looking GAAP "
             "losses), and earnings-manipulation requires earnings that can't convert to cash. "
             "Cash-flow statements are cached, so accruals / Beneish-TATA / FCF are exact._\n")
    L.append(f"_News/event layer: cache window {nlo} → {nhi} (a ~2-week live-poll snapshot; "
             "deep/historical news = on-demand web/AV enrichment, per the audit workflow)._\n")
    L.append(f"**Universe:** {total} tickers · **scored:** {scored} · "
             f"skipped (no data / <2y): {skipped} · errors: {errors}\n")
    L.append("## Bucket counts\n")
    n_insolv = sum(1 for r in avoid_bk if r.get("distress_type") == "insolvency")
    n_burn = sum(1 for r in avoid_bk if r.get("distress_type") == "cash_burn")
    L.append("| Bucket | Count | Meaning |")
    L.append("|---|---:|---|")
    L.append(f"| 🟥 AVOID — bankruptcy ({n_insolv} insolvency / {n_burn} cash-burn) | {len(avoid_bk)} | can't fund/service itself |")
    L.append(f"| 🟥 AVOID — fraud / manipulation | {len(avoid_fr)} | earnings can't convert to cash |")
    L.append(f"| 🟧 DISTRESSED — recoverable | {len(recover)} | badly stressed but solvent + turning |")
    L.append(f"| 🟨 WATCH (incl. forensic EQ flags) | {len(watch)} | stress signals, not terminal/recovering |")
    L.append(f"| 🟩 CLEAR | {len(clear)} | no material distress/manipulation signal |")
    L.append(f"\n_Of the {len(avoid_bk)+len(avoid_fr)} AVOID names, {len(news_hits)} carry a "
             f"corroborating NEWS event (📰) in the cache window. **insolvency** = an over-levered/"
             "loss-eroded operating business genuinely failing; **cash-burn** = a pre-profit "
             "company dependent on raising more capital (higher-risk, but not the same as a "
             "business going under)._")
    L.append("")

    def tbl(items, kind):
        out, shown = [], items[:TOPN]
        if kind == "bk":
            out.append("| # | Ticker | Sector | Mkt cap | Type | Z'' | Ohlson P(def) | ND/EBITDA | News | Sev | Flags |")
            out.append("|---:|---|---|---:|---|---:|---:|---:|:--:|---:|---|")
            for i, r in enumerate(shown, 1):
                nw = "📰" if r.get("news_bk_event") == 1 else ""
                out.append(f"| {i} | **{r['ticker']}** | {r['sector']} | {_cap(_mc(r))} | "
                           f"{(r.get('distress_type') or '')} | {_f(r['altman_z2'])} | {_pct(r['ohlson_p'])} | "
                           f"{_f(r['nd_ebitda'],1)} | {nw} | {r['bankruptcy_severity']} | {r['reasons']} |")
        elif kind == "fr":
            out.append("| # | Ticker | Sector | Mkt cap | Beneish M | Accruals | Montier C | Flags (incl. 4y CFO/NI) |")
            out.append("|---:|---|---|---:|---:|---:|---:|---|")
            for i, r in enumerate(shown, 1):
                out.append(f"| {i} | **{r['ticker']}** | {r['sector']} | {_cap(_mc(r))} | "
                           f"{_f(r['beneish_m'])} | {_pct(r['accrual_ratio'],1)} | {r['montier_c']}/6 | "
                           f"{r['fraud_reasons']} |")
        elif kind == "eq":
            out.append("| # | Ticker | Sector | Mkt cap | Bucket | Beneish M | Accruals |")
            out.append("|---:|---|---|---:|---|---:|---:|")
            for i, r in enumerate(shown, 1):
                out.append(f"| {i} | **{r['ticker']}** | {r['sector']} | {_cap(_mc(r))} | "
                           f"{r['bucket']} | {_f(r['beneish_m'])} | {_pct(r['accrual_ratio'],1)} |")
        else:  # recover
            out.append("| # | Ticker | Sector | Mkt cap | Z'' | ND/EBITDA | Recovery | Why recoverable |")
            out.append("|---:|---|---|---:|---:|---:|:--:|---|")
            for i, r in enumerate(shown, 1):
                out.append(f"| {i} | **{r['ticker']}** | {r['sector']} | {_cap(_mc(r))} | "
                           f"{_f(r['altman_z2'])} | {_f(r['nd_ebitda'],1)} | {r['recovery_score']}/7 | "
                           f"{r['headline'].split('—')[-1].strip()} |")
        if len(items) > TOPN:
            out.append(f"\n_…and {len(items)-TOPN} more — full ranked list in `DISTRESS_SCREEN.csv`._")
        return "\n".join(out)

    L.append("## 🟥 AVOID — Bankruptcy / insolvency risk  (top by severity × size)\n")
    L.append("> On the verge of bankruptcy: burning operating cash with a short runway, "
             "can't service debt (negative EBITDA, no offsetting cash), insolvent from "
             "accumulated losses, or a high Ohlson default probability — and NOT rescued by "
             "the solvency / profitability / long-runway overrides. **Note:** clinical-stage "
             "biotech and pre-revenue tech dominate this list — they burn cash *by design* "
             "and survive on equity raises; 'bankruptcy risk' for them means dilution/failure "
             "risk, a different flavor than an over-levered operating business going under.\n")
    L.append(tbl(avoid_bk, "bk") if avoid_bk else "_none_")
    L.append("")
    L.append("## 🟥 AVOID — Fraud / earnings-manipulation risk  (top by severity × size)\n")
    L.append("> Reported numbers likely juiced: Beneish M above -1.78 AND elevated POSITIVE "
             "accruals AND poor multi-year cash conversion (cum CFO < 70% of cum NI) AND a "
             "distinct corroborator (≥4 Montier flags, receivables spike, or M > -1.0). The "
             "cash-conversion + accruals gates clear hyper-growers (NVDA) and cash-backed "
             "quality compounders (AAON) that Beneish alone false-flags. Treat as "
             "'investigate', not proof.\n")
    L.append(tbl(avoid_fr, "fr") if avoid_fr else "_none_")
    L.append("")
    L.append("## 🟧 DISTRESSED — but RECOVERABLE  (slow-recovery candidates)\n")
    L.append("> Badly stressed (operating loss, cash burn, or high leverage + strain) BUT "
             "still solvent and turning: positive operating cash flow plus ≥3 of "
             "{deleveraging, improving margins, stabilizing revenue, asset coverage, decent "
             "Piotroski, rising Altman}. A fortress balance sheet (net cash + positive FCF) is "
             "excluded — a GAAP loss from stock-comp (CRWD/SNOW) is not distress. Largest first.\n")
    L.append(tbl(recover, "rc") if recover else "_none_")
    L.append("")
    L.append("## 🟨 Forensic earnings-quality watchlist  (NOT bucketed AVOID)\n")
    L.append("> Fundamentals-suspicious (elevated Beneish / accruals) but **demoted from the "
             "fraud bucket** because earnings DO convert to cash (good multi-year CFO/NI) or "
             "the firm is profitable & net-cash — so the high accruals are almost always a "
             "one-time non-cash item (deferred-tax release, lease/milestone accounting) or just "
             "fast-grower working-capital build, not manipulation. Investigate the accounting; "
             "this is where to point the live news/AV enrichment, not a manipulation call.\n")
    L.append(tbl(eq_watch, "eq") if eq_watch else "_none_")
    L.append("")
    L.append("## 📰 News-corroborated distress / fraud events  (cache window)\n")
    L.append(f"> Names with an actual distress/fraud HEADLINE in the news cache "
             f"({nlo} → {nhi}): going-concern, Chapter 11, default, SEC action, short-seller "
             "report, or restatement. These are the highest-confidence flags (footprint + "
             "event). Law-firm class-action solicitations are filtered out as noise.\n")
    if news_hits:
        L.append("| # | Ticker | Sector | Mkt cap | Bucket | Event |")
        L.append("|---:|---|---|---:|---|---|")
        for i, r in enumerate(news_hits[:TOPN], 1):
            ev = ("bankruptcy/going-concern" if r.get("news_bk_event") == 1 else "")
            ev += (" + " if r.get("news_bk_event") == 1 and r.get("news_fraud_event") == 1 else "")
            ev += ("fraud/SEC/short/restatement" if r.get("news_fraud_event") == 1 else "")
            L.append(f"| {i} | **{r['ticker']}** | {r['sector']} | {_cap(_mc(r))} | {r['bucket']} | {ev} |")
    else:
        L.append("_No actionable distress/fraud events in the current 2-week cache window. "
                 "Run the live audit (web/AV) for historical coverage._")
    L.append("")
    L.append("---\n_Limitations: interest expense is not separately disclosed in the cache "
             "(coverage approximated/omitted); for Financials, Real Estate, Utilities and "
             "detected float businesses (payroll processors, captive-finance, BDCs), Altman / "
             "leverage / Ohlson are structurally distorted and suppressed — those names are "
             "judged on cash flow + real (long-term) leverage. Beneish/Ohlson carry inherent "
             "false-positive rates; this screen mitigates with multi-signal corroboration, an "
             "accruals + cash-conversion necessary condition, and sector/float guards, but the "
             "AVOID-fraud list is a 'look harder' list, not a verdict. Single-vintage annuals "
             "(FY in the engine cache); not point-in-time as-reported._")
    path = os.path.join(HERE, "DISTRESS_REPORT.md")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


def main():
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    run(limit=limit)


if __name__ == "__main__":
    main()
