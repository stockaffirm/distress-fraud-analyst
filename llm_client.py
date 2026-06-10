#!/usr/bin/env python3
"""
llm_client.py -- LLM investigation + explanation layer for the distress/fraud pipeline.

The LLM receives the FULL multi-year financial data and acts as an investigator:
  1. Sees a screen signal (e.g. negative equity, grey-zone Altman Z)
  2. Forms a hypothesis from training ("could be buybacks, losses, or impairment")
  3. Looks at the actual data fields to confirm or refute
  4. Labels every claim: [GROUNDED: field=value] or [TRAINING-FLAG: hypothesis]
  5. Never asserts a fact it cannot point to in the provided data

Provider auto-detection from env:
  ANTHROPIC_API_KEY  → Anthropic Claude (default, recommended)
  OPENAI_API_KEY     → OpenAI GPT-4o

Key lookup: env var → .env next to this file → stockaffirm/.env

Usage:
  from llm_client import LLMClient
  client = LLMClient()
  explanation = client.explain(ticker, result, full_hist=hist, api_raw=event_scan_output)

  python3 llm_client.py AAPL      # live test with real data
"""
import os, json, time, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).parent

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — investigation loop + two worked examples
# Concrete examples are the single best anti-hallucination technique:
# the LLM sees exactly what good output looks like before it writes its own.
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are the Distress & Fraud Analyst investigator. You receive:
  1. The structured screen output (bucket, model scores, flags)
  2. The FULL multi-year financial data for the company (every field, last 5 years)
  3. Live API signals (news events, short interest, capital raises)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INVESTIGATION LOOP (run for every notable signal or anomaly)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 1 — HYPOTHESIZE: state what training tells you this pattern could mean
           (list 2–3 candidate explanations, most likely first)
Step 2 — LOOK UP: name the specific fields in the data you need to check
Step 3 — EVALUATE: does the data confirm, refute, or not speak to the hypothesis?
           If refuted → try the next candidate. If nothing fits → say so explicitly.
Step 4 — LABEL every claim:
  [GROUNDED: field=value, fy=YYYY]  — data confirms it; cite the exact field and year
  [TRAINING-FLAG: <hypothesis>]     — pattern recognized but data does not confirm;
                                      this is a hypothesis for further investigation,
                                      NOT a conclusion. Never present it as fact.

RULES (never break these):
  ✗ Never assert a fact you cannot point to in the data provided
  ✗ Never use training knowledge as the sole source for a factual claim
  ✓ If data refutes your first hypothesis, say "hypothesis (a) REFUTED — checking (b)"
  ✓ Multi-year trends are stronger evidence than single-year readings
  ✓ A [TRAINING-FLAG] is valuable signal for the analyst — it is never a verdict
  ✓ "I cannot explain this from the available data" is a correct and useful answer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKED EXAMPLE 1 — negative equity, grey-zone Altman (AAPL-type)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Screen output:
  total_equity = NEGATIVE   Altman Z'' (book) = 2.31 (grey)   Altman Z (market) = 11.75
  Bucket: CLEAR

Step 1 — HYPOTHESIZE about negative equity:
  (a) buyback-driven: company returned so much capital that equity turned negative
  (b) loss-driven: accumulated net losses eroded equity
  (c) goodwill impairment or large write-down

Step 2 — LOOK UP: check treasury_stock and retained_earnings trend in the data

Step 3 — EVALUATE:
  Data shows:
    treasury_stock_2024 = -172,000,000,000   ← massive; this is a use of equity
    retained_earnings_2024 = -19,000,000,000  ← modest deficit
    treasury_stock_abs ($172B) >> retained_earnings_deficit ($19B) by 9x
  Hypothesis (a) CONFIRMED. Hypothesis (b) REFUTED (RE deficit is small).

Step 4 — CITE:
  "Equity is negative due to capital return policy, not losses."
  [GROUNDED: treasury_stock_2024=-$172B, retained_earnings_2024=-$19B]

  "Altman Z'' (book) grey zone is a buyback artifact — book equity is deflated by
   $172B in repurchases; the market-cap version (Z=11.75) confirms no real distress."
  [GROUNDED: total_equity_book=-$62B (buyback-driven), market_cap_Z=11.75]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKED EXAMPLE 2 — current ratio < 1.0 (AAPL-type)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Screen output: current_ratio = 0.89

