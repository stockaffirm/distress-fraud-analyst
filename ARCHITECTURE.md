# Distress & Fraud Analyst — Visual Architecture

## 1. Component stack (who calls whom)

```
 ┌────────────────────────────────────────────────────────────────────────────┐
 │  CALLABLE SURFACE  — how anyone reaches the subagent                        │
 │                                                                            │
 │   /distress-fraud-screen  ──►  agent: distress-fraud-analyst               │
 │   (skill, SKILL.md)            (subagent_type, agent .md)                  │
 └───────────────────────────────────┬────────────────────────────────────────┘
                                     │  STEP ZERO: read brain LIVE every run
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────────┐
 │  BRAIN  (docs — read fresh each run, so any edit updates the agent)         │
 │   AGENT_PLAYBOOK.md · DISTRESS_AGENT.md · CALIBRATION_LOG.md                │
 └───────────────────────────────────┬────────────────────────────────────────┘
                                     │  routes by what was asked
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
  ONE TICKER                    WHOLE UNIVERSE                 CALIBRATE / CONTINUE
  distress_screen.py            distress_batch.py              loop_runner.py
   + calibrate.py --ticker       → DISTRESS_SCREEN.csv          → state_db (SQLite)
                                  → DISTRESS_REPORT.md           → calibrated_report.py
        │                             │                             │
        └─────────────┬───────────────┴─────────────┬───────────────┘
                     ▼                               ▼
            ┌──────────────────┐            ┌──────────────────────┐
            │ LAYER 1 (Python) │            │ LAYER 2 (Python)     │
            │ fundamentals     │            │ DIRECT Massive API   │
            │ distress_screen  │            │ massive_api.py       │
            │ data_loader      │            │  news · short int.   │
            │ (7 models)       │            │  · capital raises    │
            └──────────────────┘            └──────────────────────┘
                     └───────────── reconciled by ─────────────┘
                                       ▼
                             effective_bucket  (the answer)
```

## 2. Single-ticker decision flow (the pipeline + the logic)

```
 TICKER
   │
   ▼
 ┌─ data_loader.full_history ── 10y income + balance + CASH-FLOW (exact) ─┐
   │
   ▼
 LAYER 1  distress_screen.screen()  — 7 models, all at once
   │   Altman Z''   Beneish M   Ohlson O   Sloan accruals   Montier C
   │   + liquidity / leverage / cash-runway
   │
   ▼   gates (cash-serviceability first, multi-signal — never one model alone)
   │
   ├─ sector/float guards → suppress Altman/Beneish for Fin/RE/Util/lenders/float
   │
   ▼
 SCREEN BUCKET ──────────────────────────────────────────────────────────┐
   │                                                                       │
   ▼                                                                       │
 LAYER 2  massive_api.event_scan()  — live ground truth                    │
   │   news events (going-concern/Ch11/SEC/restatement)                    │
   │   short interest (days-to-cover)   recent capital raise               │
   │   guards: focus-filter · law-firm-spam · recovery ("regains compl.")  │
   │                                                                       │
   ▼                                                                       │
 OVERLAY (calibrate.effective_bucket) ◄────────────────────────────────────┘
   │
   ├─ CORROBORATED  (API confirms)              → AVOID
   ├─ OVERFLAG_recent_raise (just raised $)     → downgrade AVOID→WATCH
   ├─ UNDERFLAG, ≥2 distress/fraud articles     → escalate up to WATCH/AVOID
   ├─ short interest                            → only corroborates, never flags alone
   └─ else                                      → keep screen bucket
   │
   ▼
 EFFECTIVE BUCKET  =  AVOID(insolvency | cash_burn | fraud)
                      | DISTRESSED-RECOVERABLE | WATCH | CLEAR
```

## 3. The bucketing logic (how a name lands)

```
 is an enterprise DCF/screen valid?  (not Financials/REIT/float)
   │
 cash serviceability + solvency
   │
   ├─ FORTRESS (net cash + FCF>0)  ───────────────────────────────────► CLEAR
   ├─ profitable + serviceable leverage (overrides) ──────────────────► CLEAR
   │
   ├─ insolvent-from-losses  OR  CFO-burn + short runway (<18mo)
   │     └─ over-levered operating business ──────────► AVOID(insolvency)
   │     └─ pre-profit, runway-dependent ─────────────► AVOID(cash_burn)
   │            └─ but just RAISED capital (API) ──────► downgrade → WATCH
   │
   ├─ Beneish M>-1.78 + high positive accruals + poor 4y cash-conversion + corrob.
   │     └─ profitable & cash-generative? (one-time item) ─► WATCH (forensic watch)
   │     └─ else ──────────────────────────────────────────► AVOID(fraud)
   │            └─ confirm with news/SEC/short-report (API)
   │
   ├─ distressed but CFO>0 + ≥3 recovery signals ─────► DISTRESSED-RECOVERABLE
   │
   └─ live news shows going-concern/SEC/restatement the screen missed (≥2 art.)
         └─ escalate CLEAR/WATCH ───────────────────────► WATCH / AVOID
```

## 4. The calibration loop (closed loop — how it gets "perfect")

```
        ┌──────────────────────────────────────────────────────────────┐
        │                                                              │
        ▼                                                              │
  state_db (SQLite)  ── DUE tickers (pending ∪ stale-TTL ∪ logic-bump) │
        │                                                              │
        ▼                                                              │
  loop_runner.py  (head-less, time-budgeted, cron-safe, resumable)     │
        │   for each DUE ticker, mcap order:                           │
        ▼                                                              │
  calibrate.process_one  →  screen bucket  ⊕  API overlay  =  effective │
        │                                                              │
        ▼                                                              │
  VERDICT:  AGREE | CORROBORATED | OVERFLAG_* | UNDERFLAG_* | NEWS_NOTE │
        │                                                              │
        ├─ AGREE/CORROBORATED ─────────────► write to DB, done         │
        │                                                              │
        └─ OVERFLAG_* / UNDERFLAG_* (a disagreement) ──► surfaced       │
                    │                                                   │
                    ▼                                                   │
            ◄═══ AGENT (LLM) — the ONLY human-judgment step ═══►        │
              find the SYSTEMATIC cause (not per-ticker)                │
              fix the rule in distress_screen.py / massive_api.py       │
              log why+what in CALIBRATION_LOG.md  ──────────────────────┘  (bumps
              re-run ticker → regression-check → done                       logic_version
                                                                            → DB rows
   Result so far: 5,022/5,022 processed; zero fundamentals bucket errors;   re-flagged DUE)
   all adjustments were API-overlay precision → CALIBRATED_FINDINGS.md
```

## 5. The self-sync loop (keeps the agent md current with the brain)

```
   every 10 min  (cron f901627b  / launchd)
        │
        ▼
   sync_agent.py  ── hash the brain docs ── compare to AGENT_SYNC_STATE.json
        │
        ├─ NO_CHANGE ───────────────────────────────► stop (cheap)
        │
        └─ CHANGED
              ├─ regenerate AUTO-SYNCED manifest block in the agent .md
              ├─ append a line to AGENT_SYNC_LOG.md
              └─ if a METHOD doc changed → agent makes the minimal md/playbook edit
```

## Legend
- **Layer 1 = Python, offline, exhaustive** (fundamentals → candidate bucket).
- **Layer 2 = Python, live Massive API** (news/short/raise → confirm or correct).
- **effective_bucket = Layer1 ⊕ Layer2 = the final answer.**
- **Agent (LLM) only enters to CALIBRATE** — encode a general fix + log it; everything
  else runs deterministically on all 5,022 names with no model in the loop.
