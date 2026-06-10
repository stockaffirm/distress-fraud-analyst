# Calibrated Findings — distress & fraud, full universe

_Final view after the sequential per-ticker calibration loop reconciled the fundamentals screen with the DIRECT Massive API (live news events, short interest, recent capital raises). `effective_bucket` = screen ∪ API overlay = the final answer._

**Universe:** 5022 · scored: 4210 · skipped (no data/<2y): 812 · overlay adjusted **151** names.

## Final distribution (effective bucket vs raw screen)

| Bucket | Screen | Effective |
|---|---:|---:|
| AVOID | 687 | 575 |
| DISTRESSED-RECOVERABLE | 422 | 416 |
| WATCH | 650 | 774 |
| CLEAR | 2451 | 2445 |

## 🔎 ESCALATIONS — live-API caught what the fundamentals missed (23)

> A short-seller report, an SEC action, a subsidiary fraud, a restatement, or a going-concern headline the snapshot fundamentals structurally can't see. These moved UP to WATCH/AVOID on ≥2 corroborating live-news articles — the payoff of the overlay.

| Ticker | Mkt cap | Screen → Effective | Signal | Headline |
|---|---:|---|---|---|
| **SEZL** | $3.9B | CLEAR → WATCH | fraud/SEC/restatement | Sezzle Inc. (SEZL) Shares Crash After Hindenburg Alleges Risky Practic |
| **EVLV** | $1.1B | DISTRESSED-RECOVERABLE → WATCH | fraud/SEC/restatement | Evolv Technologies (EVLV) Shares Crash After Admitting To Improper Rev |
| **PCRX** | $895M | CLEAR → WATCH | fraud/SEC/restatement | Pacira BioSciences Reports Inducement Grants Under Nasdaq Listing Rule |
| **CODI** | $801M | WATCH → AVOID | distress/going-concern | Compass Diversified Announces Conference Call to Discuss the Restateme |
| **BBBY** | $432M | WATCH → AVOID | distress/going-concern | 'I lost $100,000': investors share Bed Bath & Beyond losses on Reddit  |
| **VFF** | $239M | CLEAR → WATCH | distress/going-concern | Village Farms International Provides Update on Nasdaq Listing |
| **AVNW** | $233M | CLEAR → WATCH | fraud/SEC/restatement | Aviat Networks (AVNW) Delays Annual Report, Stock Tumbles - Hagens Ber |
| **JYNT** | $118M | CLEAR → WATCH | fraud/SEC/restatement | The Joint Corp. Expects to Restate Full Year 2024 and First Quarter 20 |
| **DUO** | $39M | WATCH → AVOID | distress/going-concern | FangDD Receives Nasdaq Notice Regarding Minimum Bid Price Requirement |
| **SWAG** | $38M | WATCH → AVOID | distress/going-concern | Stran & Company Announces Receipt of Nasdaq Staff Delisting Determinat |
| **PMEC** | $28M | DISTRESSED-RECOVERABLE → AVOID | distress/going-concern | Primech Holdings Receives NASDAQ Minimum Bid Price Requirement Extensi |
| **SWVL** | $15M | WATCH → AVOID | distress/going-concern | Swvl Reports Receipt of Nasdaq Minimum Bid Price Notification |
| **XELB** | $12M | WATCH → AVOID | distress/going-concern | XCEL BRANDS, INC. Receives NASDAQ notice regarding late Form 10-K fili |
| **NVNI** | $12M | CLEAR → WATCH | distress/going-concern | NVNI Group Receives Nasdaq Notification of Non-Compliance with Listing |
| **OST** | $10M | DISTRESSED-RECOVERABLE → AVOID | distress/going-concern | Ostin Technology Group Announces Update to Effective Date of Reverse S |
| **YYAI** | $8M | WATCH → AVOID | distress/going-concern | Connexa Announces 1:20 Reverse Split to Remedy Bid Price Delisting Not |
| **SXTC** | $6M | WATCH → AVOID | distress/going-concern | China SXT Pharmaceuticals, Inc. Announces Share Consolidation |
| **ABTS** | $6M | DISTRESSED-RECOVERABLE → AVOID | distress/going-concern | Abits Group Inc Announces Changes of the Authorized Shares and Share C |
| **OCG** | $3M | DISTRESSED-RECOVERABLE → AVOID | distress/going-concern | Oriental Culture Holding LTD. Granted Additional 180 Calendar Day Grac |
| **PW** | $3M | WATCH → AVOID | distress/going-concern | Power REIT Receives Notice of Non-Compliance with NYSE American Contin |
| **BTOG** | $3M | WATCH → AVOID | distress/going-concern | Bit Origin Receives 180-Day Extension from Nasdaq to Regain Compliance |
| **UPC** | $2M | WATCH → AVOID | distress/going-concern | Universe Pharmaceuticals INC Receives Nasdaq Notification Regarding Mi |
| **WOK** | $0M | DISTRESSED-RECOVERABLE → AVOID | distress/going-concern | WORK Medical Technology Group LTD Announces 1-for-100 Reverse Stock Sp |

## ⤵️ DOWNGRADES — funded burners cut from AVOID (128)

> Flagged AVOID(cash_burn) on a short snapshot runway, but a just-closed equity raise (public offering / registered direct / private placement) extends the runway the snapshot can't see → downgraded to WATCH. Top by size:

| Ticker | Mkt cap | Raise headline |
|---|---:|---|
| **AAOI** | $14.2B | Applied Optoelectronics Closes Exchange of 2026 Notes and Concurrent Regist |
| **CNTA** | $6.1B | Centessa Pharmaceuticals Announces Pricing of $250,000,000 Public Offering  |
| **XENE** | $5.0B | Xenon Pharmaceuticals Announces Pricing of Upsized $650.0 Million Public Of |
| **RCAT** | $1.9B | Red Cat Announces Pricing of Public Offering of Common Stock |
| **NTLA** | $1.9B | Intellia Therapeutics Announces Pricing of Public Offering of Common Stock |
| **IMTX** | $1.3B | Immatics Announces Pricing of $150 Million Public Offering |
| **IAUX** | $1.2B | i-80 Gold Announces Upsizing of Previously Announced Bought Deal Public Off |
| **ABSI** | $998M | Absci Announces Pricing of Public Offering of Common Stock |
| **LXRX** | $848M | Lexicon Announces Closing of Approximately $94.6 Million Public Offering an |
| **ALOY** | $764M | REalloys Announces Pricing of Upsized $50 Million Public Offering |
| **AVTX** | $689M | Avalo Therapeutics Announces Pricing of $375 Million Public Offering |
| **NFGC** | $622M | PALISADES ANNOUNCES $2.5 MILLION FULLY SUBSCRIBED NON-BROKERED PRIVATE PLAC |
| **VELO** | $472M | Velo3D, Inc. Announces Pricing of $50 Million Underwritten Registered Direc |
| **CGC** | $463M | recent capital raise extends runway | FR:Canopy Growth Is Re |
| **OVID** | $448M | Ovid Therapeutics Announces Pricing of $60 Million Private Placement |
| **DDD** | $428M | 3D Systems Announces Pricing of $50 Million Upsized Public Offering |
| **ABAT** | $424M | $10M Registered Direct Offering Priced At-The-Market Under Nasdaq Rules |
| **CLPT** | $387M | ClearPoint Neuro Launches Proposed Public Offering of Common Stock |
| **SENS** | $348M | Senseonics Announces Pricing of $80 Million Public Offering of Common Stock |
| **CATX** | $346M | Perspective Therapeutics Announces Pricing of $80 Million Underwritten Offe |
| **DUOT** | $345M | Duos Technologies Group, Inc. Announces Pricing of $65 Million Public Offer |
| **PRLD** | $303M | Prelude Therapeutics Announces $25 Million Private Placement |
| **LODE** | $298M | Comstock Inc. Prices $50 Million Upsized and Oversubscribed Public Offering |
| **FATE** | $231M | Fate Therapeutics Announces Pricing of $100 Million Underwritten Offering a |
| **ARQQ** | $211M | Arqit Quantum Inc. Announces Closing of $16.2 Million Registered Direct Off |

_…and 103 more (full list in CALIBRATION_LEDGER.csv, verdict=OVERFLAG_recent_raise)._

## 🟥 Final AVOID list (575) — top 40 by size

| Ticker | Sector | Mkt cap | Type | API-corroborated |
|---|---|---:|---|:--:|
| **FTAI** | Information Technology | $24.0B | fraud |  |
| **INSM** | Health Care | $20.4B | cash_burn |  |
| **BBIO** | Health Care | $13.2B | insolvency |  |
| **APLD** | Information Technology | $11.3B | insolvency |  |
| **CYTK** | Health Care | $9.7B | insolvency |  |
| **MSGS** | Communication Services | $9.3B | insolvency |  |
| **LUMN** | Communication Services | $9.2B | insolvency |  |
| **W** | Consumer Discretionary | $9.0B | insolvency |  |
| **CORZ** | Financials | $8.2B | insolvency |  |
| **CLF** | Materials | $7.7B | cash_burn |  |
| **VFS** | Unknown | $7.5B | insolvency |  |
| **IBRX** | Health Care | $7.2B | insolvency | ✓ |
| **TGTX** | Health Care | $6.1B | fraud | ✓ |
| **REZI** | Industrials | $4.7B | cash_burn |  |
| **PLUG** | Information Technology | $4.5B | cash_burn |  |
| **BTDR** | Financials | $4.3B | fraud |  |
| **CLSK** | Financials | $4.0B | fraud |  |
| **RDW** | Industrials | $3.7B | cash_burn |  |
| **RNG** | Information Technology | $3.5B | insolvency |  |
| **RUN** | Information Technology | $3.2B | insolvency |  |
| **CLMT** | Energy | $3.1B | insolvency | ✓ |
| **BKD** | Health Care | $2.9B | insolvency |  |
| **CHRN** | Industrials | $2.7B | cash_burn |  |
| **WOLF** | Information Technology | $2.7B | insolvency | ✓ |
| **VISN** | Information Technology | $2.7B | insolvency |  |
| **STNE** | Unknown | $2.5B | cash_burn |  |
| **PTON** | Consumer Discretionary | $2.5B | insolvency |  |
| **BW** | Materials | $2.4B | insolvency |  |
| **ALMS** | Health Care | $2.4B | cash_burn | ✓ |
| **AMBP** | Materials | $2.4B | insolvency |  |
| **PIII** | Health Care | $2.4B | insolvency |  |
| **PCT** | Materials | $2.3B | cash_burn |  |
| **DCO** | Industrials | $2.3B | cash_burn |  |
| **MLCO** | Unknown | $2.2B | insolvency |  |
| **ESTA** | Health Care | $2.2B | cash_burn |  |
| **RARE** | Health Care | $2.2B | insolvency |  |
| **LCID** | Consumer Discretionary | $2.0B | cash_burn |  |
| **NKTR** | Health Care | $1.9B | cash_burn |  |
| **IOVA** | Health Care | $1.9B | cash_burn | ✓ |
| **APPN** | Information Technology | $1.8B | insolvency |  |

_…and 535 more in CALIBRATION_LEDGER.csv (effective_bucket=AVOID)._

---
_Limitations carry from DISTRESS_AGENT.md §10. The AVOID-fraud names are 'investigate', corroborated where the API column shows ✓. SKIP names lack ≥2y data._