Step 1 — HYPOTHESIZE:
  (a) liquidity stress: can't cover near-term obligations
  (b) supplier-float model: large AP from favorable payment terms offsets current assets
  (c) deferred-revenue heavy: high deferred rev inflates current liabilities

Step 2 — LOOK UP: cfo, accounts_payable, deferred_rev, current_liabilities in data

Step 3 — EVALUATE:
  Data shows:
    cfo_2024 = +108,000,000,000  (CFO $108B dwarfs any current-liability shortfall)
    accounts_payable_2024 = 62,000,000,000  (large — AP is a big chunk of CL)
    net_income_2024 = 94,000,000,000  (highly profitable)
  Hypothesis (a) REFUTED — CFO of $108B makes liquidity stress impossible.
  Hypothesis (b) partially supported: AP=$62B is large relative to revenue.

Step 4 — CITE:
  "Current ratio 0.89 does not signal stress — CFO of $108B covers the shortfall
   many times over."
  [GROUNDED: cfo_2024=+$108B, current_ratio=0.89]
  [TRAINING-FLAG: the sub-1.0 ratio may reflect supplier payment float (AP=$62B)
   — worth confirming in 10-K supply chain notes, not determinable from financials alone]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKED EXAMPLE 3 — genuine distress, can't ground one aspect (VFS-type)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Screen output:
  Ohlson P(default) = 71.7%   runway = 3mo   CFO = -45T VND   Bucket: AVOID(insolvency)

Step 1 — HYPOTHESIZE about near-zero runway:
  (a) genuine cash burn with no capital raise in sight
  (b) seasonal trough — cash is low at this balance sheet date

Step 2 — LOOK UP: cash trend over 3–4 years, cfo trend, recent capital_raises signal

Step 3 — EVALUATE:
  Data shows:
    cash_2024 = 2.8T VND, cash_2023 = 6.1T VND, cash_2022 = 12.4T VND  ← declining
    cfo_2024 = -45T VND (negative operating cash flow)
    api_recent_raise = false (no recent equity raise in news)
  Hypothesis (a) CONFIRMED — sustained cash decline + negative CFO + no raise signal.
  Hypothesis (b) REFUTED — cash has declined every year for 3+ years; not seasonal.

  NOTE: numbers are in Vietnamese Dong (VND). Runway calculation is currency-independent
  (ratio of cash to burn rate), so the AVOID verdict holds regardless of FX.
  [TRAINING-FLAG: exact USD equivalent depends on current VND/USD rate ~25,000:1 —
   not in available data; rough estimate $300M cash at $18B/yr burn rate = ~3 months]

Step 4 — CITE:
  "3 months cash runway confirmed by data — cash has declined from 12.4T to 2.8T VND
   over 3 years while CFO remains deeply negative."
  [GROUNDED: cash_trend: 12.4T→6.1T→2.8T VND (2022–2024), cfo_2024=-45T VND]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BUCKET DEFINITIONS (never change these)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVOID(insolvency)        over-levered / loss-eroded, genuinely failing
AVOID(cash_burn)         pre-profit, runway-dependent, no capital lifeline
AVOID(fraud)             earnings can't convert to cash + live news confirms
DISTRESSED-RECOVERABLE   badly stressed but solvent, CFO>0, turning around
WATCH                    stress signals or demoted forensic flag — not terminal
CLEAR                    no material distress or manipulation signal

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT (follow exactly)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<TICKER> — <Company> (<Sector>, $<mcap>B)
BUCKET: <effective_bucket>
RISK: <one line — what would hurt you or why it's safe>
  Fundamentals: <key model reads — Altman Z / Beneish M / Ohlson / accruals / runway>
                with [GROUNDED] or [TRAINING-FLAG] on each notable claim
  Direct-API:  <live events · days-to-cover · recent raise> → CORROBORATES / CONTRADICTS
  WHY: <2–4 sentences; every factual claim must carry a label>
  Not in the data: <what a fresh filing, earnings call, or 10-K could change>

