# Distress & Fraud Screening Subagent — complete build & operation spec

A companion to the valuation Analyst Agent whose only job is **risk avoidance**: surface the
names to *not* own because they're on the verge of bankruptcy or are juicing their reported
numbers — and, separately, the badly-stressed names that can **recover**.

This document is **self-contained**: an agent given only this file (plus the data cache) can
rebuild and operate the screen exactly. Every formula, coefficient, threshold, data-field
mapping, and the validation protocol are below.

---

## 0. Architecture — four layers (read this first)

The single most important design fact, learned from an adversarial audit (§9): **a fundamentals
snapshot produces CANDIDATES; news/events CONFIRM them.** A pure-fundamentals screen cannot
tell a well-funded cash-burner (just raised equity, drug launching) from a failing one, nor a
one-time non-cash accrual from manipulation. So the system is layered:

```
  Layer 1  FUNDAMENTALS  (distress_screen.py)  — whole universe, fast, offline
           7 models on cached financials -> candidate buckets
                     |
  Layer 2  DIRECT-API    (massive_api.py + edgar_api.py)   — live, cached per-ticker
           massive_api : full focused article corpus (ALL headlines + body text),
                         short interest (days-to-cover), capital-raise detection
           edgar_api   : SEC 10-K auditor going-concern opinion, material weakness,
                         covenant violations (7-day cache; full-text keyword extraction)
           -> corroborates (boosts confidence), escalates, or overrides the bucket
                     |
  Layer 3  LLM INVESTIGATION (llm_client.py, explain=True)  — on-demand per name
           4 grounding sources: av_financial (fundamentals) · av_price_data (24mo monthly
           prices) · massive_news (complete article corpus with descriptions) · edgar_10k
           (going-concern/MW/covenant + MD&A) -> structured verdict with grounded claims
                     |
  Layer 4  LIVE AUDIT   (web / on-demand deep-dive)
           ad-hoc web research for the highest-stakes names
           reference impl: the `distress-avoid-audit` workflow (§9)
```

Layer 1 is exhaustive but blind to events; Layer 2 is the primary live cross-check (handles the
routine case: funded cash-burner, news-confirmed going-concern, recent raise); Layer 3 is the
deep analytical layer with full grounding (prices, complete news, 10-K); Layer 4 is for the
highest-stakes ad-hoc confirmations. **Do not ship an AVOID-fraud verdict on Layer 1 alone — run
at minimum Layer 2, ideally Layer 3.**

---

## 1. Buckets

| Bucket | Meaning |
|---|---|
| 🟥 **AVOID — bankruptcy** (`insolvency`) | over-levered / loss-eroded operating business genuinely failing |
| 🟥 **AVOID — bankruptcy** (`cash_burn`) | pre-profit company burning cash, dependent on raising more capital |
| 🟥 **AVOID — fraud** | earnings can't convert to cash + corroboration (forensic, "investigate") |
| 🟧 **DISTRESSED — recoverable** | badly stressed but solvent, cash-generating, and turning |
| 🟨 **WATCH** | stress signals (or a demoted forensic earnings-quality flag), not terminal |
| 🟩 **CLEAR** | no material distress or manipulation signal |

`insolvency` vs `cash_burn` is an honesty distinction the audit forced: a funded biotech that
might fail a trial is *not* the same risk as an over-levered retailer going under.

---

## 2. Files & run commands

| File | Role |
|---|---|
| `distress_screen.py` | Layer-1 engine — `screen(ticker, ctx, hist, news=None)` returns the bucket dict |
| `distress_batch.py` | runs the whole universe (Layer-1 only) → `DISTRESS_SCREEN.csv` + `DISTRESS_REPORT.md` |
| `data_loader.py` | read-only loader — `full_history(fund)` (income+balance+**cash-flow**); `price_history(ticker, months=24)` (AV monthly prices) |
| **`massive_api.py`** | **Layer-2 DIRECT API** — `event_scan(ticker)`: full article corpus (no cap, with body text), short interest, recent raises |
| **`edgar_api.py`** | **Layer-2 EDGAR 10-K** — `edgar_10k_signals(ticker)`: going-concern, material weakness, covenant risk (7-day cache, full-text) |
| **`llm_client.py`** | **Layer-3 LLM** — `explain(ticker, result, ...)`: 4-source grounded prompt → structured verdict |
| **`api_server.py`** | HTTP API server — `POST /analyze` (explain=True triggers Layer-3) + `/analyze/batch` |
| **`calibrate.py`** | per-ticker validate→bucket→**effective_bucket** (screen ∪ API ∪ EDGAR); `--ticker/--review` |
| **`state_db.py`** | durable SQLite status table (`tickers`) — the resumable "what to (re)process" store |
| **`loop_runner.py`** | head-less, time-budgeted, cron-callable runner — processes all DUE tickers |
| `distress_news.py` | the older 2-week-cache news scan (Layer-2 fallback; superseded by `massive_api.py`) |
| `CALIBRATION_LOG.md` | the calibration protocol + full change log + how to run/resume the loop |

