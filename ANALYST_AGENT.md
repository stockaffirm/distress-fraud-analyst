# Analyst Agent — a Morningstar-style intrinsic-valuation analyst

**What it is:** a self-contained agent that does what a Morningstar equity analyst
does — builds an intrinsic **fair value** from a multi-stage DCF, rates the
**economic moat**, **moat trend**, and **fair-value uncertainty**, and outputs a
**star rating** and a buy/trim/avoid verdict — then cross-checks it against the
StockAffirm factor engine and the Street.

It is deliberately **independent** of StockAffirm's factor model. StockAffirm ranks
stocks *relative* to each other on percentile factors (no notion of absolute worth).
This agent computes *absolute* intrinsic value per share. Two different lenses → a
genuine second opinion. (This directly attacks StockAffirm's documented GAP-25:
quality/moat weighted 0.)

> Status: **analysis tool, read-only.** Reads cached fundamentals + recommendations.csv.
> Writes nothing to the engine. Lives entirely under `stockaffirmtodos/analyst_agent/`.

---

## How a Morningstar analyst actually works (what we replicate)

1. **Economic moat** (None / Narrow / Wide) — can the business earn returns on
   capital above its cost of capital, and for **how long**? Five sources: intangibles,
   switching costs, network effect, cost advantage, efficient scale.
2. **Moat trend** (Positive / Stable / Negative) — is that advantage widening or eroding?
3. A **3-stage DCF**: explicit forecast → fade toward cost of capital → perpetuity.
   The moat **mechanically sets the fade length** — wide moats compound excess
   returns for ~15–20 years before fading; no-moat names fade almost immediately.
4. **Fair-value uncertainty** (Low → Extreme) — sets the **margin of safety**: how far
   below fair value the price must fall before it's a 5-star buy.
5. **Star rating** from price ÷ fair value, scaled by that margin of safety.

---

## What this agent computes (the quantitative core — `valuation.py`)

| Morningstar concept | Our quantitative proxy |
|---|---|
| Economic moat | ROIC − WACC excess spread × **durability** (yrs of positive ROIC) × gross-margin level × earnings stability |
| Moat trend | recent (3y) vs older (yrs 4–6) ROIC + operating-margin direction |
| Fair-value uncertainty | volatility of operating margin + revenue growth + leverage + profitability cushion |
| WACC | CAPM cost of equity (β from uncertainty) + after-tax cost of debt, market-weighted |
| Stage-1 growth | trailing 5y revenue CAGR, haircut 15%, capped 20%, floored at terminal |
| Fade window | **Wide 15y / Narrow 10y / None 5y** |
| Reinvestment | fundamental identity: reinvestment rate = g ÷ ROIC (Damodaran) |
| Fair value | PV(FCFF, 3 stages) + cash − debt → equity value, ÷ shares → per-share |
| Star rating | (market cap ÷ fair value) banded by the uncertainty margin of safety |

**Two signature outputs beyond a plain DCF:**
- **Reverse DCF** — solves for the growth rate today's price implies, so you can ask
  "is the market's implied growth realistic?" (e.g. *AAPL's $4.5T price implies
  ~17%/yr revenue growth vs a 2.8% trend* — a precise, falsifiable bear case).
- **Sensitivity grid** — fair value across growth ±2pp × WACC ±1pp, so the whole
  answer is auditable, not a single false-precision number.

### Data source
10 years of annual income statements + balance sheets, cached at
`stockaffirm/cache/data/raw/fundamentals_annual_zips/`. Cash-flow statements are
**not** cached, so FCFF is derived: `NOPAT + D&A − capex_proxy − ΔWorkingCapital`,
where D&A ≈ EBITDA − operating income and capex ≈ Δnet-PP&E + D&A. These are
proxies — flagged as such in every report.

### Known limitations (be honest, like Morningstar's methodology page)
- **Conservative growth bias.** Trailing-CAGR base case under-prices genuine
  reaccelerators (services, AI). *Mitigant:* the reverse DCF + sensitivity make the
  growth assumption explicit and invertible rather than hidden.
- **Buyback distortion.** Heavy repurchasers (AAPL, ORLY) shrink book equity →
  inflated ROIC and occasionally negative equity. ROIC is capped at 60% and faded;
  still, read ROIC on these names with care. (This is the same S-7 distortion the
  factor engine suffers.)
- **No qualitative moat read** in the core — that's the LLM layer below.
- Proxy FCFF (no real capex/cash-flow statement) — ±10–20% on capital-heavy names.

---

## The LLM layer — what turns the calculator into an *analyst* agent

Morningstar's real edge is **human judgment**: reading the 10-K, assessing whether
the moat is durable, capturing forward guidance, weighing management. That's the part
an LLM agent (this Claude session, or a spawned sub-agent) supplies on top of the
deterministic math. Workflow per ticker:

1. **Run the quant core** → `python3 analyst.py TICKER --save`. Gives FVE, moat,
   uncertainty, star rating, reverse-DCF implied growth, sensitivity.
2. **Qualitative moat check** (web / 10-K): which of the five moat sources actually
   apply? Does the quant "Wide" hold up narratively, or is it just buyback-inflated
   ROIC? Confirm or override the moat rating with a one-line rationale.
3. **Moat-trend / disruption read:** competitive threats, share shifts, fad risk
   (e.g. NKE) — the things no feed captures (StockAffirm failure-mode #6).
4. **Forward guidance capture** (8-K Exhibit 99.1 / earnings call): is management
   guiding above or below the model's stage-1 growth? Adjust the base case and note it.
5. **Reverse-DCF reality check:** is the market's implied growth achievable given the
   moat and TAM? This is the single most decision-useful step.
6. **Write the verdict:** reconcile analyst-agent vs StockAffirm engine vs Street.
   Three-way disagreement is the highest-signal situation (e.g. ANET/ORLY:
   engine SELL, Street BUY, analyst-agent OVERVALUED-on-cash-flows → "great business,
   wrong price").

This division of labour mirrors Morningstar exactly: a **quant model** for structure
and consistency, a **human/LLM analyst** for judgment and narrative.

---

## Usage

```
python3 analyst.py AAPL                  # one report to stdout
python3 analyst.py AAPL MSFT NKE ANET    # several
python3 analyst.py --save AAPL           # also write reports/AAPL.md
python3 analyst.py --batch tickers.txt   # one ticker per line
```

Files:
- `data_loader.py` — read-only loader (cached fundamentals + recommendations.csv)
- `valuation.py` — moat / WACC / 3-stage DCF / reverse-DCF / uncertainty / stars
- `analyst.py` — CLI + Morningstar-style report renderer
- `reports/` — saved per-ticker reports

## Roadmap / calibration ideas (not yet built)
- Per-sector β and terminal-growth defaults (defensives like KO warrant β≈0.6).
- Segment-level growth for reaccelerators (split services vs hardware).
- Pull real cash-flow statements (EDGAR XBRL) to replace proxy FCFF.
- Beneish M-score + accrual flags as a fraud/earnings-quality overlay.
- Batch-run the full 5,022 and diff fair-value stars vs engine tiers to surface
  the largest quality-vs-price disagreements (the GAP-25 worklist).
