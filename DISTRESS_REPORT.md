# Distress & Fraud Screen — full universe

_Subagent of the Analyst Agent. Composes Altman Z''/Z, Beneish M, Ohlson O, Sloan accruals, Montier C, hard liquidity/leverage/cash-runway signals, and a NEWS/EVENT layer (going-concern, Chapter 11, SEC, short-seller, restatement). A name is bucketed AVOID only when multiple corroborating signals agree; cash runway + capital access decide near-term bankruptcy (not backward-looking GAAP losses), and earnings-manipulation requires earnings that can't convert to cash. Cash-flow statements are cached, so accruals / Beneish-TATA / FCF are exact._

_News/event layer: cache window 2026-05-23 → 2026-06-06 (a ~2-week live-poll snapshot; deep/historical news = on-demand web/AV enrichment, per the audit workflow)._

**Universe:** 5022 tickers · **scored:** 4210 · skipped (no data / <2y): 812 · errors: 0

## Bucket counts

| Bucket | Count | Meaning |
|---|---:|---|
| 🟥 AVOID — bankruptcy (205 insolvency / 473 cash-burn) | 678 | can't fund/service itself |
| 🟥 AVOID — fraud / manipulation | 16 | earnings can't convert to cash |
| 🟧 DISTRESSED — recoverable | 422 | badly stressed but solvent + turning |
| 🟨 WATCH (incl. forensic EQ flags) | 650 | stress signals, not terminal/recovering |
| 🟩 CLEAR | 2451 | no material distress/manipulation signal |

_Of the 694 AVOID names, 1 carry a corroborating NEWS event (📰) in the cache window. **insolvency** = an over-levered/loss-eroded operating business genuinely failing; **cash-burn** = a pre-profit company dependent on raising more capital (higher-risk, but not the same as a business going under)._

## 🟥 AVOID — Bankruptcy / insolvency risk  (top by severity × size)

> On the verge of bankruptcy: burning operating cash with a short runway, can't service debt (negative EBITDA, no offsetting cash), insolvent from accumulated losses, or a high Ohlson default probability — and NOT rescued by the solvency / profitability / long-runway overrides. **Note:** clinical-stage biotech and pre-revenue tech dominate this list — they burn cash *by design* and survive on equity raises; 'bankruptcy risk' for them means dilution/failure risk, a different flavor than an over-levered operating business going under.