```
python3 distress_screen.py TSLA CCL AAL        # detail, one or many
python3 distress_screen.py --json NVDA          # raw dict
python3 distress_news.py NVAX GROW              # recent news events
python3 distress_batch.py                        # whole universe (~4s, ~4,200 names)
python3 distress_batch.py --limit 300            # quick sample
```

---

## 3. Data sources

**USED (read-only):**
- **Engine fundamentals cache** `stockaffirm/cache/data/raw/fundamentals_annual_zips/*.zip` —
  10y annual **income statements, balance sheets, AND cash-flow statements**. The cash-flow
  statements live under the top-level `cash_flows` key (the original valuation loader missed
  them), so **operating cash flow, real D&A, real capex, accruals, Beneish-TATA, and FCF are
  EXACT here, not proxied**.
- **`recommendations.csv`** (`.../output/<date>/recommendations.csv`) — sector, market cap,
  `piotroski_f`, `quality_delta_yoy`, plus the engine's own `sentiment_score`, `risk_flags`,
  `eq_warn`, `ca_warn` (available for fusion).
- **Massive API (DIRECT — `massive_api.py`)** — the live Layer-2 ground truth, key from
  `stockaffirm/.env` (`API_KEY`). Endpoints: `/v2/reference/news?ticker=` (full focused article
  corpus — ALL articles, no 30-article cap; each with `title` + `desc` body text → distress/fraud/
  raise events) and `/stocks/v1/short-interest` (days-to-cover). The whole 5,022-name calibration
  ran on this. Precision guards: **focus filter** (primary ticker only), **law-firm-spam filter**,
  **recovery guard** ("regains compliance" ≠ distress), **single-vs-≥2-article** weighting.
- **SEC EDGAR 10-K (DIRECT — `edgar_api.py`)** — auditor-issued signals from the latest annual
  filing. Chain: `company_tickers.json` (CIK) → `data.sec.gov/submissions/CIK{:010d}.json`
  (latest 10-K accession + primaryDocument URL) → full document download (50MB ceiling) →
  keyword extraction. Signals: `going_concern_flag` (auditor language, not management MD&A),
  `material_weakness_flag` (narrowed to positive-finding phrases — excludes boilerplate "assessing
  the risk that a material weakness"), `covenant_risk_flag` (narrowed to debt covenant terms —
  excludes FCPA/regulatory language). 7-day SQLite cache.
- **Alpha Vantage monthly prices (`data_loader.price_history()`)** — `TIME_SERIES_MONTHLY_ADJUSTED`
  24-month adj_close, cached per-ticker. Grounds LLM stock-price claims (`grounding_source=
  "av_price_data"`).
- **Alpha Vantage `NEWS_SENTIMENT`** — wired in `llm_client.py` fallback news path (when Massive is
  unavailable).
- **News cache** `stockaffirm/cache/data/raw/news.jsonl` (`distress_news.py`) — the older 2-week
  fallback, superseded by the Massive API above (it was ~2-week, law-firm-spam-heavy).

**NOT yet used (optional future):**
- **Massive consensus/Benzinga ratings** — needs a plan upgrade (returns NOT_AUTHORIZED today).
- **Live web-search agent** (the `distress-avoid-audit` workflow) — heavier confirmation for the
  highest-stakes names; the Massive news feed + EDGAR covers the routine case far more cheaply.

> **What's Python vs agent:** Layers 1+2 (the screen, the API scan, verdicts, the effective_bucket,
> the state DB, `loop_runner.py`) are **100% deterministic Python** — they processed all 5,022 with
> no LLM. An **agent is only needed to CALIBRATE** — i.e. when the loop surfaces a new systematic
> OVERFLAG/UNDERFLAG pattern, the agent encodes a general fix into the Python and logs it
> (`CALIBRATION_LOG.md`). Agent improves the rules; Python applies them to every ticker.

