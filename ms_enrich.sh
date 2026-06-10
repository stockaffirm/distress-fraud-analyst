#!/bin/bash
# Morningstar enrichment — continuously pull live MS fair values into ms_cache/,
# largest-cap first, skipping anything already cached. Resumable & killable.
# Runs in parallel with the valuation loop; the workers read whatever MS data exists.
set -u
AG=/Users/prasadmenon/Claude/StockAffirmProject/stockaffirmtodos/analyst_agent
IH=/Users/prasadmenon/Claude/InvestmentHub
LOG=$AG/ms_enrich.log
: > "$LOG"
n=0; got=0
while read -r T; do
  [ -z "$T" ] && continue
  T=$(echo "$T" | tr -d '[:space:]')
  # skip if already cached with a real fair_value
  if [ -f "$AG/ms_cache/$T.json" ] && grep -q '"fair_value"' "$AG/ms_cache/$T.json" 2>/dev/null; then
    continue
  fi
  n=$((n+1))
  J=$(cd "$IH" && python3.11 fetch_one.py "$T" 0 2>/dev/null | tail -1)
  if echo "$J" | grep -q '"fair_value"'; then
    echo "$J" > "$AG/ms_cache/$T.json"; got=$((got+1))
    echo "[$(date +%H:%M:%S)] $T cached ($got ok / $n tried)" >> "$LOG"
  else
    echo "[$(date +%H:%M:%S)] $T no-data" >> "$LOG"
  fi
  sleep 1
done < "$AG/universe_1500.txt"
echo "[$(date +%H:%M:%S)] ms_enrich DONE: $got cached of $n tried" >> "$LOG"