| # | Ticker | Sector | Mkt cap | Type | Z'' | Ohlson P(def) | ND/EBITDA | News | Sev | Flags |
|---:|---|---|---:|---|---:|---:|---:|:--:|---:|---|
| 1 | **BBIO** | Health Care | $13.2B | insolvency | -14.22 | 100% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 2 | **APLD** | Information Technology | $11.3B | insolvency | -1.90 | 81% | 9.6 |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; leverage_severe; sustained_losses_2y |
| 3 | **CYTK** | Health Care | $9.7B | insolvency | -7.91 | 98% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 4 | **MSGS** | Communication Services | $9.3B | insolvency | -1.84 | 89% | 8.1 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; leverage_severe |
| 5 | **W** | Consumer Discretionary | $9.0B | insolvency | -5.25 | 99% | 4.2 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 6 | **CLF** | Materials | $7.7B | cash_burn | 0.90 | 33% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; altman_deep_distress; sustained_losses_2y |
| 7 | **VFS** | Unknown | $7.5B | insolvency | -12.51 | 99% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 8 | **IBRX** | Health Care | $7.2B | insolvency | -24.85 | 100% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 9 | **PLUG** | Information Technology | $4.5B | cash_burn | -11.92 | 78% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 10 | **CLMT** | Energy | $3.1B | insolvency | -2.17 | 70% | 11.4 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; leverage_severe; sustained_losses_2y |
| 11 | **BKD** | Health Care | $2.9B | insolvency | -2.40 | 50% | 8.8 |  | 100 | insolvent_from_accumulated_losses; altman_deep_distress; leverage_severe; sustained_losses_2y |
| 12 | **CHRN** | Industrials | $2.7B | cash_burn | -44.37 | 98% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 13 | **WOLF** | Information Technology | $2.7B | insolvency | -7.90 | 89% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 14 | **BW** | Materials | $2.4B | insolvency | -8.40 | 89% | 11.2 |  | 100 | operating_cash_flow_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; leverage_severe; sustained_losses_2y |
| 15 | **ALMS** | Health Care | $2.4B | cash_burn | -7.78 | 99% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 16 | **PIII** | Health Care | $2.4B | insolvency | -10.33 | 99% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 17 | **PCT** | Materials | $2.3B | cash_burn | -3.35 | 65% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; altman_deep_distress; sustained_losses_2y |
| 18 | **ESTA** | Health Care | $2.2B | cash_burn | -2.10 | 89% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 19 | **RARE** | Health Care | $2.2B | insolvency | -9.61 | 82% | n/a |  | 100 | operating_cash_flow_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 20 | **LCID** | Consumer Discretionary | $2.0B | cash_burn | -8.21 | 70% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 21 | **NKTR** | Health Care | $1.9B | cash_burn | -41.60 | 96% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 22 | **NTLA** | Health Care | $1.9B | cash_burn | -6.12 | 89% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 23 | **PLSE** | Health Care | $1.8B | cash_burn | -10.11 | 100% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 24 | **PSNY** | Unknown | $1.7B | insolvency | -17.59 | 100% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 25 | **AEVA** | Industrials | $1.6B | cash_burn | -14.13 | 99% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 26 | **SNDX** | Health Care | $1.5B | cash_burn | -7.54 | 96% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 27 | **VIR** | Health Care | $1.5B | cash_burn | -0.98 | 73% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 28 | **LIND** | Industrials | $1.4B | insolvency | -2.17 | 82% | 3.7 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 29 | **URGN** | Health Care | $1.3B | insolvency | -15.63 | 100% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 30 | **PGEN** | Health Care | $1.3B | cash_burn | -50.41 | 100% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 31 | **IAUX** | Materials | $1.2B | cash_burn | -2.76 | 68% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; altman_deep_distress; sustained_losses_2y |
| 32 | **KDK** | Information Technology | $1.2B | insolvency | -19.47 | 100% | n/a |  | 100 | operating_cash_flow_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 33 | **CCO** | Information Technology | $1.2B | insolvency | -5.39 | 99% | 10.2 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; leverage_severe |
| 34 | **RXT** | Information Technology | $1.2B | insolvency | -5.69 | 94% | 15.4 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; leverage_severe; sustained_losses_2y |
| 35 | **REAL** | Consumer Discretionary | $1.1B | insolvency | -11.84 | 100% | 24.3 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; leverage_severe; sustained_losses_2y |
| 36 | **EYPT** | Health Care | $988M | cash_burn | -3.58 | 100% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 37 | **AVR** | Health Care | $938M | insolvency | -81.60 | 100% | n/a |  | 100 | operating_cash_flow_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 38 | **LPTH** | Information Technology | $937M | cash_burn | -8.77 | 61% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; altman_deep_distress; sustained_losses_2y |
| 39 | **ADSE** | Information Technology | $852M | insolvency | -18.16 | 99% | n/a |  | 100 | operating_cash_flow_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 40 | **MGTX** | Health Care | $833M | insolvency | -14.65 | 94% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 41 | **PHAT** | Health Care | $808M | insolvency | -21.03 | 100% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 42 | **FBYD** | Communication Services | $719M | cash_burn | -4.71 | 94% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress |
| 43 | **ANL** | Health Care | $641M | insolvency | -56.99 | 100% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 44 | **GRPN** | Information Technology | $625M | insolvency | -7.77 | 79% | 1.5 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 45 | **IHRT** | Communication Services | $588M | insolvency | -2.73 | 87% | 8.8 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; leverage_severe; sustained_losses_2y |
| 46 | **PRME** | Health Care | $553M | cash_burn | -9.55 | 94% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 47 | **WTI** | Energy | $550M | insolvency | -3.18 | 88% | 2.2 |  | 100 | insolvent_from_accumulated_losses; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 48 | **ANGX** | Communication Services | $511M | insolvency | -10.22 | 99% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress |
| 49 | **FIP** | Industrials | $492M | insolvency | -0.54 | 65% | 21.6 |  | 100 | operating_cash_flow_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; altman_deep_distress; leverage_severe; sustained_losses_2y |
| 50 | **TOI** | Health Care | $487M | insolvency | -5.27 | 93% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 51 | **VELO** | Industrials | $472M | cash_burn | -15.44 | 92% | n/a |  | 100 | operating_cash_flow_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 52 | **CGC** | Materials | $463M | cash_burn | -37.11 | 75% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 53 | **ECX** | Information Technology | $461M | insolvency | -10.16 | 99% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 54 | **SPCE** | Industrials | $457M | cash_burn | -11.93 | 84% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 55 | **UXIN** | Unknown | $449M | insolvency | -27.99 | 96% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 56 | **CTEV** | Industrials | $441M | insolvency | -1.66 | 46% | 9.5 |  | 100 | insolvent_from_accumulated_losses; altman_deep_distress; leverage_severe; sustained_losses_2y |
| 57 | **EOLS** | Health Care | $439M | insolvency | -8.65 | 90% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 58 | **OCGN** | Health Care | $433M | insolvency | -40.32 | 100% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 59 | **STRO** | Health Care | $432M | insolvency | -22.06 | 100% | n/a |  | 100 | operating_cash_flow_negative; insolvent_from_accumulated_losses; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |
| 60 | **ABAT** | Materials | $424M | cash_burn | -7.19 | 96% | n/a |  | 100 | operating_cash_flow_negative; cant_service_debt_ebitda_negative; cash_runway_under_18mo; ohlson_high_default_prob; altman_deep_distress; sustained_losses_2y |