---

## 4. Data-field map (raw → model inputs)

`full_history(fund)` joins income/balance/cash-flow by fiscal year, newest-first. Key fields:

| model input | raw field(s) |
|---|---|
| revenue, gross_profit, cost_of_revenue, operating_income (EBIT), ebitda | income statement |
| sga | `selling_general_administrative` |
| net_income | `consolidated_net_income_loss` (fallback: attributable-to-common) |
| total_assets, current_assets, current_liabilities, total_liabilities, total_equity | balance sheet |
| retained_earnings | `retained_earnings_deficit` |
| ppe_net, intangibles, receivables, inventories | balance sheet |
| total_debt | `debt_current` + `long_term_debt_and_capital_lease_obligations` |
| long_term_debt | `long_term_debt_and_capital_lease_obligations` (REAL corporate leverage) |
| cash | `cash_and_equivalents` + `short_term_investments` |
| **cfo** | `net_cash_from_operating_activities` |
| **dep** | `depreciation_depletion_and_amortization` |
| **capex** | `purchase_of_property_plant_and_equipment` (reported as positive outflow) |
| dividends, ltd_issued_repaid | cash-flow statement |

---

## 5. The seven models (exact formulas — all coefficients verified vs primary sources)

### Altman Z''-Score (book, cross-sector primary)
`Z'' = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4`
- X1 = (current assets − current liabilities) / total assets
- X2 = retained earnings / total assets
- X3 = operating income (EBIT) / total assets
- X4 = **book** total equity / total liabilities
- Zones: **>2.6 safe · 1.1–2.6 grey · <1.1 distress**.
Also compute original Z (manufacturers, market value) when market cap known:
`Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·(mktcap/TL) + 1.0·(sales/TA)`, zones >2.99 / 1.81.

### Beneish M-Score (8-variable; threshold M > −1.78 ⇒ likely manipulator)
`M = −4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + 0.115·DEPI − 0.172·SGAI + 4.679·TATA − 0.327·LVGI`
- DSRI = (Recv_t/Sales_t)/(Recv_{t-1}/Sales_{t-1})
- GMI  = GM_{t-1}/GM_t   (GM = gross_profit/revenue)
- AQI  = [1−(CA+PPE)/TA]_t / [1−(CA+PPE)/TA]_{t-1}
- SGI  = Sales_t/Sales_{t-1}
- DEPI = [Dep_{t-1}/(Dep_{t-1}+PPE_{t-1})] / [Dep_t/(Dep_t+PPE_t)]
- SGAI = (SGA_t/Sales_t)/(SGA_{t-1}/Sales_{t-1})
- TATA = (net income − CFO) / total assets   ← **exact (CFO cached)**
- LVGI = [(LTD+CL)/TA]_t / [(LTD+CL)/TA]_{t-1}
(DEPI/SGAI/LVGI default to 1.0 if a field is missing; DSRI/GMI/AQI/SGI/TATA are required.)

### Ohlson O-Score (9-variable logit; P = 1/(1+e^−O); "severe" if P>0.70)
`O = −1.32 − 0.407·ln(TA/1e6) + 6.03·(TL/TA) − 1.43·(WC/TA) + 0.0757·(CL/CA) − 1.72·OENEG − 2.37·(NI/TA) − 1.83·(CFO/TL) + 0.285·INTWO − 0.521·CHIN`
OENEG=1 if TL>TA; INTWO=1 if NI<0 both latest two years; CHIN=(NI_t−NI_{t-1})/(|NI_t|+|NI_{t-1}|).
(Size term uses TA in $millions as a deflator approximation — documented; corroborating only.)

### Sloan accruals  `(NI − CFO) / avg total assets`  (high positive ⇒ low earnings quality)
### Montier C-Score  6 binary flags (NI-vs-CFO gap, rising DSO, rising DSI, rising other-CA/rev, declining dep-rate, asset growth >15%) → 0–6; ≥4 = manipulation-suspect.
### Multi-year cash conversion  `cum CFO / cum NI` over ~4y → the real manipulation discriminator (§7).

---

## 6. The gates (exact logic & thresholds)

