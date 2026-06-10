# Distress Screen — Sequential Per-Ticker Calibration Loop (log + protocol)

**Goal:** validate and calibrate `distress_screen.py` against DIRECT-API ground truth,
**one ticker at a time**, across the whole universe (~5,022), largest market cap first.
Fully **resumable** — any agent can stop and continue from the ledger.

## How to run / resume (any agent, anytime)

**Durable state machine (preferred) — SQLite status table + self-starting runner:**
```
cd stockaffirmtodos/analyst_agent
python3 state_db.py init          # one-time: seed all ~5,022 tickers + import the ledger
python3 state_db.py stats         # status / effective_bucket / due counts
python3 loop_runner.py --minutes 8  # process all DUE tickers for up to 8 min, then exit (cron-callable)
python3 loop_runner.py --export   # rewrite CALIBRATION_LEDGER.csv (human-readable mirror) from the DB
```
- **State:** `calibration_state.db` (table `tickers`). Each row carries status / verdict /
  effective_bucket / last_processed_utc / logic_version. **This is the "where to start / what to
  reprocess" store** — survives any stop; resume = just run `loop_runner.py` again.
- **A ticker is DUE** when: `status='pending'` (new), OR `logic_version != current` (bump
  `LOGIC_VERSION` in `state_db.py` after a logic change → forces full re-validation), OR past its
  TTL (AVOID/WATCH/REC 7d, CLEAR 30d → automatic news refresh). Idle/no-op when nothing is due.
- `loop_runner.py` is head-less (pure Python + direct API, no LLM/auth) → safe for a cron/launchd.

**Manual / inspection (also fine):**
```
python3 calibrate.py --review     # verdict mix + the actionable disagreements so far
python3 calibrate.py --ticker XYZ # inspect one ticker (screen + live API)
python3 massive_api.py XYZ        # raw live distress/fraud/raise/short read for a ticker
```
Order is deterministic (market cap desc), so progress is monotonic and restart-safe.

## What each ticker goes through (the loop)
1. **Re-screen LIVE** — `distress_screen.screen()` on cached fundamentals + cache news
   (so any logic change takes effect immediately on re-run).
2. **Direct-API ground truth** — `massive_api.event_scan()`:
   - live historical **news** → distress events (going-concern/Ch11/delisting/default),
     fraud events (SEC/short-seller/restatement/material-weakness), and **capital raises**
     — all gated by a **focus filter** (article's primary ticker == this ticker; tags are
     subject-ordered) and a law-firm-spam filter.
   - **short interest** → days-to-cover (a direct distress/squeeze tell).
3. **Verdict** (bucket vs API evidence) — logged to the ledger:

