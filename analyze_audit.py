#!/usr/bin/env python3
"""analyze_audit.py OUTPUT.json -- aggregate calibration-audit verdicts to find
systematic false-positive patterns. Prints verdict mix overall + per our_call bucket,
the pattern histogram for false positives, and the false-positive ticker list per pattern."""
import sys, json, csv
from collections import Counter, defaultdict

out = sys.argv[1]
d = json.load(open(out))
res = d.get("result", d) if isinstance(d, dict) else d
res = [r for r in res if isinstance(r, dict) and r.get("ticker")]

# join with our screen rows for bucket context
rows = {r["ticker"]: r for r in csv.DictReader(open("DISTRESS_SCREEN.csv"))}

print(f"=== AUDIT n={len(res)} ===")
print("verdicts:", dict(Counter(r["verdict"] for r in res)))

# verdict by our bucket
byb = defaultdict(Counter)
for r in res:
    b = rows.get(r["ticker"], {}).get("bucket", "?")
    byb[b][r["verdict"]] += 1
print("\nverdict by our bucket:")
for b, c in byb.items():
    tot = sum(c.values())
    fp = c.get("false_positive", 0)
    print(f"  {b:24} n={tot:3}  FP={fp:3} ({100*fp/tot:.0f}%)  confirmed={c.get('confirmed',0)} partial={c.get('partial',0)}")

# pattern histogram among FALSE POSITIVES + PARTIALS
print("\npattern histogram (false_positive + partial):")
pat = Counter(r["pattern"] for r in res if r["verdict"] in ("false_positive", "partial"))
for p, c in pat.most_common():
    print(f"  {p:26} {c}")

# false positives grouped by pattern, with tickers
print("\nFALSE POSITIVES by pattern:")
fpp = defaultdict(list)
for r in res:
    if r["verdict"] == "false_positive":
        fpp[r["pattern"]].append(r["ticker"])
for p, ts in sorted(fpp.items(), key=lambda kv: -len(kv[1])):
    print(f"  [{p}] ({len(ts)}): {', '.join(ts)}")

# dump FP/partial detail for inspection
print("\n--- FP/partial detail ---")
for r in res:
    if r["verdict"] in ("false_positive", "partial"):
        b = rows.get(r["ticker"], {}).get("bucket", "?")
        print(f"{r['ticker']:6} {r['verdict']:14} [{r['pattern']:22}] {b:22} {r['one_line'][:90]}")