Constants (top of `distress_screen.py`): `Z2_SAFE 2.6 / Z2_DISTRESS 1.1`, `M_THRESHOLD −1.78`,
`OHLSON_SEVERE 0.70`, `ACCRUAL_HI 0.10`, `FRAUD_ACCRUAL_MIN 0.08`, `CASH_CONV_FLOOR 0.70`,
`C_HIGH 4`, `ND_EBITDA_SEVERE 8 / _HIGH 5`, `RUNWAY_SHORT 18 / LONG_RUNWAY 24` (months),
`RECOVERY_MIN_SIGNALS 3`. Structurally-levered sectors (Altman/leverage/Ohlson suppressed):
Financials, Real Estate, Utilities + **detected float businesses** (current liabilities > revenue
+ tiny long-term debt + profitable ⇒ payroll processors / BDCs / captive-finance).

### Bankruptcy gate (cash-serviceability first, NOT leverage)
Cash-insolvency signals: operating CFO negative (suppressed for Financials/lenders) · negative
EBITDA with net debt and no offsetting CFO · insolvent-from-accumulated-losses (neg equity **and**
neg retained earnings **and** a loss) · cash runway <18mo. Corroborators: Ohlson P>0.70 · Altman
<1.1 · net-debt/EBITDA >8 · 2 straight years of losses. (Leverage/Altman corroborators are off
for levered sectors.)
**AVOID-bankruptcy fires** when, and only when, NONE of the overrides hold AND one of:
insolvent-from-losses · CFO-burn + short runway · CFO-burn + ≥3 total signals · can't-service +
≥2 · Ohlson-severe + a cash signal. **A news going-concern/Ch11/default headline escalates** a
borderline name.
**Overrides that PREVENT a bankruptcy call** (precision):
1. *solvent* — positive CFO, positive EBITDA, no sustained losses, serviceable leverage.
2. *profitable* — positive NI **and** EBIT, positive equity, real (LT) leverage <4× — OR a
   profitable **dividend-payer** (boards cut the dividend long before default; covers lenders/BDCs).
3. *fortress* — net cash **and** positive FCF.
4. *long-runway* — >24 months of cash.
`distress_type = insolvency` if insolvent-equity / high leverage / news event, else `cash_burn`.

### Fraud gate (earnings that can't become cash)
`fraud_fundamental` = Beneish M>−1.78 **AND** accruals >8% (positive) **AND** poor multi-year
conversion (cum CFO < 70% of cum NI) **AND** a distinct corroborator (Montier ≥4, receivables
spike DSRI>1.4, or M>−1.0).
**Cash-generative veto → demote to forensic WATCHLIST** (not AVOID) if the firm converts to cash
(positive latest CFO + positive cum CFO + profitable) OR is profitable & net-cash — because then
the high accruals are a one-time non-cash item (deferred-tax release, lease/milestone), not
manipulation. **News (SEC/short/restatement) overrides the veto** and confirms AVOID.

### Recovery gate
Distressed (operating loss / CFO-burn / high-leverage+strain — but NOT a fortress balance sheet)
**AND** positive operating CFO **AND** ≥3 of {deleveraging, improving margins, stabilizing
revenue, tangible-asset coverage of debt, Piotroski ≥5 or improving, rising Altman}, and not AVOID.

---

## 7. False-positive taxonomy (the calibration knowledge — fixes are GENERAL, not per-name)

| Class | Examples | Why it false-flagged | Fix |
|---|---|---|---|
| Buyback negative equity | ABBV, ADP, LOW, MCD, HD | neg equity/RE from returning capital, not losses | insolvent-equity counts only with a loss/cash problem |
| Float businesses | ADP, PAYX, BDCs (ARCC) | client funds as huge CL / gross "debt" | detect → treat like a levered sector |
| Capital-intensive sectors | AEP/AEE utilities, pipelines | high leverage + low Altman by design | Utilities/Fin/RE exempt from leverage/Altman |
| Hyper-growth Beneish trap | **NVDA**, AAON, AGI | growth builds receivables/inventory | accruals + **multi-year cash conversion** necessary |
| Meme / melting ice cube | GME | equity raises + revenue collapse distort Beneish | negative accruals ⇒ not manipulation |
| Homebuilder inventory | TOL | profit sunk into real land/homes | fraud needs a *distinct* corroborator beyond accruals |
| One-bad-year + cash cushion | STLA, Ford | single operating-loss year, long runway | profitability + long-runway overrides |
| Cash-rich GAAP losers | CRWD, NET, SNOW | stock-comp GAAP losses | fortress (net cash + positive FCF) exemption |
| **Lenders / mortgage** | **RKT** | loans-held-for-sale make operating CFO structurally negative | suppress CFO signals for Financials |
| **Well-funded cash-burners** | **GH, AUR, RBRK, INSM** | backward-looking GAAP losses; years of runway | long-runway (>24mo) + fortress vetoes |
| **One-time accrual spikes** | **FTAI, ACAD, AUPH, ADMA** | deferred-tax release / lease accounting | cash-generative & profitable-net-cash veto → watchlist |

