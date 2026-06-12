# JPM — Analyst Agent (Morningstar-style intrinsic valuation)
_Financials · market cap $837.0B · 10y financial history_

> ⚠️ **Enterprise DCF NOT valid for this sector (Financials).** For banks/insurers/REITs, debt & float are the operating model, so an FCFF-to-firm DCF is meaningless. The fair value below is **suppressed** — value these on **excess-return / DDM / P-B×ROE** instead. Moat, uncertainty, and the engine/Street cross-check below remain valid.

## Verdict
**DCF N/A (financial)** — enterprise DCF invalid for this sector — see warning above
- **Fair Value / Star rating:** _suppressed — DCF invalid for financials (see warning above)_
- **Economic Moat:** None   |   **Moat Trend:** Stable   |   **Uncertainty:** High (MoS 30%)

## Economic Moat
**None** — no positive invested-capital returns computable
Trend **Stable**: insufficient history

## Key DCF Assumptions (all auditable)
- WACC **8.1%**  (beta 1.20, cost of equity 10.3%, after-tax cost of debt 4.3%)
- Stage-1 revenue growth **18.6%/yr** for 5y (from 5y CAGR 21.8%, haircut 15%)
- Moat-governed fade window: **5 years** (None moat)
- Target operating margin **25.9%**  (recent 25.9%, 10y median 30.6%)
- Normalized ROIC **8.1%** → terminal ROIC 8.1%
- Terminal growth 2.5%; terminal value = **90%** of enterprise value

## Reverse DCF — what is the market actually pricing in?
- Today's market cap implies **-10.0%/yr** stage-1 revenue growth vs our **18.6%** base case (10y trend-based).
- **Read:** market is pricing growth BELOW the historical trend — potential value if the franchise holds.

## Sensitivity — equity fair value ($) by growth × WACC
| Stage-1 growth ↓ / WACC → | −1.0% | base | +1.0% |
|---|---|---|---|
| 16.6% (-2pp vs base) | $3.5T | $3.2T | $3.0T |
| 18.6% (base case) | $3.7T | $3.4T | $3.1T |
| 20.6% (+2pp vs base) | $3.9T | $3.5T | $3.3T |
_(compare every cell to market cap $837.0B)_

## Normalized Economics (10y)
- Revenue CAGR: 3y 8.2%, 5y 21.8%
- ROIC: median n/a, recent n/a, older n/a
- Operating margin: median 30.6%, stdev 5.8pp
- Gross margin median 83%; revenue-growth volatility 17.4pp

## Cross-check vs StockAffirm engine & the Street
- Engine composite **40.8** → tier **HOLD**  (Piotroski n/a, Altman-Z n/a)
- Street: rec_mean 2.17 (Hold, 21 analysts), PT upside 10%
- **Three-way read:** analyst-agent says _DCF N/A (financial)_; engine says _HOLD_; Street says _Hold_.

## Year-by-year FCFF (derived; cash-flow stmts not cached, so FCFF is NOPAT + D&A − capex_proxy − ΔWC)
| FY | Revenue | Op margin | ROIC | FCFF |
|----|---------|-----------|------|------|
| 2025 | $280.3B | 25.9% | n/a | $53.0B |
| 2024 | $278.9B | 26.9% | n/a | $56.4B |
| 2023 | $239.4B | 25.7% | n/a | $47.1B |
| 2022 | $154.8B | 29.8% | n/a | $37.0B |
| 2021 | $127.2B | 46.8% | n/a | $48.4B |
| 2020 | $129.9B | 27.6% | n/a | $27.8B |

> _Limitations: capex/ΔWC are proxies (cash-flow statements not in cache); moat & uncertainty are quantitative proxies for what a Morningstar analyst judges qualitatively from filings. See ANALYST_AGENT.md for the LLM layer that adds the qualitative read (moat narrative, management guidance, risk factors)._
