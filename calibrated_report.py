#!/usr/bin/env python3
"""
calibrated_report.py -- the FINAL deliverable of the calibration loop.

Merges the per-ticker calibration ledger's `effective_bucket` (screen ∪ direct-API overlay)
into a single corrected view and writes CALIBRATED_FINDINGS.md:
  * final effective-bucket distribution (vs raw screen)
  * ESCALATIONS — names the live-API caught that the fundamentals screen missed (the payoff)
  * DOWNGRADES — AVOID→WATCH funded burners that just raised capital (false-positive cuts)
  * the headline AVOID list by effective_bucket

  python3 calibrated_report.py
"""
import os, csv
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "CALIBRATION_LEDGER.csv")
OUT = os.path.join(HERE, "CALIBRATED_FINDINGS.md")


def mc(r):
    try:
        return float(r["market_cap"])
    except (TypeError, ValueError):
        return 0.0


def cap(m):
    return ("$%.1fB" % (m / 1e9)) if m >= 1e9 else ("$%.0fM" % (m / 1e6)) if m else "n/a"


def eff(r):
    return r.get("effective_bucket") or r["bucket"]


def main():
    rows = list(csv.DictReader(open(LEDGER)))
    scored = [r for r in rows if not r["bucket"].startswith("SKIP")]
    sb, eb = Counter(r["bucket"] for r in rows), Counter(eff(r) for r in rows)
    changed = [r for r in rows if eff(r) != r["bucket"]]
    escal = sorted([r for r in changed if eff(r) in ("AVOID", "WATCH")
                    and r["bucket"] in ("CLEAR", "WATCH", "DISTRESSED-RECOVERABLE")],
                   key=lambda r: -mc(r))
    downg = sorted([r for r in changed if r["bucket"] == "AVOID" and eff(r) != "AVOID"],
                   key=lambda r: -mc(r))
    avoid = sorted([r for r in rows if eff(r) == "AVOID"], key=lambda r: -mc(r))

    L = ["# Calibrated Findings — distress & fraud, full universe\n",
         "_Final view after the sequential per-ticker calibration loop reconciled the fundamentals "
         "screen with the DIRECT Massive API (live news events, short interest, recent capital "
         "raises). `effective_bucket` = screen ∪ API overlay = the final answer._\n",
         f"**Universe:** {len(rows)} · scored: {len(scored)} · skipped (no data/<2y): {len(rows)-len(scored)} · "
         f"overlay adjusted **{len(changed)}** names.\n",
         "## Final distribution (effective bucket vs raw screen)\n",
         "| Bucket | Screen | Effective |", "|---|---:|---:|"]
    for b in ("AVOID", "DISTRESSED-RECOVERABLE", "WATCH", "CLEAR"):
        L.append(f"| {b} | {sb.get(b,0)} | {eb.get(b,0)} |")
    L.append("")

    L.append(f"## 🔎 ESCALATIONS — live-API caught what the fundamentals missed ({len(escal)})\n")
    L.append("> A short-seller report, an SEC action, a subsidiary fraud, a restatement, or a "
             "going-concern headline the snapshot fundamentals structurally can't see. These moved "
             "UP to WATCH/AVOID on ≥2 corroborating live-news articles — the payoff of the overlay.\n")
    L.append("| Ticker | Mkt cap | Screen → Effective | Signal | Headline |")
    L.append("|---|---:|---|---|---|")
    for r in escal:
        head = r["note"].split("BK:")[-1].split("FR:")[-1][:70] if r["note"] else ""
        sig = "fraud/SEC/restatement" if "fraud" in r["verdict"] else "distress/going-concern"
        L.append(f"| **{r['ticker']}** | {cap(mc(r))} | {r['bucket']} → {eff(r)} | {sig} | {head} |")
    L.append("")

    L.append(f"## ⤵️ DOWNGRADES — funded burners cut from AVOID ({len(downg)})\n")
    L.append("> Flagged AVOID(cash_burn) on a short snapshot runway, but a just-closed equity raise "
             "(public offering / registered direct / private placement) extends the runway the "
             "snapshot can't see → downgraded to WATCH. Top by size:\n")
    L.append("| Ticker | Mkt cap | Raise headline |")
    L.append("|---|---:|---|")
    for r in downg[:25]:
        head = r["note"].split("RAISE:")[-1][:75] if "RAISE:" in (r["note"] or "") else r["note"][:60]
        L.append(f"| **{r['ticker']}** | {cap(mc(r))} | {head} |")
    if len(downg) > 25:
        L.append(f"\n_…and {len(downg)-25} more (full list in CALIBRATION_LEDGER.csv, verdict=OVERFLAG_recent_raise)._")
    L.append("")

    L.append(f"## 🟥 Final AVOID list ({len(avoid)}) — top 40 by size\n")
    L.append("| Ticker | Sector | Mkt cap | Type | API-corroborated |")
    L.append("|---|---|---:|---|:--:|")
    for r in avoid[:40]:
        corr = "✓" if (r["api_distress"] == "1" or r["api_fraud"] == "1" or r["api_high_short"] == "1") else ""
        L.append(f"| **{r['ticker']}** | {r['sector']} | {cap(mc(r))} | {r.get('distress_type') or 'fraud' if r['fraud']=='1' else r.get('distress_type','')} | {corr} |")
    L.append(f"\n_…and {len(avoid)-40} more in CALIBRATION_LEDGER.csv (effective_bucket=AVOID)._")
    L.append("\n---\n_Limitations carry from DISTRESS_AGENT.md §10. The AVOID-fraud names are "
             "'investigate', corroborated where the API column shows ✓. SKIP names lack ≥2y data._")
    open(OUT, "w").write("\n".join(L) + "\n")
    print(f"wrote {OUT}")
    print(f"  escalations={len(escal)}  downgrades={len(downg)}  final AVOID={len(avoid)}")


if __name__ == "__main__":
    main()
