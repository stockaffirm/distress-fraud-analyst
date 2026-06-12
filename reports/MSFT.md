# MSFT — Analyst Agent (Morningstar-style intrinsic valuation)
_Information Technology · market cap $3.1T · 10y financial history_

## Verdict
**RICH / TRIM** — trading ~11% above intrinsic fair value (Medium uncertainty)
- **Fair Value (equity):** $2.8T  vs market cap $3.1T
- **Fair Value / share:** $374.81  (7.46B dil. shares)
- **Star rating:** ★★☆☆☆  (price/fair-value = 111%)
- **Economic Moat:** Wide   |   **Moat Trend:** Negative   |   **Uncertainty:** Medium (MoS 20%)

## Economic Moat
**Wide** — median ROIC 75.6% vs ~WACC 9.2% (excess +66.4pp), 10/10y positive, gross margin 68%, op-margin stdev 5.9pp
Trend **Negative**: ROIC 86.3%->36.6%, op-margin 41.6->44.6%

## Key DCF Assumptions (all auditable)
- WACC **9.2%**  (beta 1.00, cost of equity 9.3%, after-tax cost of debt 4.3%)
- Stage-1 revenue growth **11.7%/yr** for 5y (from 5y CAGR 13.8%, haircut 15%)
- Moat-governed fade window: **15 years** (Wide moat)
- Target operating margin **44.6%**  (recent 44.6%, 10y median 39.3%)
- Normalized ROIC **60.0%** → terminal ROIC 12.2%
- Terminal growth 2.5%; terminal value = **36%** of enterprise value

## Reverse DCF — what is the market actually pricing in?
- Today's market cap implies **13.1%/yr** stage-1 revenue growth vs our **11.7%** base case (10y trend-based).
- **Read:** market is pricing growth ROUGHLY in line with history — valuation hinges on margins/moat durability.

## Sensitivity — equity fair value ($) by growth × WACC
| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |
|---|---|---|---|
| 9.7% (-2pp vs base) | $2.9T | $2.4T | $2.1T |
| 11.7% (base case) | $3.3T | $2.8T | $2.4T |
| 13.7% (+2pp vs base) | $3.9T | $3.2T | $2.8T |
_(compare every cell to market cap $3.1T)_

## Normalized Economics (10y)
- Revenue CAGR: 3y 15.3%, 5y 13.8%
- ROIC: median 75.6%, recent 36.6%, older 86.3%
- Operating margin: median 39.3%, stdev 5.9pp
- Gross margin median 68%; revenue-growth volatility 4.0pp

## Cross-check vs StockAffirm engine & the Street
- Engine composite **52.1** → tier **HOLD**  (Piotroski 4, Altman-Z 8.5)
- Street: rec_mean 1.34 (Buy, 55 analysts), PT upside 35%
- **Three-way read:** analyst-agent says _RICH / TRIM_; engine says _HOLD_; Street says _Buy_.

## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is NOPAT + D&A − capex_proxy − ΔWC)
| FY | Revenue | Op margin | ROIC | FCFF |
|----|---------|-----------|------|------|
| 2025 | $281.7B | 45.6% | 36.2% | $36.5B |
| 2024 | $245.1B | 44.6% | 36.6% | $53.1B |
| 2023 | $211.9B | 41.8% | 50.4% | $51.8B |
| 2022 | $198.3B | 42.1% | 64.9% | $58.3B |
| 2021 | $168.1B | 41.6% | 86.3% | $46.1B |
| 2020 | $143.0B | 37.0% | 98.0% | $40.7B |

> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); moat & uncertainty are quantitative proxies for what a Morningstar analyst judges qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the qualitative read (moat narrative, management guidance, risk factors)._
