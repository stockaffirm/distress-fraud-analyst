# Calibration Diagnostics — Analyst Agent vs population

Scored **4026** tickers with usable fundamentals.

Enterprise-DCF-valid (non-financial): **2973**

## Star-rating distribution (1=overvalued .. 5=deep value)
- 5★: 1595 (54%)  █████████████████████
- 4★: 125 (4%)  █
- 3★: 231 (8%)  ███
- 2★: 95 (3%)  █
- 1★: 927 (31%)  ████████████

**Overvalued share (1-2★): 34%.** A well-calibrated model centered on market ≈ ~40-50% here; looks balanced.

## price ÷ fair-value distribution
- all valid: min 0.00 | p10 0.12 | median 0.69 | p90 4.22 | max 637.42
  (1.0 = fairly valued; >1 market above model; median far from 1.0 ⇒ bias)

## Median price/FV by sector  (systematic bias shows here)
- Materials: median 0.90  (n=270)
- Information Technology: median 0.86  (n=569)
- Consumer Staples: median 0.78  (n=87)
- Health Care: median 0.78  (n=580)
- Industrials: median 0.77  (n=475)
- Energy: median 0.76  (n=111)
- Utilities: median 0.65  (n=99)
- Unknown: median 0.51  (n=355)
- Consumer Discretionary: median 0.44  (n=306)
- Communication Services: median 0.44  (n=121)

## Moat distribution
- Wide: 491 (12%)
- Narrow: 1636 (41%)
- None: 1899 (47%)

_Morningstar coverage is ~10% Wide / ~40% Narrow / ~50% None. Large deviation ⇒ moat thresholds need tightening._

## Reverse-DCF: market-implied minus model base growth
- min -0.38 | p10 -0.20 | median -0.06 | p90 0.21 | max 0.37
- median gap -5.8pp. centered ⇒ growth assumption roughly right.

## Three-way agreement (where the value-add is)
- analyst-agent BUY while engine SELL: 418
- analyst-agent SELL while engine BUY: 9
  (these disagreements are the GAP-25 worklist — quality/price tension)