_…and 618 more — full ranked list in `DISTRESS_SCREEN.csv`._

## 🟥 AVOID — Fraud / earnings-manipulation risk  (top by severity × size)

> Reported numbers likely juiced: Beneish M above -1.78 AND elevated POSITIVE accruals AND poor multi-year cash conversion (cum CFO < 70% of cum NI) AND a distinct corroborator (≥4 Montier flags, receivables spike, or M > -1.0). The cash-conversion + accruals gates clear hyper-growers (NVDA) and cash-backed quality compounders (AAON) that Beneish alone false-flags. Treat as 'investigate', not proof.

| # | Ticker | Sector | Mkt cap | Beneish M | Accruals | Montier C | Flags (incl. 4y CFO/NI) |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | **TGTX** | Health Care | $6.1B | 8.77 | 57.5% | 4/6 | beneish_m(8.77>-1.78); accruals_58pct; cfo/ni_-1.05; montier_c_high; beneish_strong |
| 2 | **BTDR** | Financials | $4.3B | 9.85 | 82.7% | 6/6 | beneish_m(9.85>-1.78); accruals_83pct; montier_c_high; receivables_spike; beneish_strong |
| 3 | **NA** | Unknown | $49M | 47.60 | 27.4% | 4/6 | beneish_m(47.60>-1.78); accruals_27pct; montier_c_high; receivables_spike; beneish_strong |
| 4 | **NIVF** | Unknown | $2M | 7.73 | 113.8% | 4/6 | beneish_m(7.73>-1.78); accruals_114pct; cfo/ni_-2.07; montier_c_high; beneish_strong |
| 5 | **FBYD** | Communication Services | $719M | 1.12 | 48.3% | 1/6 | beneish_m(1.12>-1.78); accruals_48pct; beneish_strong |
| 6 | **AREN** | Communication Services | $63M | 0.95 | 74.8% | 2/6 | beneish_m(0.95>-1.78); accruals_75pct; beneish_strong |
| 7 | **GREE** | Financials | $26M | 0.27 | 34.3% | 2/6 | beneish_m(0.27>-1.78); accruals_34pct; receivables_spike; beneish_strong |
| 8 | **GREEL** | Financials | n/a | 0.27 | 34.3% | 2/6 | beneish_m(0.27>-1.78); accruals_34pct; receivables_spike; beneish_strong |
| 9 | **SKYT** | Information Technology | $1.7B | -0.79 | 29.1% | 5/6 | beneish_m(-0.79>-1.78); accruals_29pct; cfo/ni_-0.25; montier_c_high; receivables_spike; beneish_strong |
| 10 | **ATCH** | Financials | $34M | -0.60 | 8.3% | 2/6 | beneish_m(-0.60>-1.78); accruals_8pct; beneish_strong |
| 11 | **FTAI** | Information Technology | $24.0B | -0.83 | 19.3% | 2/6 | beneish_m(-0.83>-1.78); accruals_19pct; cfo/ni_-0.70; beneish_strong |
| 12 | **CLSK** | Financials | $4.0B | -1.03 | 32.1% | 4/6 | beneish_m(-1.03>-1.78); accruals_32pct; cfo/ni_-27.51; montier_c_high |
| 13 | **FUFU** | Unknown | $275M | -1.16 | 22.2% | 2/6 | beneish_m(-1.16>-1.78); accruals_22pct; cfo/ni_-14.58; receivables_spike |
| 14 | **JVA** | Consumer Staples | $24M | -1.49 | 16.9% | 4/6 | beneish_m(-1.49>-1.78); accruals_17pct; montier_c_high |
| 15 | **SPCB** | Unknown | $57M | -1.55 | 16.2% | 4/6 | beneish_m(-1.55>-1.78); accruals_16pct; montier_c_high |
| 16 | **PDEX** | Health Care | $208M | -1.69 | 18.8% | 4/6 | beneish_m(-1.69>-1.78); accruals_19pct; cfo/ni_0.40; montier_c_high |

