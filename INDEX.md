# Fair-Value Analyst — system index (start here)

An independent, Morningstar-calibrated intrinsic-value analyst. This folder is the whole system:
brain (docs), engine (scripts), state (ledger/overrides/verdicts), and the agent/skill/scheduler
that run it. Any agent can pick it up cold by reading this file.

## How it's invoked
- **Skill:** `/fair-value-analyst` (or it auto-triggers on "fair value of X", "value my portfolio on a DCF", "continue the 1500").
- **Agent:** `Agent(subagent_type: "fair-value-analyst", …)` — definition at `~/.claude/agents/fair-value-analyst.md`. (Registers on next session start.)
- **Scheduler:** scheduled task `portfolio-fv-sync` runs `portfolio_sync_check.py` every 10 min to keep `/Users/prasadmenon/Claude/portfolio_analysis.md` in sync (managed block) and flag holdings missing a verdict.

## Brain (read fresh every run — these ARE the instructions)
| File | What |
|---|---|
| `PROCESS.md` | the per-ticker SOP: the loop, buckets, live-API commands, §Rules learned, "done" criteria |
| `ALGORITHM.md` | the model spec (FCFF→moat→uncertainty→WACC→3-stage DCF→star), every constant + line ref |
| `MS_CALIBRATION_LOG.md` | how the model was calibrated to live Morningstar (12 iterations) + the irreducible ceiling |

## Engine (scripts, pure-Python3, no venv)
| Script | Use |
|---|---|
| `data_loader.py` | read cached 10yr fundamentals + `recommendations.csv` context (+ `full_history` w/ real cash flows) |
| `valuation.py` | the model: `analyze()`, the 3-stage DCF, moat/uncertainty, the override hooks (CSV + RUNTIME) |
| `research.py TICKER` | analyst worksheet: 10yr trajectory + my baseline + MS comp |
| `value_with.py TICKER [g] [m] [unc]` | fair value under a trial assumption set (no file writes) |
| `value_batch.py --range a b / --overrides "T:g:m:u,…"` | batch valuer (one process) |
| `reconcile.py TICKER` | my FV vs Morningstar + reverse-solve which assumption explains the gap |
| `portfolio_sync_check.py` | refresh the managed block in portfolio_analysis.md from LEDGER (the scheduler runs this) |

## State (resumable — this is the memory)
| File | What |
|---|---|
| `LEDGER.csv` | every ticker + status (pending/done) + bucket/my_fv/ms_fv/ratio. **Resume = first `pending` row.** |
| `analyst_overrides.csv` | per-name analyst inputs: `ticker,fwd_growth,mature_margin,uncertainty,note` |
| `VERDICTS.md` | the reasoned verdict per name (how/why, why ≥ MS, risk) |
| `ms_cache/` | cached live Morningstar pulls |
| `SYNC_LOG.md` | portfolio-sync history |

## The override levers (per-name analyst judgment, mirrors Morningstar analysts)
`analyst_overrides.csv` columns: **fwd_growth**, **mature_margin**, **uncertainty** (Low..Extreme),
note. Set only what the business warrants; leave blank to use the model default. Uncertainty is the
lever for risk the model can't see (regulatory/litigation/political/accounting).

## Status (2026-06-09)
Model calibrated to Morningstar (matchable median ~0.97×, moat ~77%). Portfolio: ~12/19 verdicted
(NKE, AMZN, MSFT, META, GOOG, SBUX, CAVA, CMG, CRWD, UNH, V, PANW…). Universe: 1,500 seeded in LEDGER,
worked one-by-one. Next pending = see `LEDGER.csv`.
