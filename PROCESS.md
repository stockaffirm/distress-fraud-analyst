# PER-TICKER ANALYST PROCESS  (SOP — any agent can run this)

> Goal: for every ticker, produce an INDEPENDENT, defensible fair value (Morningstar-
> grade), iterating until it's right, and log *why* it differs from the baseline model
> and from Morningstar. Serial, one ticker at a time — NOT batches. Use LIVE APIs.
>
> **Resume:** open `LEDGER.csv`, find the first row with status=`pending`, do the loop
> below, set it `done`, append the verdict to `VERDICTS.md`. Repeat. State lives in
> `LEDGER.csv` (progress) + `analyst_overrides.csv` (per-name inputs) + `VERDICTS.md`
> (reasoning) + this file (rules learned). Everything needed to continue is in this folder.

---

## The loop (one ticker)

### 1. TAKE the next `pending` ticker from `LEDGER.csv`.

### 2. PULL live data (direct APIs — don't rely only on the cached 10yr fundamentals):
- **Morningstar (ground truth):** `cd /Users/prasadmenon/Claude/InvestmentHub && python3.11 fetch_one.py TICKER 0`
  → last stdout line = JSON with `fair_value`, `moat`, `uncertainty`, `star_rating`,
  `bull_case`/`bear_case`. (Login is cached; ~20s. Save to `ms_cache/TICKER.json`.)
- **AlphaVantage (forward view):** key `FCDX4WIX8O3MJHQ2`
  `curl -s "https://www.alphavantage.co/query?function=OVERVIEW&symbol=TICKER&apikey=FCDX4WIX8O3MJHQ2"`
  → `AnalystTargetPrice`, `ForwardPE`, `OperatingMarginTTM`, `QuarterlyRevenueGrowthYOY`,
  `ProfitMargin`, `RevenueTTM`, `EPS`. Forward PE vs trailing PE = the market's growth view.
  Also `function=EARNINGS` for the beat/miss trajectory (turnaround vs decline signal).
- **My model + 10yr trajectory:** `cd analyst_agent && python3 research.py TICKER`
- (Optional) **Massive** GAAP financials / short interest if AV looks off (see InvestmentHub/CLAUDE.md).

### 3. BUCKET the name (drives the calibration rule — see table below).

### 4. ANALYZE — set the independent forward view:
- **fwd_growth**: blend the 10yr trajectory with AV's forward signal (ForwardPE vs trailing,
  QuarterlyRevenueGrowthYOY, analyst PT). Decelerate hypergrowth; normalize cyclical troughs/peaks.
- **mature_margin**: structural operating margin at scale (not a trough/peak/data-artifact).
- Sanity-check against AV `AnalystTargetPrice` (a forward anchor) and the bull/bear from Morningstar.

### 5. CALIBRATE — apply + measure:
`python3 value_with.py TICKER <growth> <margin>` → read `my_fv`, `ratio_vs_ms`, `star`.

### 6. FIX & RE-RUN (the iterate-til-right step):
- If the gap is a **per-name judgment** → tune the override, re-run, until the FV is defensible.
- If the gap exposes a **bucket/structural flaw** in the model (a rule wrong for a whole class)
  → fix it in `valuation.py` AND record the rule here in §Rules; then re-run. A structural fix
  must not break already-`done` names — spot-check 2-3 with `reconcile.py`.
- "Perfect" = the FV is one I can defend on the fundamentals, and either matches Morningstar
  OR differs for a stated, falsifiable reason (not a bug).

### 7. LOG (append to `VERDICTS.md`): ticker, bucket, my FV vs MS vs baseline, what I changed
and WHY, why my view ≥ MS, key risk. Add the override to `analyst_overrides.csv`.

### 8. UPDATE this file's §Rules if you learned a general lesson (so the next agent benefits).

### 9. MARK `done` in `LEDGER.csv` (fill my_fv, ms_fv, ratio, bucket, date). Next ticker.

---

## Buckets & calibration rules

| Bucket | What | Rule |
|---|---|---|
| **STABLE** | mature compounder (KO, PG, JNJ) | low growth (3-6%), stable margin; Low uncertainty → low WACC; baseline usually ~right |
| **COMPOUNDER** | wide-moat secular grower (MSFT, GOOG, V) | decelerate trailing growth for scale; hold high margin |
| **HYPERGROWTH** | fast, often GAAP-unprofitable (CRWD, PLTR) | decelerate to sustainable; use **FCF** margin (GAAP suppressed by SBC); demand margin of safety |
| **CYCLICAL** | commodity/cyclical (energy, materials, semis, autos) | **mid-cycle** margin & growth, not the trailing trough/peak |
| **TURNAROUND** | temporary trough (NKE, SBUX) | look THROUGH the trough to normalized growth+margin; check insider buying |
| **FINANCIAL** | banks/insurers | DCF invalid → value on normalized P/E or P/B×ROE; note in verdict |
| **REIT** | real estate | DCF invalid → FFO/AFFO multiple |
| **ADR/FOREIGN** | foreign ADRs (BABA, TSM) | currency/disclosure caveats; often out-of-model |
| **OPTIONALITY** | value beyond DCF (TSLA) | out-of-model; state what the market prices that fundamentals can't |
| **RESTRUCTURING** | spin-off/M&A discontinuity (GE) | out-of-model or normalize to the continuing business |

## Rules learned (append as you go — bucket-level lessons that help future tickers)
- (2026-06-09) Data artifact: when cached `gross_margin >= 0.95`, the source folded COGS into
  opex → mature_margin must come from `opm_recent`/`opm_peak`, not a fraction of gross. (caught on SBUX)
- (2026-06-09) Software hypergrowth: value on **FCF margin (~30%)**, not GAAP op margin (SBC-suppressed). (CRWD)
- (2026-06-09) Cost of equity comes from the Uncertainty bucket (Morningstar method), NOT CAPM beta.
- (2026-06-09) Regulated/litigated names (managed care, pharma, defense, tobacco, banks under
  probe): the model can't see regulatory/legal risk, so it may rate them Low/Medium uncertainty
  wrongly -> set an **uncertainty override** (4th col in analyst_overrides.csv) to High/Very High.
  A name with growth near its WACC + Low uncertainty will explode (caught on UNH: raw $1107).
- (2026-06-09) NEW LEVER: analyst_overrides.csv now has an `uncertainty` column (Low..Extreme);
  it overrides the model's computed uncertainty -> cost of equity. Use for qualitative risk.



- (2026-06-09) STRUCTURAL FIX: asset-light software (gross margin >65%) earns very high returns
  on little capital (growth funded via opex S&M/R&D), so the g/ROIC reinvestment identity was
  double-counting -> now floors roic_norm to 0.40 for gm>0.65. Lifted PANW/CRWD; no regression on
  MSFT/GOOG/NVDA (already high-ROIC or <65% gross).

## "Done" definition
A ticker is `done` when: bucket assigned · independent fwd_growth+margin set (override if needed) ·
my_fv computed · compared to Morningstar (live pull) + AV forward anchor · verdict logged with the
why · LEDGER row filled. If a structural fix was made, prior `done` names were spot-checked.