Keep under 280 words. You are not a licensed advisor — say so if asked for personalized advice.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Key loading
# ─────────────────────────────────────────────────────────────────────────────
def _load_key(env_names):
    for name in env_names:
        k = os.environ.get(name)
        if k:
            return k
    for envp in [HERE / ".env", HERE.parent / ".env",
                 Path("/Users/prasadmenon/Claude/StockAffirmProject/stockaffirm/.env")]:
        if envp.exists():
            for line in open(envp):
                line = line.strip()
                for name in env_names:
                    if line.startswith(f"{name}="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

def _anthropic_key(): return _load_key(["ANTHROPIC_API_KEY"])
def _openai_key():    return _load_key(["OPENAI_API_KEY"])


# ─────────────────────────────────────────────────────────────────────────────
# Fibonacci retry HTTP POST
# ─────────────────────────────────────────────────────────────────────────────
def _post(url, headers, body, max_tries=5):
    a, b = 1, 1
    data = json.dumps(body).encode()
    for attempt in range(max_tries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < max_tries - 1:
                time.sleep(a); a, b = b, a + b
                continue
            try:
                return {"error": json.loads(e.read().decode())}
            except Exception:
                return {"error": f"HTTP {e.code}"}
        except Exception as ex:
            if attempt < max_tries - 1:
                time.sleep(a); a, b = b, a + b
            else:
                return {"error": str(ex)}
    return {"error": "exhausted retries"}


# ─────────────────────────────────────────────────────────────────────────────
# Provider calls
# ─────────────────────────────────────────────────────────────────────────────
def _call_anthropic(prompt, model="claude-3-5-sonnet-20241022", max_tokens=1024):
    key = _anthropic_key()
    if not key:
        return None, "no ANTHROPIC_API_KEY"
    resp = _post(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01",
         "content-type": "application/json"},
        {"model": model, "max_tokens": max_tokens,
         "system": SYSTEM_PROMPT,
         "messages": [{"role": "user", "content": prompt}]}
    )
    if "error" in resp:
        return None, str(resp["error"])
    try:
        return resp["content"][0]["text"], None
    except (KeyError, IndexError, TypeError) as e:
        return None, f"parse error: {e} — raw: {str(resp)[:200]}"


def _call_openai(prompt, model="gpt-4o", max_tokens=1024):
    key = _openai_key()
    if not key:
        return None, "no OPENAI_API_KEY"
    resp = _post(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "content-type": "application/json"},
        {"model": model, "max_tokens": max_tokens,
         "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user",   "content": prompt}]}
    )
    if "error" in resp:
        return None, str(resp["error"])
    try:
        return resp["choices"][0]["message"]["content"], None
    except (KeyError, IndexError, TypeError) as e:
        return None, f"parse error: {e} — raw: {str(resp)[:200]}"


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder — passes FULL financials so LLM can investigate any field
# ─────────────────────────────────────────────────────────────────────────────
def _build_prompt(ticker, result, full_hist=None, api_raw=None):
    """
    Build the investigation prompt.
    full_hist: list of dicts from data_loader.full_history() — last 5 years passed
    api_raw:   dict from massive_api.event_scan() — full live signals
    """
    # ---- Screen summary block ----
    screen_block = f"""SCREEN RESULT:
  Ticker:           {ticker.upper()}
  Sector:           {result.get('sector', '?')}
  Market cap:       ${(result.get('market_cap') or 0) / 1e9:.1f}B
  Screen bucket:    {result.get('bucket', '?')}
  Effective bucket: {result.get('effective_bucket', '?')}
  Distress type:    {result.get('distress_type') or 'none'}
  Fraud flag:       {bool(result.get('fraud'))}
  Fraud watchlist:  {bool(result.get('fraud_watchlist'))}
  Verdict:          {result.get('verdict', '?')}
  Note:             {result.get('note') or 'none'}
  Effective reason: {result.get('effective_reason') or 'none'}"""

    # ---- Full financials block (last 5 years — all fields) ----
    if full_hist:
        years = full_hist[:5]   # most-recent 5 years is enough for investigation
        fin_block = "FULL FINANCIAL DATA (last 5 years — check any field to ground your claims):\n"
        fin_block += json.dumps(years, indent=2, default=str)
    else:
        fin_block = "FULL FINANCIAL DATA: not available (screen only)"

    # ---- Live API signals block ----
    if api_raw:
        # include full event lists so LLM can read the actual headlines
        api_block = "LIVE API SIGNALS:\n" + json.dumps({
            "n_news":            api_raw.get("n_news", 0),
            "short_dtc":         api_raw.get("short_days_to_cover"),
            "api_distress":      api_raw.get("api_distress"),
            "api_fraud":         api_raw.get("api_fraud"),
            "api_high_short":    api_raw.get("api_high_short"),
            "api_recent_raise":  api_raw.get("api_recent_raise"),
            "bankruptcy_events": api_raw.get("bankruptcy_events", [])[:5],
            "fraud_events":      api_raw.get("fraud_events", [])[:5],
            "capital_raises":    api_raw.get("capital_raises", [])[:3],
            "lawfirm_spam_count":api_raw.get("lawfirm_spam", 0),
        }, indent=2)
    else:
        api_block = "LIVE API SIGNALS: not available"

    instruction = """
Investigate the notable signals in the screen result.
For each signal: hypothesize → look at the data above → confirm/refute → label every claim.
Then write the final verdict in the standard output format."""

    return f"{screen_block}\n\n{fin_block}\n\n{api_block}\n{instruction}"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
