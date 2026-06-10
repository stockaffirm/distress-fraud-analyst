# Analyst Agent — the exact stepwise algorithm

> Where the logic lives: **`valuation.py`** (the brain), `data_loader.py` (inputs),
> `analyst.py` (report), `reconcile.py` (per-ticker MS validation).
> This doc is the human-readable spec of what `valuation.py` actually does, with the
> real formulas, calibrated constants, and the function/line each step maps to.

The entry point is `analyze(ticker, ctx, hist)` (valuation.py:457). It runs 9 steps.

---

## INPUT (data_loader.py)
- `hist` = 10 years of annual income statements + balance sheets from the cached
  fundamentals zips (revenue, operating income, EBITDA, taxes, diluted shares,
  PP&E, receivables/inventory/payables/deferred-rev, debt, cash, equity).
- `ctx` = sector, market cap, Street consensus (from `recommendations.csv`).

---

## STEP 0 — Is an enterprise DCF even valid?  (`analyze`, line 458)
`dcf_applicable = sector not in {Financials, Real Estate}`.
For banks/insurers/REITs, debt & float are the *operating* model, so an FCFF-to-firm
DCF is meaningless → the fair value is suppressed and the report says "use DDM / P-B×ROE".

## STEP 1 — Derive normalized economics  (`derive_economics`, line 75)
For each of the 10 years compute:
- `tax_rate` = income_taxes / pretax_income, clamped [0, 35%] (else 21%)
- `NOPAT` = operating_income × (1 − tax_rate)
- `D&A`  ≈ EBITDA − operating_income  (fallback 4% of revenue)
- `capex` ≈ Δ(net PP&E) + D&A           (cash-flow statement isn't cached → proxy)
- `ΔWC`  = Δ(receivables + inventory − payables − deferred revenue)
- **`FCFF` = NOPAT + D&A − capex − ΔWC**   (unlevered free cash flow)
- `invested capital` = equity + debt − cash
- **`ROIC` = NOPAT / invested capital**

Then summarize across the 10y into `norm`: revenue CAGR (3y & 5y), median/recent/peak
operating margin, median gross margin, median/recent/old ROIC, margin & growth
volatility (std-dev), years of positive ROIC, latest shares/debt/cash.

## STEP 2 — Economic moat  (`assess_moat`, line 155) → None / Narrow / Wide
A points score (the moat is what governs the DCF fade length, so it matters a lot):
```
score  = clamp((ROIC − WACC) / 0.10, −1, +2)   # excess returns (dominant term)
       + 1.0 if durable (≥8y positive ROIC)
       + 0.5 if gross margin > 45%              # pricing power proxy
       + 0.5 if op-margin std-dev < 5%          # earnings stability
       + 1.0 if "scalable" (gross margin >60% AND 5y growth >10%)
```
- **Wide**  if `score ≥ 2.6 AND excess > 8pp AND durable`, or `scalable AND score ≥ 2.8`
- **Narrow** if `excess > 0 AND (score ≥ 0.7 OR durable)`, or `scalable`
- **None** otherwise
- Special case: if ROIC is null (young reinvestor / buyback-distorted equity) but
  the business is *scalable* → Narrow (this is what fixed CRWD: None→Narrow vs MS Wide).

## STEP 3 — Uncertainty rating  (`assess_uncertainty`, line 211) → Low … Extreme
Points, calibrated to **look through the cycle** (a commodity swing ≠ a fragile
business). Higher uncertainty → wider margin of safety → higher discount rate later.
```
+0..3  from operating-margin volatility (std-dev bands 3/6/11%)
+0..2  from revenue-growth volatility   (bands 8/20%, capped at 2 — cycle look-through)
+0..2  from net-debt / market-cap leverage (bands 20/55%)
+1     if median ROIC < 3%   (thin profitability)
+1     if median op margin < 3%
−1     if market cap > $50B AND durable (scale lowers uncertainty)
```
Buckets: Low ≤1 · Medium ≤4 · High ≤6 · Very High ≤8 · Extreme >8.

## STEP 4 — WACC  (`compute_wacc`, line 243)
**Morningstar's actual method — cost of equity straight from the Uncertainty bucket
(NOT CAPM beta):** Low 6.5% · Medium 7.5% · High 9.0% · Very High 11.0% · Extreme 13.5%.
- Utilities capped at the Low (6.5%) cost of equity (regulated = low systematic risk).
- After-tax cost of debt = 5.5% × (1 − 21%) = 4.35%.
- **WACC = (E/(E+D))·ke + (D/(E+D))·kd**, E = market cap, D = book debt.

## STEP 5 — Sector moat floor  (`_sector_moat_floor`, line 441)
Regulated utilities (durable) and large energy/midstream (>$40B, durable) earn a moat
from their *franchise*, not from excess ROIC a pure test misses → floored to **Narrow**.

## STEP 6 — The 3-stage DCF  (`dcf` → `_equity_value`, lines 313 / 260)

**6a. Mature operating-margin target (margin-expansion model).** Young high-gross-margin
firms reinvest away today's margin, so value them on mature economics:
```
gm_mature = 0.42×gross  if gross>65%   (best-in-class software → ~40% op margin)
          = 0.34×gross  if gross>55%
          = 0.22×gross  if gross>40%
          = 0            otherwise
target_margin = max(recent op margin, p75 peak margin, gm_mature),  capped ≤ 90%×gross
```
Margin **ramps** linearly from today → target over 6 years (if expanding).

**6b. Normalized ROIC** for the reinvestment math = median ROIC (clamped 2–60%);
floored to WACC+6% for margin-expanders, WACC+1.5% for utilities (regulated returns).

**6c. Stage-1 growth.** `base = 0.6×(5y CAGR) + 0.4×(3y CAGR)`.
- Moaty hyper-growth (base>20% AND moat≥Narrow): **6-year** explicit stage, cap 28%.
- Else: **5-year** explicit stage, cap 25%. Floor = terminal growth (3%).

**6d. Discount the three stages** (`_equity_value`):
- **Reinvestment rate = g / ROIC** (Damodaran identity), capped at 0.60.
  → `FCFF_t = revenue_t × margin_t × (1−tax) × (1 − reinvestment_rate)`
- **Stage 1 (explicit, 5–6y):** grow revenue at g1, discount each year's FCFF at WACC.
- **Stage 2 (fade, Wide 15y / Narrow 10y / None 5y):** growth fades g1→3% and ROIC
  fades toward `WACC + terminal_excess` (Wide +3pp, Narrow +1pp, None 0).
- **Stage 3 (perpetuity):** `TV = FCFF_terminal / (WACC − 3%)`, discounted back.
- **Enterprise value = Σ PV(stage 1) + PV(stage 2) + PV(terminal).**

**6e. Equity value = EV − debt + cash.  Fair value/share = equity ÷ diluted shares.**

**6f. Reverse DCF** (line 373): bisection-solve the stage-1 growth that makes the model
equal today's market cap → "what is the market actually pricing in?"

**6g. Sensitivity grid** (line 389): equity value across growth ±2pp × WACC ±1pp.

## STEP 7 — Star rating  (`star_rating`, line 414)
`price/fair-value = market cap ÷ equity value`, banded by the uncertainty margin of
safety (Low 10% … Extreme 55%):
5★ ≥MoS discount · 4★ half-MoS discount · 3★ within ±½MoS · 2★ · 1★ ≥MoS premium.

## STEP 8 — Out-of-model flag  (`analyze`, line 472)
Mark names a fundamentals DCF structurally can't value (→ 🚩 banner, excluded from
accuracy stats):
- revenue collapsed >45% in a year (spin-off / restructuring — e.g. GE)
- market implies ≥40% growth (extreme optionality — e.g. TSLA)
- model fair value < 18% of price (ADR / data-distorted — e.g. BABA)

---

## OUTPUT
`analyze` returns one dict with: moat, moat trend, uncertainty, WACC/ke/kd, all DCF
assumptions, enterprise & equity value, fair value/share, star rating, price/FV,
reverse-DCF implied growth, sensitivity grid, and the out-of-model flag — everything
the report (`analyst.py`) and the validators consume. **Nothing is hidden; every dial
is in the returned dict and every constant is at the top of `valuation.py`.**

## Calibration provenance
Every constant above was set against **live Morningstar fair values** — see
`MS_CALIBRATION_LOG.md` for the 12 iterations and the before/after accuracy at each
step (final: matchable-pool median 0.97× MS, moat 77%, 11% hard-opposed).