## 🟧 DISTRESSED — but RECOVERABLE  (slow-recovery candidates)

> Badly stressed (operating loss, cash burn, or high leverage + strain) BUT still solvent and turning: positive operating cash flow plus ≥3 of {deleveraging, improving margins, stabilizing revenue, asset coverage, decent Piotroski, rising Altman}. A fortress balance sheet (net cash + positive FCF) is excluded — a GAAP loss from stock-comp (CRWD/SNOW) is not distress. Largest first.

| # | Ticker | Sector | Mkt cap | Z'' | ND/EBITDA | Recovery | Why recoverable |
|---:|---|---|---:|---:|---:|:--:|---|
| 1 | **ORCL** | Information Technology | $614.6B | 0.24 | 3.4 | 4/7 | solvent with a turnaround vector |
| 2 | **BA** | Industrials | $169.8B | 0.95 | n/a | 4/7 | solvent with a turnaround vector |
| 3 | **NGG** | Unknown | $81.5B | 2.03 | 5.9 | 4/7 | solvent with a turnaround vector |
| 4 | **BE** | Information Technology | $75.0B | 2.02 | 3.3 | 5/7 | solvent with a turnaround vector |
| 5 | **APO** | Financials | $73.8B | -0.06 | n/a | 3/7 | solvent with a turnaround vector |
| 6 | **LITE** | Information Technology | $67.2B | 1.44 | 26.3 | 4/7 | solvent with a turnaround vector |
| 7 | **APD** | Materials | $62.9B | 2.27 | 3.6 | 4/7 | solvent with a turnaround vector |
| 8 | **F** | Consumer Discretionary | $59.4B | 0.38 | n/a | 3/7 | solvent with a turnaround vector |
| 9 | **NBIS** | Unknown | $57.8B | 2.83 | n/a | 5/7 | solvent with a turnaround vector |
| 10 | **TTWO** | Communication Services | $39.8B | -1.59 | 1.1 | 6/7 | solvent with a turnaround vector |
| 11 | **BIP** | Industrials | $30.6B | n/a | 6.5 | 5/7 | solvent with a turnaround vector |
| 12 | **EL** | Consumer Staples | $30.2B | 2.44 | 2.2 | 4/7 | solvent with a turnaround vector |
| 13 | **FTS** | Unknown | $28.5B | 0.76 | 6.2 | 5/7 | solvent with a turnaround vector |
| 14 | **BG** | Consumer Staples | $24.5B | 3.17 | 6.6 | 3/7 | solvent with a turnaround vector |
| 15 | **AER** | Information Technology | $21.6B | 1.25 | 5.3 | 7/7 | solvent with a turnaround vector |
| 16 | **AFRM** | Financials | $21.3B | -0.80 | n/a | 5/7 | solvent with a turnaround vector |
| 17 | **DD** | Materials | $19.0B | -0.39 | 1.6 | 6/7 | solvent with a turnaround vector |
| 18 | **IFF** | Materials | $18.6B | 1.21 | 3.0 | 5/7 | solvent with a turnaround vector |
| 19 | **VTRS** | Health Care | $18.5B | 0.65 | 4.4 | 3/7 | solvent with a turnaround vector |
| 20 | **ALB** | Materials | $18.3B | 3.26 | 2.2 | 6/7 | solvent with a turnaround vector |
| 21 | **H** | Consumer Discretionary | $18.2B | 1.05 | 3.8 | 4/7 | solvent with a turnaround vector |
| 22 | **IP** | Materials | $17.8B | 1.03 | 3.8 | 3/7 | solvent with a turnaround vector |
| 23 | **FLUT** | Information Technology | $17.4B | 0.91 | 5.0 | 3/7 | solvent with a turnaround vector |
| 24 | **TLN** | Utilities | $16.7B | 0.11 | 14.4 | 4/7 | solvent with a turnaround vector |
| 25 | **XPEV** | Unknown | $15.2B | -2.13 | n/a | 5/7 | solvent with a turnaround vector |
| 26 | **JAZZ** | Health Care | $15.0B | 1.63 | 2.4 | 4/7 | solvent with a turnaround vector |
| 27 | **SMTC** | Information Technology | $14.1B | 1.58 | 1.8 | 6/7 | solvent with a turnaround vector |
| 28 | **U** | Information Technology | $12.7B | -0.19 | n/a | 5/7 | solvent with a turnaround vector |
| 29 | **CRBG** | Financials | $12.3B | 1.72 | -150.1 | 4/7 | solvent with a turnaround vector |
| 30 | **IVZ** | Financials | $12.1B | 1.38 | n/a | 3/7 | solvent with a turnaround vector |
| 31 | **HAS** | Consumer Discretionary | $11.9B | 1.92 | 1.9 | 5/7 | solvent with a turnaround vector |
| 32 | **ELAN** | Health Care | $11.8B | 1.25 | 3.7 | 5/7 | solvent with a turnaround vector |
| 33 | **LFUS** | Information Technology | $11.6B | 4.60 | 0.5 | 4/7 | solvent with a turnaround vector |
| 34 | **QXO** | Industrials | $11.4B | 3.11 | 5.0 | 3/7 | solvent with a turnaround vector |
| 35 | **SJM** | Consumer Staples | $11.0B | 0.32 | 3.5 | 4/7 | solvent with a turnaround vector |
| 36 | **GSAT** | Communication Services | $10.5B | -1.96 | 0.4 | 6/7 | solvent with a turnaround vector |
| 37 | **BAX** | Health Care | $10.0B | 3.79 | 7.9 | 6/7 | solvent with a turnaround vector |
| 38 | **OC** | Materials | $9.6B | 2.26 | 2.0 | 3/7 | solvent with a turnaround vector |
| 39 | **SNAP** | Information Technology | $9.5B | -3.13 | n/a | 5/7 | solvent with a turnaround vector |
| 40 | **CWEN** | Utilities | $9.5B | 0.50 | 8.0 | 3/7 | solvent with a turnaround vector |
| 41 | **MASI** | Health Care | $9.4B | 6.72 | 1.0 | 6/7 | solvent with a turnaround vector |
| 42 | **FRHC** | Financials | $9.1B | 0.88 | n/a | 4/7 | solvent with a turnaround vector |
| 43 | **AAL** | Industrials | $8.9B | -1.64 | 6.3 | 5/7 | solvent with a turnaround vector |
| 44 | **CRL** | Health Care | $8.7B | 1.81 | 2.4 | 4/7 | solvent with a turnaround vector |
| 45 | **ALGM** | Information Technology | $8.6B | 3.74 | 1.3 | 6/7 | solvent with a turnaround vector |
| 46 | **NCLH** | Consumer Discretionary | $8.6B | -1.48 | 5.3 | 6/7 | solvent with a turnaround vector |
| 47 | **BRKR** | Health Care | $8.6B | n/a | 4.1 | 4/7 | solvent with a turnaround vector |
| 48 | **VSH** | Information Technology | $7.8B | 3.61 | 1.5 | 4/7 | solvent with a turnaround vector |
| 49 | **JXN** | Financials | $7.5B | 4.61 | n/a | 4/7 | solvent with a turnaround vector |
| 50 | **CWAN** | Information Technology | $7.3B | 2.68 | 8.2 | 3/7 | solvent with a turnaround vector |
| 51 | **MXL** | Information Technology | $7.2B | -1.24 | n/a | 3/7 | solvent with a turnaround vector |
| 52 | **MIDD** | Industrials | $7.0B | 5.52 | 2.8 | 6/7 | solvent with a turnaround vector |
| 53 | **MAC** | Financials | $7.0B | -1.00 | 8.9 | 3/7 | solvent with a turnaround vector |
| 54 | **HR** | Financials | $6.9B | 1.13 | 6.0 | 4/7 | solvent with a turnaround vector |
| 55 | **GDS** | Unknown | $6.8B | 1.19 | 6.4 | 5/7 | solvent with a turnaround vector |
| 56 | **MRCY** | Information Technology | $6.7B | 3.84 | 3.9 | 4/7 | solvent with a turnaround vector |
| 57 | **RIG** | Energy | $6.6B | -1.28 | 3.7 | 4/7 | solvent with a turnaround vector |
| 58 | **JBTM** | Industrials | $6.5B | 1.95 | 3.5 | 3/7 | solvent with a turnaround vector |
| 59 | **AN** | Consumer Discretionary | $6.3B | 1.70 | 6.1 | 4/7 | solvent with a turnaround vector |
| 60 | **AVTR** | Health Care | $6.3B | 1.86 | 3.8 | 3/7 | solvent with a turnaround vector |