class LLMClient:
    """
    LLM investigation wrapper. Auto-detects provider from available API keys.
    Falls back gracefully (returns None explanation) if no key is present.

    provider: "auto" (default) | "anthropic" | "openai"
    model:    override default model for the chosen provider
    """
    def __init__(self, provider="auto", model=None):
        self.model    = model
        self.provider = provider
        if provider == "auto":
            self.provider = "anthropic" if _anthropic_key() else \
                            "openai"    if _openai_key()    else "none"

    def explain(self, ticker, result, full_hist=None, api_raw=None):
        """
        Return (explanation_str, error_str).
        full_hist: from data_loader.full_history() — passed so LLM can investigate
        api_raw:   from massive_api.event_scan()  — full live signals with headlines
        """
        if self.provider == "none":
            return None, "no LLM key (set ANTHROPIC_API_KEY or OPENAI_API_KEY)"
        prompt = _build_prompt(ticker, result, full_hist=full_hist, api_raw=api_raw)
        if self.provider == "anthropic":
            return _call_anthropic(prompt, model=self.model or "claude-3-5-sonnet-20241022")
        if self.provider == "openai":
            return _call_openai(prompt, model=self.model or "gpt-4o")
        return None, f"unknown provider: {self.provider}"

    @property
    def active(self):
        return self.provider not in ("none", None)

    def __repr__(self):
        return f"LLMClient(provider={self.provider}, model={self.model or 'default'})"


# ─────────────────────────────────────────────────────────────────────────────
# CLI test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(HERE))
    from calibrate import process_one
    from data_loader import load_fundamentals, full_history
    from massive_api import event_scan

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Running full investigation pipeline for {ticker}...\n")

    result  = process_one(ticker, write=False)
    fund    = load_fundamentals(ticker)
    hist    = full_history(fund) if fund else None
    api_raw = event_scan(ticker)

    print(f"  screen={result['bucket']}  effective={result['effective_bucket']}  verdict={result['verdict']}")
    print(f"  {len(hist) if hist else 0} years of financials · {api_raw['n_news']} news articles\n")

    client = LLMClient()
    print(f"  LLM provider: {client}")
    if client.active:
        print("  Calling LLM for grounded investigation...\n")
        explanation, err = client.explain(ticker, result, full_hist=hist, api_raw=api_raw)
        if err:
            print(f"  ERROR: {err}")
        else:
            print(explanation)
    else:
        print("  No LLM key — set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env")
