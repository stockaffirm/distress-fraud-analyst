# KO — Analyst Agent (Morningstar-style intrinsic valuation)
_Consumer Staples · market cap $342.0B · 10y financial history_

## Verdict
**OVERVALUED** — trading ~224% above intrinsic fair value (Medium uncertainty)
- **Fair Value (equity):** $105.6B  vs market cap $342.0B
- **Fair Value / share:** $24.48  (4.31B dil. shares)
- **Star rating:** ★☆☆☆☆  (price/fair-value = 324%)
- **Economic Moat:** Narrow   |   **Moat Trend:** Stable   |   **Uncertainty:** Medium (MoS 20%)

## Economic Moat
**Narrow** — median ROIC 15.1% vs ~WACC 8.7% (excess +6.4pp), 10/10y positive, gross margin 61%, op-margin stdev 2.7pp
Trend **Stable**: ROIC 14.8%->16.7%

## Key DCF Assumptions (all auditable)
- WACC **8.7%**  (beta 1.00, cost of equity 9.3%, after-tax cost of debt 4.3%)
- Stage-1 revenue growth **4.7%/yr** for 5y (from 5y CAGR 5.5%, haircut 15%)
- Moat-governed fade window: **10 years** (Narrow moat)
- Target operating margin **24.7%**  (recent 24.7%, 10y median 26.0%)
- Normalized ROIC **15.1%** → terminal ROIC 9.7%
- Terminal growth 2.5%; terminal value = **45%** of enterprise value

## Reverse DCF — what is the market actually pricing in?
- Today's market cap implies **24.0%/yr** stage-1 revenue growth vs our **4.7%** base case (10y trend-based).
- **Read:** market demands materially FASTER growth than the 10y trend — rich unless a reacceleration story is real.

## Sensitivity — equity fair value ($) by growth × WACC
| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |
|---|---|---|---|
| 2.7% (-2pp vs base) | $117.0B | $96.8B | $81.4B |
| 4.7% (base case) | $128.9B | $105.6B | $87.9B |
| 6.7% (+2pp vs base) | $142.2B | $115.3B | $95.0B |
_(compare every cell to market cap $342.0B)_

## Normalized Economics (10y)
- Revenue CAGR: 3y 2.4%, 5y 5.5%
- ROIC: median 15.1%, recent 16.7%, older 14.8%
- Operating margin: median 26.0%, stdev 2.7pp
- Gross margin median 61%; revenue-growth volatility 9.7pp

## Cross-check vs StockAffirm engine & the Street
- Engine composite **59.9** → tier **HOLD**  (Piotroski 7, Altman-Z 5.2)
- Street: rec_mean 1.75 (Buy, 23 analysts), PT upside 8%
- **Three-way read:** analyst-agent says _OVERVALUED_; engine says _HOLD_; Street says _Buy_.

## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is NOPAT + D&A − capex_proxy − ΔWC)
| FY | Revenue | Op margin | ROIC | FCFF |
|----|---------|-----------|------|------|
| 2025 | $47.9B | 28.7% | 17.7% | $5.9B |
| 2024 | $47.1B | 21.2% | 14.4% | $12.8B |
| 2023 | $45.8B | 24.7% | 16.7% | $9.6B |
| 2022 | $43.0B | 25.4% | 16.7% | $9.3B |
| 2021 | $38.7B | 26.7% | 14.8% | $11.9B |
| 2020 | $33.0B | 27.3% | 13.5% | $8.0B |

> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); moat & uncertainty are quantitative proxies for what a Morningstar analyst judges qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the qualitative read (moat narrative, management guidance, risk factors)._
