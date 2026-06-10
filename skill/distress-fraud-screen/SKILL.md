---
name: distress-fraud-screen
description: Screen any stock, a list, or the whole ~5,000-name universe for BANKRUPTCY/INSOLVENCY risk and EARNINGS FRAUD/manipulation, and surface the badly-stressed names that can still recover. Buckets each name into AVOID(insolvency|cash_burn|fraud) / DISTRESSED-RECOVERABLE / WATCH / CLEAR using a 7-model fundamentals screen (Altman Z'', Beneish M, Ohlson O, Sloan accruals, Montier C + liquidity/leverage/cash-runway) cross-checked against direct Massive APIs (live news events, short interest, recent capital raises). Use when the user says "is X going bankrupt / a fraud", "what stocks should I avoid", "screen the market for distress/fraud", "find near-bankruptcy or accounting-fraud names", "is X's accounting clean", or "calibrate / continue the distress screen". Distinct from fair-value-analyst (DCF value) and portfolio-analysis (buy/sell verdicts).
---

# Distress & Fraud Screen

Find the stocks to AVOID — near **bankruptcy/insolvency** or **juicing the numbers (fraud)** — and
the stressed names that can **recover**. Delegate to the `distress-fraud-analyst` agent, which
embodies the framework and reads its live brain (playbook + spec + calibration log) on every run.

## Parse the request
- A ticker or list (`NVDA`, `BYND CCL AAL`) → screen + direct-API validate each, bucket them.
- "everything" / "the market" / "screen the universe" / "all 5200" / "what should I avoid" →
  run the whole-universe distress batch and report the ranked AVOID (bankruptcy + fraud) lists,
  the distressed-recoverable list, and the forensic earnings-quality watchlist.
- "calibrate" / "make it perfect" / "continue calibration" → run the sequential per-ticker,
  direct-API calibration loop; act on the disagreements; log every lesson. Resumable.
- "is X's accounting clean / a fraud" → the fraud read (Beneish + accruals + cash conversion) with
  the live news/short-interest cross-check.

## Delegate
Invoke the **`distress-fraud-analyst`** agent (Agent tool, `subagent_type: distress-fraud-analyst`)
with the parsed task. It will:
1. Read its brain first: `AGENT_PLAYBOOK.md`, `DISTRESS_AGENT.md`, `CALIBRATION_LOG.md`, the ledger.
2. Run `distress_screen.py` / `distress_batch.py` (fundamentals) + `calibrate.py` / `massive_api.py`
   (direct-API ground truth: news events, short interest, recent raises).
3. Bucket each name and explain the risk; for calibration, fix the screen generally + log the why.

## Working directory
`/Users/prasadmenon/Claude/StockAffirmProject/stockaffirmtodos/analyst_agent/` — all tools, docs,
logs, and the calibration ledger live here.

## Return
The risk bucket(s) with the fundamentals read, the live-API corroboration/contradiction, and a
plain-English risk explanation. Always honest about what's not in the data; a fundamentals-only
fraud flag is "investigate," not a verdict. Analysis only — never trades.
