# ANET — Analyst Agent (Morningstar-style intrinsic valuation)
_Information Technology · market cap $194.3B · 10y financial history_

## Verdict
**OVERVALUED** — trading ~39% above intrinsic fair value (High uncertainty)
- **Fair Value (equity):** $140.1B  vs market cap $194.3B
- **Fair Value / share:** $109.78  (1.28B dil. shares)
- **Star rating:** ★☆☆☆☆  (price/fair-value = 139%)
- **Economic Moat:** Wide   |   **Moat Trend:** Positive   |   **Uncertainty:** High (MoS 30%)

## Economic Moat
**Wide** — median ROIC 140.4% vs ~WACC 10.3% (excess +130.1pp), 10/10y positive, gross margin 64%, op-margin stdev 8.8pp
Trend **Positive**: ROIC 134.3%->152.1%, op-margin 31.4->42.0%

## Key DCF Assumptions (all auditable)
- WACC **10.3%**  (beta 1.20, cost of equity 10.3%, after-tax cost of debt 4.3%)
- Stage-1 revenue growth **20.0%/yr** for 5y (from 5y CAGR 32.2%, haircut 15%)
- Moat-governed fade window: **15 years** (Wide moat)
- Target operating margin **42.0%**  (recent 42.0%, 10y median 32.4%)
- Normalized ROIC **60.0%** → terminal ROIC 13.3%
- Terminal growth 2.5%; terminal value = **41%** of enterprise value

## Reverse DCF — what is the market actually pricing in?
- Today's market cap implies **24.6%/yr** stage-1 revenue growth vs our **20.0%** base case (10y trend-based).
- **Read:** market demands materially FASTER growth than the 10y trend — rich unless a reacceleration story is real.

## Sensitivity — equity fair value ($) by growth × WACC
| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |
|---|---|---|---|
| 18.0% (-2pp vs base) | $143.7B | $121.9B | $105.2B |
| 20.0% (base case) | $166.4B | $140.1B | $120.0B |
| 22.0% (+2pp vs base) | $193.1B | $161.4B | $137.3B |
_(compare every cell to market cap $194.3B)_

## Normalized Economics (10y)
- Revenue CAGR: 3y 24.0%, 5y 32.2%
- ROIC: median 140.4%, recent 152.1%, older 134.3%
- Operating margin: median 32.4%, stdev 8.8pp
- Gross margin median 64%; revenue-growth volatility 15.3pp

## Cross-check vs StockAffirm engine & the Street
- Engine composite **47.5** → tier **SELL**  (Piotroski 2, Altman-Z 16.7)
- Street: rec_mean 1.30 (Buy, 27 analysts), PT upside 22%
- **Three-way read:** analyst-agent says _OVERVALUED_; engine says _SELL_; Street says _Buy_.

## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is NOPAT + D&A − capex_proxy − ΔWC)
| FY | Revenue | Op margin | ROIC | FCFF |
|----|---------|-----------|------|------|
| 2025 | $9.0B | 42.8% | 195.8% | $4.5B |
| 2024 | $7.0B | 42.0% | 152.1% | $3.3B |
| 2023 | $5.9B | 38.5% | 88.0% | $2.3B |
| 2022 | $4.4B | 34.9% | 70.1% | $-320.5M |
| 2021 | $2.9B | 31.4% | 146.5% | $757.2M |
| 2020 | $2.3B | 30.2% | 134.3% | $500.3M |

> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); moat & uncertainty are quantitative proxies for what a Morningstar analyst judges qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the qualitative read (moat narrative, management guidance, risk factors)._
