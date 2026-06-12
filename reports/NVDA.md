# NVDA — Analyst Agent (Morningstar-style intrinsic valuation)
_Information Technology · market cap $5.0T · 10y financial history_

## Verdict
**RICH / TRIM** — trading ~32% above intrinsic fair value (Very High uncertainty)
- **Fair Value (equity):** $3.8T  vs market cap $5.0T
- **Fair Value / share:** $153.99  (24.51B dil. shares)
- **Star rating:** ★★☆☆☆  (price/fair-value = 132%)
- **Economic Moat:** Wide   |   **Moat Trend:** Positive   |   **Uncertainty:** Very High (MoS 40%)

## Economic Moat
**Wide** — median ROIC 97.2% vs ~WACC 11.5% (excess +85.7pp), 10/10y positive, gross margin 62%, op-margin stdev 15.1pp
Trend **Positive**: ROIC 36.2%->108.7%, op-margin 27.2->60.4%

## Key DCF Assumptions (all auditable)
- WACC **11.5%**  (beta 1.45, cost of equity 11.5%, after-tax cost of debt 4.3%)
- Stage-1 revenue growth **20.0%/yr** for 5y (from 5y CAGR 68.3%, haircut 15%)
- Moat-governed fade window: **15 years** (Wide moat)
- Target operating margin **60.4%**  (recent 60.4%, 10y median 32.8%)
- Normalized ROIC **60.0%** → terminal ROIC 14.5%
- Terminal growth 2.5%; terminal value = **35%** of enterprise value

## Reverse DCF — what is the market actually pricing in?
- Today's market cap implies **23.8%/yr** stage-1 revenue growth vs our **20.0%** base case (10y trend-based).
- **Read:** market demands materially FASTER growth than the 10y trend — rich unless a reacceleration story is real.

## Sensitivity — equity fair value ($) by growth × WACC
| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |
|---|---|---|---|
| 18.0% (-2pp vs base) | $3.8T | $3.3T | $2.8T |
| 20.0% (base case) | $4.4T | $3.8T | $3.3T |
| 22.0% (+2pp vs base) | $5.2T | $4.4T | $3.7T |
_(compare every cell to market cap $5.0T)_

## Normalized Economics (10y)
- Revenue CAGR: 3y 88.3%, 5y 68.3%
- ROIC: median 97.2%, recent 108.7%, older 36.2%
- Operating margin: median 32.8%, stdev 15.1pp
- Gross margin median 62%; revenue-growth volatility 43.3pp

## Cross-check vs StockAffirm engine & the Street
- Engine composite **53.3** → tier **HOLD**  (Piotroski 6, Altman-Z 51.1)
- Street: rec_mean 1.29 (Buy, 59 analysts), PT upside 46%
- **Three-way read:** analyst-agent says _RICH / TRIM_; engine says _HOLD_; Street says _Buy_.

## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is NOPAT + D&A − capex_proxy − ΔWC)
| FY | Revenue | Op margin | ROIC | FCFF |
|----|---------|-----------|------|------|
| 2026 | $215.9B | 60.4% | 107.2% | $83.4B |
| 2025 | $130.5B | 62.4% | 158.5% | $54.0B |
| 2024 | $60.9B | 54.1% | 108.7% | $24.1B |
| 2023 | $27.0B | 15.7% | 21.4% | $874.0M |
| 2022 | $26.9B | 37.3% | 60.2% | $6.9B |
| 2021 | $16.7B | 27.2% | 36.2% | $2.8B |

> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); moat & uncertainty are quantitative proxies for what a Morningstar analyst judges qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the qualitative read (moat narrative, management guidance, risk factors)._
