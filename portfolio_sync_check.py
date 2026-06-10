#!/usr/bin/env python3
"""
portfolio_sync_check.py -- keep portfolio_analysis.md in sync with the fair-value
analyst's verdicts. Runs every ~10 min (scheduled).

Logic (deterministic, no LLM needed):
  1. holdings = LEDGER.csv rows with group=portfolio
  2. for each held ticker that is `done`, collect (bucket, my_fv, ms_fv, ratio)
  3. build a managed markdown block (fair-value vs Morningstar for holdings)
  4. compare to the block currently between the markers in portfolio_analysis.md;
     if changed (or markers missing) -> rewrite that block IN PLACE (additive, idempotent)
  5. log what changed to SYNC_LOG.md
Prints a one-line summary + whether an update was applied.

Safe: only edits the marked block; never rewrites the rest of portfolio_analysis.md.
"""
import os, csv, datetime

HERE = os.path.dirname(__file__)
LEDGER = os.path.join(HERE, "LEDGER.csv")
PF = "/Users/prasadmenon/Claude/portfolio_analysis.md"
SYNC_LOG = os.path.join(HERE, "SYNC_LOG.md")
START = "<!-- FAIR-VALUE-ANALYST:START (auto-synced; do not edit by hand) -->"
END = "<!-- FAIR-VALUE-ANALYST:END -->"


def holdings_with_verdicts():
    rows = []
    if not os.path.exists(LEDGER):
        return rows
    for r in csv.DictReader(open(LEDGER)):
        if r.get("group") == "portfolio" and r.get("status") == "done":
            rows.append(r)
    return rows


def build_block(rows):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [START,
         f"### 🎯 Fair-Value Analyst (intrinsic DCF, calibrated to Morningstar) — auto-synced {ts}",
         "_Independent fair value per share. Stance = my FV vs Morningstar's. See analyst_agent/VERDICTS.md for the why._",
         "",
         "| Ticker | Bucket | My FV | Morningstar FV | Ratio | Read |",
         "|--------|--------|-------|----------------|-------|------|"]
    def num(x):
        try: return float(x)
        except (TypeError, ValueError): return None
    for r in sorted(rows, key=lambda x: x["ticker"]):
        my, ms, ratio = num(r.get("my_fv")), num(r.get("ms_fv")), num(r.get("ratio"))
        read = "—"
        if ratio:
            read = "above MS" if ratio > 1.15 else "below MS" if ratio < 0.87 else "≈ MS"
        L.append(f"| {r['ticker']} | {r.get('bucket','')} | "
                 f"{('$'+format(my,',.0f')) if my else 'n/a'} | "
                 f"{('$'+format(ms,',.0f')) if ms else 'n/a'} | "
                 f"{(format(ratio,'.2f')+'×') if ratio else '—'} | {read} |")
    L += ["", END]
    return "\n".join(L)


def main():
    rows = holdings_with_verdicts()
    block = build_block(rows)
    if not os.path.exists(PF):
        print(f"sync: portfolio file not found at {PF}"); return
    txt = open(PF).read()
    if START in txt and END in txt:
        pre = txt[:txt.index(START)]
        post = txt[txt.index(END) + len(END):]
        current = txt[txt.index(START):txt.index(END) + len(END)]
        new = pre + block + post
        changed = current.strip() != block.strip()
    else:
        # insert after the first '---' (below the header) or append
        new = txt.rstrip() + "\n\n" + block + "\n"
        changed = True

    # ignore the timestamp line when deciding "changed" (so we don't churn every run)
    def strip_ts(s):
        return "\n".join(l for l in s.splitlines() if "auto-synced" not in l)
    if START in txt and END in txt:
        changed = strip_ts(current) != strip_ts(block)

    if changed:
        open(PF, "w").write(new)
        msg = f"{datetime.datetime.now():%Y-%m-%d %H:%M} — synced {len(rows)} holdings' fair values into portfolio_analysis.md"
        with open(SYNC_LOG, "a") as f:
            f.write(msg + "\n")
        print("UPDATED:", msg)
    else:
        print(f"no change — {len(rows)} holdings already in sync ({datetime.datetime.now():%H:%M})")


if __name__ == "__main__":
    main()