| Verdict | Meaning | Action |
|---|---|---|
| `CORROBORATED` | AVOID + API event/short confirms | none (good) |
| `AGREE` | non-AVOID + no API event | none |
| `AVOID_unconfirmed` | AVOID but no API signal (often thin coverage) | spot-check |
| `OVERFLAG_recent_raise` | AVOID cash-burn but a recent raise extends runway | **calibrate** |
| `OVERFLAG_review` | AVOID-fraud but recent raise / no fraud event | **calibrate** |
| `UNDERFLAG_distress_event` | non-AVOID but ≥2 news articles show distress | **calibrate** |
| `UNDERFLAG_fraud_event` | non-AVOID but ≥2 news articles show fraud/SEC | **calibrate** |
| `NEWS_NOTE` | single news mention (e.g. APP's one short-report) | investigate, not a screen error |
| `SHORT_WATCH` | CLEAR but elevated short interest | spot-check |
| `SKIP` | no cached data / <2y | none |

## Calibration protocol (the human/agent-in-the-loop part)
When `--review` surfaces an **actionable** disagreement (OVERFLAG_* / UNDERFLAG_*):
1. Open the ticker: `python3 calibrate.py --ticker XYZ` and `python3 massive_api.py XYZ`.
2. Decide if it's a **systematic** pattern (sector, signal combo) or a one-off.
3. If systematic → change the **general logic** in `distress_screen.py` (a threshold, a veto,
   a sector guard) — never a per-ticker hack.
4. Re-run the ticker to confirm it's fixed AND spot-check a few prior tickers of the same
   pattern (regression). Periodically re-run the full batch (`distress_batch.py`).
5. **Log the change below** (why it was different, what changed, before→after).
6. Delete affected ledger rows so they re-validate on the next pass.

---

## Change log (append newest at the bottom)

### Pre-loop calibration (from the adversarial audit, already applied)
Established before the sequential loop; see `DISTRESS_AGENT.md` §7 + §9. Net effect on the
4,210-name run: AVOID 22%→16%, fraud 57→16. Fixes: lender-CFO suppression, fortress &
long-runway (24mo) bankruptcy vetoes, cash-generative & profitable-net-cash fraud demotion,
float-business detection, buyback-negative-equity guard, hyper-growth cash-conversion gate,
insolvency-vs-cash-burn split.

### API ground-truth scanner calibration (during loop bring-up)
- **Peer-mention false positives** (MU tagged on a Supermicro accounting story; CVX on a
  "fund liquidates" piece; PEP on a Beyond-Meat delisting article). Root cause: Massive
  ticker-tagged news includes peripheral tickers. **Fix:** focus filter — only count an event
  when the article's **primary** ticker (`tickers[0]`) is the queried ticker. Verified tags are
  subject-ordered ("Marvell, Intel, Micron" → `[MRVL,INTC,MU]`).
- **Ambiguous keyword** "liquidation" (a fund liquidating a position ≠ corporate liquidation).
  **Fix:** replaced with "plan of liquidation" / "chapter 7 liquidation".
- **Single-mention over-trigger** (APP: one article referencing AppLovin's SEC probe /
  short-report, while it's fundamentally clean & profitable). **Fix:** an UNDERFLAG needs **≥2**
  corroborating articles; a single mention is a `NEWS_NOTE` (investigate, not a screen error).

### Mega-cap validation (first 80 tickers, market-cap desc)
78/80 `AGREE`, 1 `SKIP`, 1 `NEWS_NOTE` (APP). **No false flags among the largest names** —
the screen does not over-flag healthy giants. Calibration value now shifts to the AVOID-heavy
mid/small-caps below.

### Effective-bucket overlay + API-scan precision (tickers ~500–1,770)
As the sweep entered the AVOID-dense mid-caps, the systematic issues were all in the
**API overlay / news scan**, not the fundamentals screen (which kept ~96% AGREE):
- **Added `effective_bucket`** = screen ∪ direct-API evidence — the FINAL per-ticker answer.
  The screen can't see a Gotham/Muddy Waters short report or a just-closed equity raise; the
  overlay can. Rules: CORROBORATED→AVOID; OVERFLAG_recent_raise/review→WATCH (downgrade a
  funded burner, e.g. AAOI/CNTA/XENE closed offerings → runway extended); UNDERFLAG_fraud(≥2)→
  WATCH/AVOID (e.g. SOFI Muddy Waters, SEZL); UNDERFLAG_distress(≥2)→WATCH/AVOID.
- **Law-firm spam filter was leaking** — BFA Law "Contact … if you suffered losses / Investors
  with Losses" solicitations (JEF) slipped through and faked an SEC/bankruptcy event. **Fix:**
  expanded LAWFIRM with the real phrasings + firm names (BFA, Rosen, Pomerantz, Bragar Eagel,
  Schall, Glancy, Faruqi, Kessler Topaz, Levi & Korsinsky, Robbins, Gross Law…). JEF→clean.
- **Ambiguous distress keywords.** "delisting" caught a *voluntary* Nasdaq-Stockholm delisting
  (TIGO/Millicom); "debt restructuring" caught routine refinancing. **Fix:** distress-specific
  only — "delisting notice / minimum bid price / regain compliance / deficiency notice",
  "out-of-court restructuring / restructuring support agreement", "going concern doubt /
  substantial doubt". TIGO→clean.
- **Counterparty bankruptcies.** "filed for bankruptcy" matched JEF articles about a *counterparty*
  (First Brands). Handled by the spam filter here; focus filter (primary ticker) covers the rest.
- **Short-interest noise.** days-to-cover ≥10 flagged dozens of healthy low-volume names
  (REITs/banks/insurers: ADC, EPRT, ERIE, BNT, TR…). **Fix:** short interest no longer creates a
  flag on its own — it only **corroborates** an existing fundamentals AVOID. SHORT_WATCH removed.

Net: through 1,770 names (mcap-desc), **zero fundamentals-screen bucket errors**; all
adjustments were API-overlay precision. The screen + overlay is converged — the long tail runs
on the deterministic loop, surfacing only genuine OVERFLAG/UNDERFLAG for review.

### FULL UNIVERSE COMPLETE — 5,022 processed, 0 errors (mcap-desc, direct-API overlay)
| Bucket | Fundamentals screen | **Effective (screen ∪ live API)** |
|---|---|---|
| AVOID | 687 | **575** |
| WATCH | 650 | 774 |
| DISTRESSED-RECOVERABLE | 422 | 416 |
| CLEAR | 2,451 | 2,445 |
| (SKIP no-data/<2y) | 812 | 812 |

The live-API overlay changed **151** buckets: **128 AVOID→WATCH** (funded cash-burners with a
confirmed recent equity raise → runway extended; the audit's #1 false-positive class, now caught
systematically), **16 promoted to AVOID** (WATCH/REC → AVOID on ≥2 corroborating distress/fraud
news articles), 6 CLEAR→WATCH, 1 REC→WATCH. Of the 687 screen-AVOIDs: **143 API-corroborated,
128 raise-downgraded, 416 unconfirmed** (mostly thin-coverage micro-caps — fundamentals stand).

### Durable state machine + self-starting loop (this is the resumable engine going forward)
Migrated the run into **`calibration_state.db`** (SQLite `tickers` table) driven by
**`loop_runner.py`** — a time-budgeted, head-less, cron-callable processor. Proven: idles when
nothing is due; when N rows go stale/pending it processes exactly those N (mcap order) and stops.
"What to reprocess" = pending ∪ logic_version-mismatch ∪ past-TTL. Survives any stop (state on
disk). NOTE: state is **local SQLite, not Supabase** (project rule: no Supabase writes); the schema
maps 1:1 to a Supabase table if that rule is lifted.

<!-- next entries appended by the loop as systematic patterns are found -->

### 4-layer grounding architecture (June 2026)

Four systematic additions to the LLM investigation layer (`llm_client.py`, `data_loader.py`,
`massive_api.py`, new `edgar_api.py`) to eliminate training-data hallucination from grounded claims.
No changes to fundamentals screen logic (`distress_screen.py`).

**1. Stock price grounding (`data_loader.price_history`)**
- **Problem:** LLM was citing stock price ranges from training data ("Oracle $80→$345" was
  fabricated; actual range $58→$279 per AV). Any price claim without a data source is a hallucination.
- **Fix:** Added `price_history(ticker, months=24)` to `data_loader.py` using AV
  `TIME_SERIES_MONTHLY_ADJUSTED`. Returns 24 months of monthly adj_close, newest-first. Cached
  per-ticker in `av_price_cache` table (SQLite). Wired into `llm_client._build_prompt()` as a
  PRICE HISTORY block. `grounding_source = "av_price_data"`.
- **Result:** All LLM price claims now cite specific date + adj_close from the 24-month feed.
  Self-check rule updated: price claims require `av_price_data` grounding or TRAINING-FLAG.

**2. Full article corpus (`massive_api.py`)**
- **Problem:** The news corpus was capped at 30 articles and lacked body text. LLM was instructed
  to "search for X" — creating training-data confirmation bias (it would look for what it expected
  to find, not what was actually there). Oracle had 126 focused articles; only 30 were passed.
- **Fix:** Removed the `[:30]` cap. All focused articles are now passed, each with `desc` (body
  text, 300 chars from the Massive API). New instruction: "read all articles, discover freely —
  do NOT search for expected terms." `all_focused_articles` field added; `recent_focused_headlines`
  kept as backward-compat alias.
- **Result:** Richer news signal; LLM discovers things it didn't know to look for (e.g. new product
  launches, regulatory approvals, management changes) alongside distress signals.

**3. EDGAR 10-K signals (`edgar_api.py` — new module)**
- **Problem:** Going-concern opinions, identified material weaknesses, and covenant violations sit in
  the 10-K auditor's report — authoritative, public, cacheable — but were completely absent from
  the LLM's grounding data. LLM was either guessing from training or leaving these blank.
- **Fix:** New `edgar_api.py` module. Chain: `company_tickers.json` (CIK lookup) →
  `data.sec.gov/submissions/CIK{:010d}.json` (latest 10-K accession + primaryDocument URL) →
  full document download (50MB ceiling — real filings never hit this) → keyword extraction.
  Signals extracted: `going_concern_flag`, `material_weakness_flag`, `covenant_risk_flag`,
  `mda_excerpt`. 7-day SQLite cache in `av_cache.db`. `grounding_source = "edgar_10k"`.
- **False positive fixes discovered during ORCL/BYND testing:**
  - **ORCL material weakness FP:** "assessing the risk that a material weakness exists" is standard
    PwC/Big-4 audit methodology boilerplate — it appears in EVERY clean audit, not just MW findings.
    **Fix:** Added `_MATERIAL_WEAKNESS_EXCLUDE` list to `_find_excerpts()`. Narrowed
    `_MATERIAL_WEAKNESS_KWS` to only positive-finding phrases ("identified a material weakness",
    "has a material weakness", etc.).
  - **BYND covenant FP:** "not in compliance with FCPA" and "not in compliance with foreign law"
    triggered `covenant_risk_flag=True`. These are regulatory compliance disclosures, not debt
    covenant violations. **Fix:** Removed "not in compliance with" and "failed to maintain" from
    `_COVENANT_KWS`; kept only specific debt terms ("event of default", "forbearance agreement",
    "debt covenant", "covenant waiver", "cross-default", etc.).
- **Result:** `edgar_10k_signals` gives auditor-grounded going-concern and material weakness signal
  that the fundamentals screen cannot see. Wired into `llm_client._build_prompt()` as an EDGAR
  10-K SIGNALS block with flags, keyword excerpts, and MD&A excerpt.

**4. calibrate.py EDGAR wiring**
- `process_one()` now calls `_edgar_signals(ticker)` and adds `edgar_gc`, `edgar_mw`, `edgar_cov`
  (0/1 flags) to every ledger row. COLS updated to include these three fields.
- `verdict_for(res, e, edgar=None)` now checks `edgar.going_concern_flag` for non-AVOID buckets:
  if the auditor issued a going-concern opinion and the screen returned CLEAR/WATCH/DISTRESSED-
  RECOVERABLE, verdict = `UNDERFLAG_gc_opinion`.
- `effective_bucket()` maps `UNDERFLAG_gc_opinion` → `AVOID`: "promoted — EDGAR 10-K auditor
  going-concern opinion found; screen missed it."

**Calibration lesson:** Two classes of EDGAR false positives now documented and fixed.
Re-run `calibrate.py --ticker ORCL` and `--ticker BYND` to verify `edgar_mw=0` and
`edgar_cov=0` for both (post-fix). Bump `LOGIC_VERSION` in `state_db.py` after verifying to
trigger re-validation of EDGAR-flagged names in the durable loop.

- **"Regains compliance" recoveries miscounted as distress.** A headline can contain a distress
  keyword ("minimum bid price") while announcing the OPPOSITE — the company *regained* compliance
  (AHG/DARE/OCG/SQFT). **Fix:** `BK_POSITIVE` guard + a "regains…compliance" co-occurrence check in
  `massive_api.event_scan` excludes recovery articles; also added leaked plaintiff firm "Johnson
  Fistel" to LAWFIRM. Re-ran 99 affected names → AHG→CLEAR, DARE→WATCH, SQFT→recoverable; escalations
  27→23 (genuine "receives notice / reverse split to avoid delisting" cases remain).
  Final after overlay: AVOID 575, WATCH ~775, recoverable ~415, CLEAR ~2444. See CALIBRATED_FINDINGS.md.
