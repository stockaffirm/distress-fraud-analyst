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
   │                            (live Alpha Vantage fetch, 24hr SQLite cache)
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
   │
   ▼  (only when explain=true — Mode 2 subagent or Mode 3 API)
 LAYER 3  LLM INVESTIGATOR  (llm_client.py)  ← PRIMARY ANALYST
   │   Receives: full 5yr financials + Python screen (as evidence) + live API signals
   │   Runs investigation loop per notable signal:
   │     HYPOTHESIZE (training) → LOOK UP (data) → CONFIRM/REFUTE → LABEL
   │   Returns structured JSON verdict:
   │     bucket          — LLM's OWN verdict; becomes effective_bucket (primary)
   │     confidence      — "high"|"medium"|"low"
   │     grounded_claims — [{claim, field, value, fy}]  ← [GROUNDED]
   │     training_flags  — [{concern, why_ungrounded, investigate, urgency}]  ← [TRAINING-FLAG]
   │     unresolved      — [{screen_flag, explanation, next_step}]
   │     narrative       — 2-4 sentence WHY
   │   LLM MAY disagree with Python screen — explains why in narrative
   │   TRAINING-FLAG(distress/fraud/watch) = valid bucket when risk is suspected but ungroundable
   ▼
 EFFECTIVE_BUCKET  =  LLM bucket (primary, explain=true)  |  Python screen (fallback, explain=false)
   screen_bucket / screen_flags  =  Python evidence (always present, secondary)
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

## 6. The three callable modes

```
  MODE 1 — Skill (Claude chat)
  ────────────────────────────
  /distress-fraud-screen VFS
       └─► skill/distress-fraud-screen/SKILL.md
             └─► agent: distress-fraud-analyst
                   └─► runs Layers 1+2+3 inline

  MODE 2 — Subagent (agent-to-agent)
  ────────────────────────────────────
  subagent_type: distress-fraud-analyst
  (portfolio-analyst / fair-value-analyst / any workflow)
       └─► ~/.claude/agents/distress-fraud-analyst.md
             └─► reads brain docs live (STEP ZERO)
                   └─► runs Layers 1+2 (Python) + Layer 3 (LLM) for explanation

  MODE 3 — API server (any server, any language, any scheduler)
  ──────────────────────────────────────────────────────────────
  python3 api_server.py --port 8080

  GET  /health                        → status, llm_active, provider
  POST /analyze    {"ticker":"VFS",   → full JSON verdict
                    "explain":true}     (explain=true triggers Layer 3 LLM)
  POST /analyze/batch                 → parallel, up to 200 tickers
  GET  /universe/summary              → CALIBRATED_FINDINGS.md as JSON

  explain=false: Layers 1+2 only, pure Python, instant, no LLM cost
  explain=true:  Layers 1+2+3, full financials passed to LLM, cited verdict
```

## 7. The grounding protocol (Layer 3 — LLM investigator)

```
  PROBLEM: LLM says "buyback artifact" from training knowledge, not data.
  SOLUTION: Pass full 5yr financials to the LLM; require it to investigate.

  Investigation loop (per notable signal):
  ┌─────────────────────────────────────────────────────────────────────┐
  │  Signal: "equity is NEGATIVE"                                       │
  │                                                                     │
  │  Step 1 HYPOTHESIZE (training OK here)                              │
  │    candidates: (a) buybacks  (b) accumulated losses  (c) impairment │
  │                                                                     │
  │  Step 2 LOOK UP (from full financials in context)                   │
  │    → treasury_stock_2024 = -172B                                    │
  │    → retained_earnings_2024 = -19B                                  │
  │                                                                     │
  │  Step 3 EVALUATE                                                    │
  │    treasury ($172B) >> RE deficit ($19B) by 9×                      │
  │    → hypothesis (a) CONFIRMED                                       │
  │    → hypothesis (b) REFUTED (RE deficit is small)                   │
  │                                                                     │
  │  Step 4 LABEL                                                       │
  │    "Equity negative due to buybacks, not losses."                   │
  │    [GROUNDED: treasury_stock=-$172B, RE=-$19B, fy=2024]             │
  └─────────────────────────────────────────────────────────────────────┘

  If data does NOT confirm hypothesis:
    [TRAINING-FLAG: <pattern> — not data-confirmable; needs 10-K investigation]

  Rule: every factual claim in the verdict must carry one of these two labels.
  Training knowledge = valid for PATTERN RECOGNITION; invalid for FACT ASSERTION.
```

## Legend
- **Layer 1 = Python, deterministic** (fundamentals → candidate bucket; 7 models).
- **Layer 2 = Python, live Massive + AV API** (news/short/raise → confirm or correct). Both at limit=200.
- **screen_bucket = Layer1 ⊕ Layer2** — Python's verdict; always present as secondary evidence.
- **Layer 3 = LLM Investigator (PRIMARY)** — receives full financials + Python screen as evidence.
  Issues its own structured JSON verdict. `effective_bucket` = LLM bucket when explain=true.
  TRAINING-FLAG(distress/fraud/watch) = valid bucket when risk is suspected but ungroundable.
  Falls back to Python screen_bucket if LLM is unavailable or explain=false.
- **Calibration LLM** — only enters to encode a general fix when screen ≠ API. Separate from
  Layer 3 (investigation/verdict) and entirely separate from the bucket evaluation logic.
