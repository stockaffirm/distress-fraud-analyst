# NKE — Analyst Agent (Morningstar-style intrinsic valuation)
_Consumer Discretionary · market cap $63.6B · 10y financial history_

## Verdict
**FAIRLY VALUED** — trading ~2% below intrinsic fair value (Medium uncertainty)
- **Fair Value (equity):** $64.8B  vs market cap $63.6B
- **Fair Value / share:** $43.54  (1.49B dil. shares)
- **Star rating:** ★★★☆☆  (price/fair-value = 98%)
- **Economic Moat:** Wide   |   **Moat Trend:** Negative   |   **Uncertainty:** Medium (MoS 20%)

## Economic Moat
**Wide** — median ROIC 41.3% vs ~WACC 8.7% (excess +32.5pp), 10/10y positive, gross margin 45%, op-margin stdev 2.3pp
Trend **Negative**: ROIC 51.8%->39.4%, op-margin 14.3->11.5%

## Key DCF Assumptions (all auditable)
- WACC **8.7%**  (beta 1.00, cost of equity 9.3%, after-tax cost of debt 4.3%)
- Stage-1 revenue growth **2.5%/yr** for 5y (from 5y CAGR 1.0%, haircut 15%)
- Moat-governed fade window: **15 years** (Wide moat)
- Target operating margin **11.5%**  (recent 11.5%, 10y median 12.2%)
- Normalized ROIC **41.3%** → terminal ROIC 11.7%
- Terminal growth 2.5%; terminal value = **28%** of enterprise value

## Reverse DCF — what is the market actually pricing in?
- Today's market cap implies **2.2%/yr** stage-1 revenue growth vs our **2.5%** base case (10y trend-based).
- **Read:** market is pricing growth ROUGHLY in line with history — valuation hinges on margins/moat durability.

## Sensitivity — equity fair value ($) by growth × WACC
| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |
|---|---|---|---|
| 0.5% (-2pp vs base) | $65.8B | $57.1B | $50.6B |
| 2.5% (base case) | $75.4B | $64.8B | $56.8B |
| 4.5% (+2pp vs base) | $86.7B | $73.8B | $64.2B |
_(compare every cell to market cap $63.6B)_

## Normalized Economics (10y)
- Revenue CAGR: 3y -4.9%, 5y 1.0%
- ROIC: median 41.3%, recent 39.4%, older 51.8%
- Operating margin: median 12.2%, stdev 2.3pp
- Gross margin median 45%; revenue-growth volatility 7.9pp

## Cross-check vs StockAffirm engine & the Street
- Engine composite **34.1** → tier **HOLD**  (Piotroski 3, Altman-Z 3.5)
- Street: rec_mean 2.29 (Hold, 33 analysts), PT upside 41%
- **Three-way read:** analyst-agent says _FAIRLY VALUED_; engine says _HOLD_; Street says _Hold_.

## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is NOPAT + D&A − capex_proxy − ΔWC)
| FY | Revenue | Op margin | ROIC | FCFF |
|----|---------|-----------|------|------|
| 2025 | $46.3B | 8.0% | 25.5% | $3.6B |
| 2024 | $51.4B | 12.3% | 45.7% | $6.1B |
| 2023 | $51.2B | 11.5% | 39.4% | $4.6B |
| 2022 | $46.7B | 14.3% | 51.8% | $4.9B |
| 2021 | $44.5B | 15.6% | 68.5% | $5.3B |
| 2020 | $37.4B | 8.3% | 30.7% | $2.0B |

> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); moat & uncertainty are quantitative proxies for what a Morningstar analyst judges qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the qualitative read (moat narrative, management guidance, risk factors)._
