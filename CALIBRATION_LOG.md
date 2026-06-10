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

- **"Regains compliance" recoveries miscounted as distress.** A headline can contain a distress
  keyword ("minimum bid price") while announcing the OPPOSITE — the company *regained* compliance
  (AHG/DARE/OCG/SQFT). **Fix:** `BK_POSITIVE` guard + a "regains…compliance" co-occurrence check in
  `massive_api.event_scan` excludes recovery articles; also added leaked plaintiff firm "Johnson
  Fistel" to LAWFIRM. Re-ran 99 affected names → AHG→CLEAR, DARE→WATCH, SQFT→recoverable; escalations
  27→23 (genuine "receives notice / reverse split to avoid delisting" cases remain).
  Final after overlay: AVOID 575, WATCH ~775, recoverable ~415, CLEAR ~2444. See CALIBRATED_FINDINGS.md.