Sanity sweeps that must stay correct: blue chips (KO/PG/WMT/JNJ/GOOGL/META/BRK.B/COST/UNH/XOM/
CVX/HD/WM/LIN) all CLEAR; genuine distress (BA, CCL→recovered, BYND, SATS, SOUN) bucket correctly.

---

## 8. Output

`screen()` returns a dict with: `bucket`, `headline`, `bankruptcy` + `distress_type`, `fraud` +
`fraud_watchlist`, `recoverable`, `news_bk_event`/`news_fraud_event`, the per-model results
(`altman`/`beneish`/`ohlson`/`accruals`/`montier`/`solvency`), `recovery_signals`, severities,
and the human-readable `reasons`/`fraud_reasons`. `distress_batch.py` writes every screened
ticker to `DISTRESS_SCREEN.csv` and the ranked report to `DISTRESS_REPORT.md`.

---

## 9. Validation protocol — the adversarial audit (REQUIRED before trusting an AVOID list)

The fundamentals screen WILL over-flag. Confirm it. The reference is the `distress-avoid-audit`
workflow: for the top-N AVOID names by market cap, spawn one independent web-research agent per
ticker that checks the *current* condition (latest results, cash/runway, debt maturities,
going-concern language, Chapter-11/SEC/short-seller/restatement news) and returns
`confirmed | partial | false_positive` with key facts.

**Findings on the first run (21 largest AVOID names): 15 false_positive, 6 partial, 0 fully
confirmed.** Every false positive was either a well-capitalised growth/biotech burner (long
runway / capital access), a lender (CFO artifact), or a one-time-accrual name. Those findings
produced the §7 fixes; after them the AVOID share fell 22%→16% and fraud 57→16. The 6 "partial"
names (MSTR, SATS, BYND, BTDR, ADMA, AEHR) are genuinely high-risk — and BYND/BTDR carry real
news corroboration (material weakness / 10-K delay; short report + class action), which is the
whole point of Layer 3.

**Operating rule:** run the audit on the AVOID candidates each cycle; promote only audit- or
news-confirmed names to a hard AVOID; treat the rest as "investigate."

---

## 10. Honest limitations
- **Interest expense isn't separately disclosed** in the cache → interest-coverage is approximated
  (shown, not used as a primary signal; the screen leans on cash flow).
- **Financials/RE/Utilities/float businesses**: balance-sheet ratios are suppressed (structurally
  distorted); coverage there is inherently weaker (banks need capital ratios not in the cache).
- **Single-vintage annuals** — the FY in the cache, not point-in-time as-reported; a fresh quarter
  or a just-closed equity raise (which the snapshot can't see) changes the read. This is exactly
  why Layer 2 (Massive + EDGAR) exists.
- **Beneish/Ohlson** have real false-positive rates; mitigated by multi-signal corroboration, the
  accruals + cash-conversion necessary conditions, sector/float guards, and the cash-generative
  veto — but a fundamentals-only fraud flag is a "look harder" list, never a verdict.
- **News cache is a thin (~2-week) law-firm-spam-heavy window** — Layer 3 now uses the Massive full
  article corpus (no cap); for the deepest confirmations use the Layer-4 web audit.
- **EDGAR 10-K single-filing vintage** — the most recent annual; mid-year 8-K material weakness
  disclosures and 10-K/A amendments won't appear. `edgar_10k_signals` returns `None` if the ticker
  is unknown to EDGAR or the download fails — treat as absence of evidence, not as CLEAR. Going-
  concern language must appear in the auditor's opinion section to trigger the flag; management MD&A
  softer language is captured separately in the `mda_excerpt` field.
