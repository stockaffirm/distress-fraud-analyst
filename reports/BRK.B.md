# BRK.B — Analyst Agent (Morningstar-style intrinsic valuation)
_Financials · market cap $1.1T · 10y financial history_

## Verdict
**OVERVALUED** — trading ~95% above intrinsic fair value (High uncertainty)
- **Fair Value (equity):** $538.8B  vs market cap $1.1T
- **Fair Value / share:** $249.77  (2.16B dil. shares)
- **Star rating:** ★☆☆☆☆  (price/fair-value = 195%)
- **Economic Moat:** None   |   **Moat Trend:** Stable   |   **Uncertainty:** High (MoS 30%)

## Economic Moat
**None** — median ROIC 5.9% vs ~WACC 9.6% (excess -3.8pp), 9/10y positive, gross margin 47%, op-margin stdev 7.4pp
Trend **Stable**: ROIC 5.5%->6.9%

## Key DCF Assumptions (all auditable)
- WACC **9.6%**  (beta 1.20, cost of equity 10.3%, after-tax cost of debt 4.3%)
- Stage-1 revenue growth **5.7%/yr** for 5y (from 5y CAGR 6.7%, haircut 15%)
- Moat-governed fade window: **5 years** (None moat)
- Target operating margin **11.2%**  (recent 11.2%, 10y median 11.2%)
- Normalized ROIC **5.9%** → terminal ROIC 9.6%
- Terminal growth 2.5%; terminal value = **77%** of enterprise value

## Reverse DCF — what is the market actually pricing in?
- Today's market cap implies **25.1%/yr** stage-1 revenue growth vs our **5.7%** base case (10y trend-based).
- **Read:** market demands materially FASTER growth than the 10y trend — rich unless a reacceleration story is real.

## Sensitivity — equity fair value ($) by growth × WACC
| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |
|---|---|---|---|
| 3.7% (-2pp vs base) | $604.5B | $559.8B | $524.0B |
| 5.7% (base case) | $587.1B | $538.8B | $500.7B |
| 7.7% (+2pp vs base) | $617.8B | $563.6B | $520.7B |
_(compare every cell to market cap $1.1T)_

## Normalized Economics (10y)
- Revenue CAGR: 3y -0.1%, 5y 6.7%
- ROIC: median 5.9%, recent 6.9%, older 5.5%
- Operating margin: median 11.2%, stdev 7.4pp
- Gross margin median 47%; revenue-growth volatility 13.7pp

## Cross-check vs StockAffirm engine & the Street
- Engine composite **48.5** → tier **HOLD**  (Piotroski n/a, Altman-Z n/a)
- Street: rec_mean 1.75 (Buy, 3 analysts), PT upside 7%
- **Three-way read:** analyst-agent says _OVERVALUED_; engine says _HOLD_; Street says _Buy_.

## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is NOPAT + D&A − capex_proxy − ΔWC)
| FY | Revenue | Op margin | ROIC | FCFF |
|----|---------|-----------|------|------|
| 2025 | $348.2B | 11.2% | 6.9% | $18.3B |
| 2024 | $349.6B | 12.4% | 8.3% | $31.4B |
| 2023 | $348.7B | 10.5% | 5.9% | $10.1B |
| 2022 | $291.8B | 11.9% | 5.5% | $11.4B |
| 2021 | $268.7B | 12.9% | 6.1% | $16.9B |
| 2020 | $237.5B | 6.3% | 2.8% | $636.1M |

> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); moat & uncertainty are quantitative proxies for what a Morningstar analyst judges qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the qualitative read (moat narrative, management guidance, risk factors)._
