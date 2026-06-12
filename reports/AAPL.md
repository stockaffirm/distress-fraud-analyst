# AAPL — Analyst Agent (Morningstar-style intrinsic valuation)
_Information Technology · market cap $4.5T · 10y financial history_

## Verdict
**OVERVALUED** — trading ~200% above intrinsic fair value (Medium uncertainty)
- **Fair Value (equity):** $1.5T  vs market cap $4.5T
- **Fair Value / share:** $100.22  (15.00B dil. shares)
- **Star rating:** ★☆☆☆☆  (price/fair-value = 300%)
- **Economic Moat:** Wide   |   **Moat Trend:** Positive   |   **Uncertainty:** Medium (MoS 20%)

## Economic Moat
**Wide** — median ROIC 70.4% vs ~WACC 9.2% (excess +61.2pp), 10/10y positive, gross margin 40%, op-margin stdev 2.6pp
Trend **Positive**: ROIC 75.5%->95.0%, op-margin 29.8->31.5%

## Key DCF Assumptions (all auditable)
- WACC **9.2%**  (beta 1.00, cost of equity 9.3%, after-tax cost of debt 4.3%)
- Stage-1 revenue growth **2.8%/yr** for 5y (from 5y CAGR 3.3%, haircut 15%)
- Moat-governed fade window: **15 years** (Wide moat)
- Target operating margin **31.5%**  (recent 31.5%, 10y median 28.8%)
- Normalized ROIC **60.0%** → terminal ROIC 12.2%
- Terminal growth 2.5%; terminal value = **25%** of enterprise value

## Reverse DCF — what is the market actually pricing in?
- Today's market cap implies **17.3%/yr** stage-1 revenue growth vs our **2.8%** base case (10y trend-based).
- **Read:** market demands materially FASTER growth than the 10y trend — rich unless a reacceleration story is real.

## Sensitivity — equity fair value ($) by growth × WACC
| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |
|---|---|---|---|
| 0.8% (-2pp vs base) | $1.5T | $1.3T | $1.2T |
| 2.8% (base case) | $1.7T | $1.5T | $1.3T |
| 4.8% (+2pp vs base) | $2.0T | $1.7T | $1.5T |
_(compare every cell to market cap $4.5T)_

## Normalized Economics (10y)
- Revenue CAGR: 3y 4.2%, 5y 3.3%
- ROIC: median 70.4%, recent 95.0%, older 75.5%
- Operating margin: median 28.8%, stdev 2.6pp
- Gross margin median 40%; revenue-growth volatility 10.4pp

## Cross-check vs StockAffirm engine & the Street
- Engine composite **63.4** → tier **HOLD**  (Piotroski 7, Altman-Z 12.8)
- Street: rec_mean 1.98 (Buy, 43 analysts), PT upside 1%
- **Three-way read:** analyst-agent says _OVERVALUED_; engine says _HOLD_; Street says _Buy_.

## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is NOPAT + D&A − capex_proxy − ΔWC)
| FY | Revenue | Op margin | ROIC | FCFF |
|----|---------|-----------|------|------|
| 2025 | $416.2B | 32.0% | 95.4% | $104.7B |
| 2024 | $391.0B | 31.5% | 95.0% | $91.9B |
| 2023 | $383.3B | 29.8% | 87.3% | $93.1B |
| 2022 | $394.3B | 30.3% | 81.7% | $99.3B |
| 2021 | $365.8B | 29.8% | 75.5% | $88.6B |
| 2020 | $274.5B | 24.1% | 65.3% | $62.9B |

> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); moat & uncertainty are quantitative proxies for what a Morningstar analyst judges qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the qualitative read (moat narrative, management guidance, risk factors)._
