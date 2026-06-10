#!/usr/bin/env python3
"""
aggregate_verdicts.py -- consolidate the 60 worker batch files (wf_out/batch_N.json)
into the master deliverables:
  VERDICTS_1500.csv  -- full table (ticker,sector,mcap_B,my_fv,fwd_growth,mature_margin,
                        moat,star,ms_fv,ratio,stance,override_applied,reasoning,risk)
  VERDICTS_1500.md   -- readable summary + the biggest disagreements vs Morningstar
  overrides_1500.csv -- per-name overrides the workers set (ticker,fwd_growth,mature_margin,note)
Prints coverage + accuracy stats.
"""
import os, json, glob, csv, statistics, re

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "wf_out")


def load():
    rows = []
    for f in sorted(glob.glob(os.path.join(WF, "batch_*.json")),
                    key=lambda p: int(re.search(r"batch_(\d+)", p).group(1)) if re.search(r"batch_(\d+)", p) else -1):
        if not re.search(r"batch_\d+\.json$", f):
            continue                       # skip batch_test.json etc.
        try:
            data = json.load(open(f))
        except (json.JSONDecodeError, ValueError):
            print(f"  !! unparseable: {os.path.basename(f)}")
            continue
        if isinstance(data, list):
            rows += data
    # de-dupe by ticker (keep first)
    seen, out = set(), []
    for r in rows:
        t = (r.get("ticker") or "").upper()
        if t and t not in seen:
            seen.add(t); out.append(r)
    return out


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def main():
    rows = load()
    print(f"loaded {len(rows)} unique verdicts from worker batches")
    if not rows:
        print("no verdicts yet — has the workflow finished?"); return

    # normalize field names across worker variants
    for r in rows:
        r["stance"] = r.get("stance") or r.get("stance_vs_ms") or "independent"
        r["bucket"] = r.get("bucket") or ""
        if r.get("ratio") in (None, "") and num(r.get("my_fv")) and num(r.get("ms_fv")):
            r["ratio"] = round(num(r["my_fv"]) / num(r["ms_fv"]), 2)

    # full CSV
    cols = ["ticker", "sector", "mcap_B", "bucket", "my_fv", "fwd_growth", "mature_margin",
            "uncertainty", "moat", "star", "ms_fv", "ratio", "stance", "reasoning", "risk"]
    with open(os.path.join(HERE, "VERDICTS_1500.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # overrides the workers set
    ov = [r for r in rows if r.get("override_applied")]
    with open(os.path.join(HERE, "overrides_1500.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ticker", "fwd_growth", "mature_margin", "note"])
        for r in ov:
            w.writerow([r["ticker"], r.get("fwd_growth"), r.get("mature_margin"),
                        (r.get("reasoning") or "")[:160]])

    # stats
    with_ms = [r for r in rows if num(r.get("ms_fv"))]
    ratios = [num(r.get("ratio")) for r in with_ms if num(r.get("ratio"))]
    above = [r for r in with_ms if (num(r.get("ratio")) or 0) > 1.15]
    below = [r for r in with_ms if 0 < (num(r.get("ratio")) or 0) < 0.87]
    aligned = [r for r in with_ms if 0.87 <= (num(r.get("ratio")) or 0) <= 1.15]
    oom = [r for r in rows if r.get("stance") == "out-of-model"]
    dcfna = [r for r in rows if r.get("stance") == "dcf-na"]
    from collections import Counter
    moats = Counter(r.get("moat") for r in rows)

    L = ["# Analyst Verdicts — 1,500-name independent pass\n",
         f"Coverage: **{len(rows)}** names · overrides applied: **{len(ov)}** · "
         f"Morningstar comp available: **{len(with_ms)}**\n",
         f"Moat mix: Wide {moats.get('Wide',0)} · Narrow {moats.get('Narrow',0)} · None {moats.get('None',0)} "
         f"· DCF-NA {len(dcfna)} · out-of-model {len(oom)}\n"]
    if ratios:
        L.append(f"Vs Morningstar (n={len(ratios)}): median ratio **{statistics.median(ratios):.2f}** · "
                 f"above {len(above)} · aligned {len(aligned)} · below {len(below)}\n")
    L.append("## Biggest disagreements vs Morningstar (|gap| largest)\n")
    L.append("| Ticker | Sector | My FV | MS FV | ratio | stance | reasoning |")
    L.append("|---|---|---|---|---|---|---|")
    ranked = sorted(with_ms, key=lambda r: abs((num(r.get("ratio")) or 1) - 1), reverse=True)[:40]
    for r in ranked:
        L.append(f"| {r['ticker']} | {(r.get('sector') or '')[:14]} | {r.get('my_fv')} | {r.get('ms_fv')} | "
                 f"{r.get('ratio')} | {r.get('stance_vs_ms')} | {(r.get('reasoning') or '')[:90]} |")
    open(os.path.join(HERE, "VERDICTS_1500.md"), "w").write("\n".join(L) + "\n")

    print(f"  overrides applied: {len(ov)}")
    print(f"  with MS comp: {len(with_ms)}  | median ratio: {statistics.median(ratios):.2f}" if ratios else "  (no MS comps)")
    print(f"  above {len(above)} / aligned {len(aligned)} / below {len(below)} | oom {len(oom)} dcf-na {len(dcfna)}")
    print(f"  -> VERDICTS_1500.csv, VERDICTS_1500.md, overrides_1500.csv")


if __name__ == "__main__":
    main()
