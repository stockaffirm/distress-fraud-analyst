# ORLY — Analyst Agent (Morningstar-style intrinsic valuation)
_Consumer Discretionary · market cap $74.9B · 10y financial history_

## Verdict
**OVERVALUED** — trading ~50% above intrinsic fair value (Low uncertainty)
- **Fair Value (equity):** $50.0B  vs market cap $74.9B
- **Fair Value / share:** $58.38  (0.86B dil. shares)
- **Star rating:** ★☆☆☆☆  (price/fair-value = 150%)
- **Economic Moat:** Wide   |   **Moat Trend:** Negative   |   **Uncertainty:** Low (MoS 10%)

## Economic Moat
**Wide** — median ROIC 50.2% vs ~WACC 8.2% (excess +42.0pp), 10/10y positive, gross margin 52%, op-margin stdev 0.9pp
Trend **Negative**: ROIC 66.8%->60.4%, op-margin 20.8->19.5%

## Key DCF Assumptions (all auditable)
- WACC **8.2%**  (beta 0.85, cost of equity 8.5%, after-tax cost of debt 4.3%)
- Stage-1 revenue growth **6.4%/yr** for 5y (from 5y CAGR 7.5%, haircut 15%)
- Moat-governed fade window: **15 years** (Wide moat)
- Target operating margin **19.5%**  (recent 19.5%, 10y median 19.6%)
- Normalized ROIC **50.2%** → terminal ROIC 11.2%
- Terminal growth 2.5%; terminal value = **35%** of enterprise value

## Reverse DCF — what is the market actually pricing in?
- Today's market cap implies **11.2%/yr** stage-1 revenue growth vs our **6.4%** base case (10y trend-based).
- **Read:** market demands materially FASTER growth than the 10y trend — rich unless a reacceleration story is real.

## Sensitivity — equity fair value ($) by growth × WACC
| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |
|---|---|---|---|
| 4.4% (-2pp vs base) | $51.7B | $42.3B | $35.5B |
| 6.4% (base case) | $61.4B | $50.0B | $41.7B |
| 8.4% (+2pp vs base) | $73.1B | $59.0B | $48.9B |
_(compare every cell to market cap $74.9B)_

## Normalized Economics (10y)
- Revenue CAGR: 3y 6.0%, 5y 7.5%
- ROIC: median 50.2%, recent 60.4%, older 66.8%
- Operating margin: median 19.6%, stdev 0.9pp
- Gross margin median 52%; revenue-growth volatility 3.6pp

## Cross-check vs StockAffirm engine & the Street
- Engine composite **47.7** → tier **SELL**  (Piotroski 5, Altman-Z 3.9)
- Street: rec_mean 1.58 (Buy, 24 analysts), PT upside 22%
- **Three-way read:** analyst-agent says _OVERVALUED_; engine says _SELL_; Street says _Buy_.

## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is NOPAT + D&A − capex_proxy − ΔWC)
| FY | Revenue | Op margin | ROIC | FCFF |
|----|---------|-----------|------|------|
| 2025 | $17.8B | 19.5% | 51.2% | $1.9B |
| 2024 | $16.7B | 19.5% | 60.4% | $2.0B |
| 2023 | $15.8B | 20.2% | 66.8% | $1.7B |
| 2022 | $14.4B | 20.5% | 68.1% | $2.5B |
| 2021 | $13.3B | 21.9% | 66.8% | $2.6B |
| 2020 | $11.6B | 20.8% | 49.3% | $2.1B |

> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); moat & uncertainty are quantitative proxies for what a Morningstar analyst judges qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the qualitative read (moat narrative, management guidance, risk factors)._