_…and 362 more — full ranked list in `DISTRESS_SCREEN.csv`._

## 🟨 Forensic earnings-quality watchlist  (NOT bucketed AVOID)

> Fundamentals-suspicious (elevated Beneish / accruals) but **demoted from the fraud bucket** because earnings DO convert to cash (good multi-year CFO/NI) or the firm is profitable & net-cash — so the high accruals are almost always a one-time non-cash item (deferred-tax release, lease/milestone accounting) or just fast-grower working-capital build, not manipulation. Investigate the accounting; this is where to point the live news/AV enrichment, not a manipulation call.

| # | Ticker | Sector | Mkt cap | Bucket | Beneish M | Accruals |
|---:|---|---|---:|---|---:|---:|
| 1 | **NVDA** | Information Technology | $4967.7B | CLEAR | -1.15 | 10.9% |
| 2 | **MRVL** | Information Technology | $230.5B | CLEAR | -1.59 | 4.3% |
| 3 | **STX** | Information Technology | $191.7B | CLEAR | -1.48 | 4.9% |
| 4 | **IBKR** | Financials | $143.2B | CLEAR | 23.64 | -6.5% |
| 5 | **BX** | Financials | $141.0B | CLEAR | 20.30 | 3.0% |
| 6 | **LOW** | Consumer Discretionary | $118.2B | CLEAR | 7.25 | -6.6% |
| 7 | **HOOD** | Financials | $74.3B | CLEAR | -1.74 | 0.8% |
| 8 | **BAM** | Financials | $73.7B | CLEAR | 2.25 | 1.9% |
| 9 | **CVNA** | Consumer Discretionary | $73.0B | CLEAR | -1.02 | 7.9% |
| 10 | **NBIS** | Unknown | $57.8B | DISTRESSED-RECOVERABLE | 7.91 | -3.8% |
| 11 | **PSA** | Real Estate | $54.4B | CLEAR | 9.00 | -7.0% |
| 12 | **ALAB** | Information Technology | $54.3B | CLEAR | 1.63 | -7.7% |
| 13 | **WPM** | Unknown | $52.8B | CLEAR | -0.16 | -5.2% |
| 14 | **LNG** | Utilities | $50.0B | CLEAR | -1.46 | 2.7% |
| 15 | **COIN** | Financials | $40.2B | CLEAR | -1.75 | -4.5% |
| 16 | **CRDO** | Information Technology | $38.2B | CLEAR | -1.55 | -1.8% |
| 17 | **ASTS** | Communication Services | $36.3B | WATCH | 16.19 | -13.0% |
| 18 | **CQP** | Utilities | $31.2B | CLEAR | -1.68 | 1.3% |
| 19 | **TSEM** | Unknown | $28.0B | CLEAR | -1.37 | -5.5% |
| 20 | **BG** | Consumer Staples | $24.5B | DISTRESSED-RECOVERABLE | -1.53 | -0.0% |
| 21 | **AWK** | Utilities | $24.3B | CLEAR | -1.77 | -2.8% |
| 22 | **IONQ** | Information Technology | $21.2B | WATCH | 1.72 | -6.5% |
| 23 | **PAAS** | Unknown | $20.0B | CLEAR | 1.29 | -4.2% |
| 24 | **DKS** | Consumer Discretionary | $19.2B | CLEAR | -1.27 | -4.9% |
| 25 | **AMCR** | Materials | $17.6B | CLEAR | -1.68 | -3.3% |
| 26 | **CDE** | Materials | $16.9B | CLEAR | -1.16 | -8.6% |
| 27 | **NVR** | Consumer Discretionary | $16.7B | CLEAR | -1.57 | 3.6% |
| 28 | **GEN** | Information Technology | $15.8B | CLEAR | -1.75 | -3.7% |
| 29 | **KSPI** | Unknown | $15.4B | CLEAR | -0.75 | 4.1% |
| 30 | **AGI** | Materials | $14.9B | CLEAR | -1.44 | 1.5% |
| 31 | **AAOI** | Information Technology | $14.2B | AVOID | -0.73 | 15.9% |
| 32 | **ARCC** | Unknown | $13.5B | WATCH | -2.07 | 10.5% |
| 33 | **BBIO** | Health Care | $13.2B | AVOID | 8.17 | -30.9% |
| 34 | **TOL** | Industrials | $12.9B | WATCH | -1.62 | 20.6% |
| 35 | **GFL** | Unknown | $12.8B | CLEAR | -2.08 | 12.6% |
| 36 | **HUT** | Financials | $12.6B | WATCH | -0.91 | -5.1% |
| 37 | **QXO** | Industrials | $11.4B | DISTRESSED-RECOVERABLE | 247.72 | -5.2% |
| 38 | **APLD** | Information Technology | $11.3B | AVOID | 0.34 | -8.8% |
| 39 | **MDGL** | Health Care | $11.2B | WATCH | 0.38 | -8.6% |
| 40 | **AAON** | Industrials | $10.9B | CLEAR | -1.40 | 7.5% |
| 41 | **GIL** | Unknown | $10.7B | CLEAR | -1.40 | -2.9% |
| 42 | **MP** | Materials | $10.5B | WATCH | -0.57 | 2.3% |
| 43 | **HL** | Materials | $9.9B | CLEAR | 2.14 | -7.4% |
| 44 | **GME** | Consumer Discretionary | $9.8B | CLEAR | 1.87 | -2.4% |
| 45 | **CYTK** | Health Care | $9.7B | AVOID | -0.05 | -10.9% |
| 46 | **JOBY** | Industrials | $9.4B | WATCH | 345.33 | -28.0% |
| 47 | **AG** | Materials | $8.4B | CLEAR | -1.61 | -9.4% |
| 48 | **TEM** | Information Technology | $8.3B | WATCH | -1.20 | -1.7% |
| 49 | **CORZ** | Financials | $8.2B | AVOID | 516.07 | -29.7% |
| 50 | **JHG** | Financials | $8.0B | CLEAR | -1.74 | 2.5% |
| 51 | **YOU** | Information Technology | $7.3B | CLEAR | -1.08 | -16.4% |
| 52 | **IBRX** | Health Care | $7.2B | AVOID | 4.44 | -10.5% |
| 53 | **CELH** | Consumer Staples | $7.2B | CLEAR | -0.92 | -7.3% |
| 54 | **BYD** | Consumer Discretionary | $6.5B | CLEAR | -2.08 | 13.3% |
| 55 | **JBTM** | Industrials | $6.5B | DISTRESSED-RECOVERABLE | -1.31 | -6.8% |
| 56 | **PAYC** | Information Technology | $6.4B | CLEAR | -1.47 | -3.4% |
| 57 | **GATX** | Industrials | $6.1B | CLEAR | -1.68 | -2.1% |
| 58 | **PTCT** | Health Care | $5.9B | CLEAR | -1.64 | -1.2% |
| 59 | **KRG** | Financials | $5.8B | CLEAR | -1.36 | -1.8% |
| 60 | **SSRM** | Financials | $5.5B | CLEAR | -0.33 | -1.9% |

_…and 470 more — full ranked list in `DISTRESS_SCREEN.csv`._

## 📰 News-corroborated distress / fraud events  (cache window)

> Names with an actual distress/fraud HEADLINE in the news cache (2026-05-23 → 2026-06-06): going-concern, Chapter 11, default, SEC action, short-seller report, or restatement. These are the highest-confidence flags (footprint + event). Law-firm class-action solicitations are filtered out as noise.

| # | Ticker | Sector | Mkt cap | Bucket | Event |
|---:|---|---|---:|---|---|
| 1 | **GROW** | Financials | $33M | WATCH | fraud/SEC/short/restatement |

---
_Limitations: interest expense is not separately disclosed in the cache (coverage approximated/omitted); for Financials, Real Estate, Utilities and detected float businesses (payroll processors, captive-finance, BDCs), Altman / leverage / Ohlson are structurally distorted and suppressed — those names are judged on cash flow + real (long-term) leverage. Beneish/Ohlson carry inherent false-positive rates; this screen mitigates with multi-signal corroboration, an accruals + cash-conversion necessary condition, and sector/float guards, but the AVOID-fraud list is a 'look harder' list, not a verdict. Single-vintage annuals (FY in the engine cache); not point-in-time as-reported._
