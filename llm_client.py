#!/usr/bin/env python3
"""
llm_client.py -- LLM investigation + verdict layer for the distress/fraud pipeline.

The LLM is the PRIMARY analyst. It receives the full multi-year financial data and
the Python screen signals, investigates every notable signal, and issues its OWN
bucket verdict (AVOID / WATCH / CLEAR / TRAINING-FLAG). The Python screen is
secondary evidence — it feeds the investigation but does not override the verdict.

Investigation loop per signal:
  1. HYPOTHESIZE (training OK here) → 2-3 candidate explanations
  2. LOOK UP     → specific fields in the full financials
  3. EVALUATE    → confirm / refute each hypothesis
  4. LABEL       → [GROUNDED: field=value, fy=YYYY]  or  [TRAINING-FLAG: hypothesis]

Returns structured JSON (not prose) so the output is parseable:
  {
    "bucket":          "AVOID(insolvency)" | "TRAINING-FLAG(distress)" | ...,
    "confidence":      "high" | "medium" | "low",
    "one_line_risk":   "...",
    "grounded_claims": [...],
    "training_flags":  [...],
    "unresolved":      [...],
    "narrative":       "2-4 sentence WHY..."
  }

Provider auto-detection from env:
  ANTHROPIC_API_KEY  → Anthropic Claude (default, recommended)
  OPENAI_API_KEY     → OpenAI GPT-4o

Key lookup: env var → .env next to this file → stockaffirm/.env

Usage:
  from llm_client import LLMClient
  client = LLMClient()
  verdict, err = client.explain(ticker, result, full_hist=hist, api_raw=event_scan_output)
  # verdict is a dict with bucket, grounded_claims, training_flags, etc.

  python3 llm_client.py AAPL      # live test with real data
"""
import os, json, re, time, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).parent

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — investigation loop + worked examples + JSON output schema
# Concrete examples are the single best anti-hallucination technique.
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are the Distress & Fraud Analyst investigator. You are the PRIMARY analyst.
You receive:
  1. The Python screen output (bucket, model scores, flags) — this is EVIDENCE, not your verdict
  2. The FULL multi-year financial data for the company (every field, last 5 years)
  3. Live API signals (news events, short interest, capital raises)

Your job: investigate the data, form your OWN verdict, return it as structured JSON.
The Python screen is the starting hypothesis — you confirm, refute, or escalate it.

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
  ✓ A [TRAINING-FLAG] in grounded_claims is valuable signal — it is never a verdict alone
  ✓ "I cannot explain this from the available data" is a correct and useful answer
  ✓ You MAY disagree with the Python screen bucket — say why in the narrative

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKED EXAMPLE 1 — negative equity, grey-zone Altman (AAPL-type)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Screen output:
  total_equity = NEGATIVE   Altman Z'' (book) = 2.31 (grey)   Altman Z (market) = 11.75
  Python screen bucket: CLEAR

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

Step 4 — grounded_claims entry:
  claim: "Equity is negative due to capital return policy, not losses"
  [GROUNDED: treasury_stock_2024=-$172B, retained_earnings_2024=-$19B]

  claim: "Altman Z'' (book) grey zone is a buyback artifact — market-cap Z=11.75 confirms no distress"
  [GROUNDED: total_equity_book=-$62B (buyback-driven), market_cap_Z=11.75]

Output bucket: CLEAR (agree with Python, grounded from data)
Output confidence: high

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKED EXAMPLE 2 — current ratio < 1.0 (AAPL-type)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Screen output: current_ratio = 0.89, Python bucket: CLEAR

Step 1 — HYPOTHESIZE:
  (a) liquidity stress: can't cover near-term obligations
  (b) supplier-float model: large AP from favorable payment terms offsets current assets
  (c) deferred-revenue heavy: high deferred rev inflates current liabilities

Step 3 — EVALUATE:
  cfo_2024 = +108,000,000,000  (CFO $108B dwarfs any shortfall) → hypothesis (a) REFUTED
  accounts_payable_2024 = 62,000,000,000  (large AP) → hypothesis (b) partially supported

Output bucket: CLEAR
training_flags entry: {
  "concern": "sub-1.0 current ratio may reflect supplier payment float (AP=$62B)",
  "why_ungrounded": "supply chain payment terms not in financials",
  "investigate": "10-K supply chain notes, Days Payable Outstanding trend",
  "urgency": "low"
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKED EXAMPLE 3 — genuine distress, one aspect can't be grounded (VFS-type)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Screen output:
  Ohlson P(default) = 71.7%   runway = 3mo   CFO = -45T VND   Python bucket: AVOID(insolvency)

Evaluate:
  cash_2024 = 2.8T VND, cash_2023 = 6.1T VND, cash_2022 = 12.4T VND  ← 3yr declining trend
  cfo_2024 = -45T VND (negative operating cash flow)
  api_recent_raise = false (no recent equity raise in news)
  → hypothesis (a) genuine cash burn CONFIRMED; hypothesis (b) seasonal REFUTED

grounded_claims: [{
  "claim": "3 months cash runway — cash declined from 12.4T to 2.8T VND over 3 years while CFO negative",
  "field": "cash_and_equivalents + operating_cash_flow",
  "value": "2.8T VND cash, -45T VND CFO",
  "fy": 2024
}]

training_flags: [{
  "concern": "USD equivalent uncertain — VND/USD rate ~25,000:1 implies ~$300M cash vs ~$1.8B/yr burn",
  "why_ungrounded": "FX rate not in available data",
  "investigate": "current VND/USD rate, latest press release on cash position",
  "urgency": "low"
}]

Output bucket: AVOID(insolvency)
Output confidence: high

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BUCKET DEFINITIONS — choose the best fit based on your investigation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GROUNDED buckets (you confirmed from data — use when you have solid evidence):
  AVOID(insolvency)          over-levered / loss-eroded, genuinely failing
  AVOID(cash_burn)           pre-profit, runway-dependent, no capital lifeline
  AVOID(fraud)               earnings can't convert to cash + live news confirms
  DISTRESSED-RECOVERABLE     badly stressed but solvent, CFO>0, turning around
  WATCH                      stress signals or demoted forensic flag — not terminal
  CLEAR                      no material distress or manipulation signal

TRAINING-FLAG buckets (use when you suspect something but cannot fully ground it):
  TRAINING-FLAG(distress)    suspected insolvency/cash-burn risk — data insufficient to confirm
  TRAINING-FLAG(fraud)       suspected earnings manipulation — patterns suggestive, not conclusive
  TRAINING-FLAG(watch)       concerning pattern from training knowledge — warrants investigation

Use TRAINING-FLAG buckets when:
  - Python flagged something but you cannot find data to confirm OR refute it
  - Your training suggests risk that the available financials don't surface clearly
  - There is conflicting evidence you cannot resolve from the data provided
  - The Python bucket is AVOID but you can only partially ground it

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — return ONLY the JSON object below (no prose wrapper, no markdown fences)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "bucket": "<one of the bucket values listed above>",
  "confidence": "high|medium|low",
  "one_line_risk": "<what would hurt the investor, or why it is safe — one sentence>",
  "grounded_claims": [
    {
      "claim": "<factual statement confirmed from data>",
      "field": "<data field name(s)>",
      "value": "<actual value(s) from data>",
      "fy": <fiscal year as integer, e.g. 2024>
    }
  ],
  "training_flags": [
    {
      "concern": "<what training knowledge suggests>",
      "why_ungrounded": "<why you cannot confirm from available data>",
      "investigate": "<what to check: 10-K section, filing type, news search>",
      "urgency": "high|medium|low"
    }
  ],
  "unresolved": [
    {
      "screen_flag": "<Python flag that fired — e.g. beneish_m_elevated>",
      "explanation": "<why you cannot explain it from available data or training>",
      "next_step": "<where to look>"
    }
  ],
  "narrative": "<2-4 sentences connecting the fundamentals to the live signals; explain the bucket choice>"
}

confidence rules:
  "high"   — all major claims grounded in data; TRAINING-FLAG items are minor or zero
  "medium" — some claims grounded; one or more significant TRAINING-FLAG items present
  "low"    — primarily training-flagged; limited data confirmation; Python screen is the better primary signal

Return ONLY the JSON. No other text before or after it.
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
# JSON extraction — handles direct JSON, code-fenced JSON, or embedded JSON
# ─────────────────────────────────────────────────────────────────────────────
def _parse_llm_json(text):
    """
    Extract and parse the JSON verdict dict from LLM response text.
    Tries three strategies: direct parse, code-fence extraction, first-{-to-last-}.
    Returns dict on success, None on failure.
    """
    if not text:
        return None
    # 1. Direct parse (ideal — model followed instructions exactly)
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # 2. JSON inside ```json ... ``` or ``` ... ``` fences
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 3. First { to last } in the response
    start = text.find('{')
    end   = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Provider calls — return (dict_or_None, error_str_or_None)
# ─────────────────────────────────────────────────────────────────────────────
def _call_anthropic(prompt, model="claude-3-5-sonnet-20241022", max_tokens=2000):
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
        text = resp["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        return None, f"parse error: {e} — raw: {str(resp)[:200]}"
    verdict = _parse_llm_json(text)
    if verdict is None:
        # Fallback: return raw text wrapped in a minimal dict so caller still gets something
        return {"bucket": "TRAINING-FLAG(watch)", "confidence": "low",
                "one_line_risk": "LLM returned unparseable response",
                "grounded_claims": [], "training_flags": [], "unresolved": [],
                "narrative": text[:500]}, None
    return verdict, None


def _call_openai(prompt, model="gpt-4o", max_tokens=2000):
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
        text = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        return None, f"parse error: {e} — raw: {str(resp)[:200]}"
    verdict = _parse_llm_json(text)
    if verdict is None:
        return {"bucket": "TRAINING-FLAG(watch)", "confidence": "low",
                "one_line_risk": "LLM returned unparseable response",
                "grounded_claims": [], "training_flags": [], "unresolved": [],
                "narrative": text[:500]}, None
    return verdict, None


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder — passes FULL financials so LLM can investigate any field
# ─────────────────────────────────────────────────────────────────────────────
def _build_prompt(ticker, result, full_hist=None, api_raw=None):
    """
    Build the investigation prompt.
    full_hist: list of dicts from data_loader.full_history() — last 5 years passed
    api_raw:   dict from massive_api.event_scan() — full live signals
    """
    # ---- Python screen evidence block (secondary — starting hypothesis) ----
    screen_block = f"""PYTHON SCREEN EVIDENCE (starting hypothesis — investigate and reach your own verdict):
  Ticker:           {ticker.upper()}
  Sector:           {result.get('sector', '?')}
  Market cap:       ${(result.get('market_cap') or 0) / 1e9:.1f}B
  Screen bucket:    {result.get('bucket', '?')}
  API overlay:      {result.get('effective_bucket', '?')}
  Distress type:    {result.get('distress_type') or 'none'}
  Fraud flag:       {bool(result.get('fraud'))}
  Fraud watchlist:  {bool(result.get('fraud_watchlist'))}
  Calibration verdict: {result.get('verdict', '?')}
  Note:             {result.get('note') or 'none'}
  Effective reason: {result.get('effective_reason') or 'none'}

Investigate the notable signals above. Confirm or refute each one from the data below.
You may disagree with the Python screen bucket — explain why in the narrative."""

    # ---- Full financials block (last 5 years — all fields) ----
    if full_hist:
        years = full_hist[:5]   # most-recent 5 years
        fin_block = "FULL FINANCIAL DATA (last 5 years — use this to ground every claim):\n"
        fin_block += json.dumps(years, indent=2, default=str)
    else:
        fin_block = "FULL FINANCIAL DATA: not available — base verdict on Python screen + live signals only"

    # ---- Live API signals block ----
    if api_raw:
        api_block = "LIVE API SIGNALS:\n" + json.dumps({
            "n_news":            api_raw.get("n_news", 0),
            "n_news_massive":    api_raw.get("n_news_massive", 0),
            "n_news_av":         api_raw.get("n_news_av", 0),
            "av_avg_sentiment":  api_raw.get("av_avg_sentiment"),
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
Investigate. Return ONLY the JSON verdict object. No prose before or after it."""

    return f"{screen_block}\n\n{fin_block}\n\n{api_block}\n{instruction}"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
class LLMClient:
    """
    LLM investigation + verdict wrapper. Auto-detects provider from available API keys.
    Falls back gracefully (returns None verdict) if no key is present.

    provider: "auto" (default) | "anthropic" | "openai"
    model:    override default model for the chosen provider

    Returns: (verdict_dict_or_None, error_str_or_None)

    verdict_dict keys:
      bucket          — LLM's verdict (primary effective_bucket)
      confidence      — "high" | "medium" | "low"
      one_line_risk   — one sentence
      grounded_claims — list of {claim, field, value, fy}
      training_flags  — list of {concern, why_ungrounded, investigate, urgency}
      unresolved      — list of {screen_flag, explanation, next_step}
      narrative       — 2-4 sentence WHY
    """
    def __init__(self, provider="auto", model=None):
        self.model    = model
        self.provider = provider
        if provider == "auto":
            self.provider = "anthropic" if _anthropic_key() else \
                            "openai"    if _openai_key()    else "none"

    def explain(self, ticker, result, full_hist=None, api_raw=None):
        """
        Investigate and return (verdict_dict_or_None, error_str_or_None).
        full_hist: from data_loader.full_history() — passed so LLM can investigate
        api_raw:   from massive_api.event_scan()  — full live signals with headlines

        On success: (dict with bucket/grounded_claims/training_flags/unresolved/narrative, None)
        On failure: (None, error_str)
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

    print(f"  Python screen:   {result['bucket']}")
    print(f"  Python effective:{result['effective_bucket']}  verdict={result['verdict']}")
    print(f"  {len(hist) if hist else 0} years of financials · {api_raw['n_news']} news articles\n")

    client = LLMClient()
    print(f"  LLM provider: {client}")
    if client.active:
        print("  Calling LLM for grounded investigation...\n")
        verdict, err = client.explain(ticker, result, full_hist=hist, api_raw=api_raw)
        if err and verdict is None:
            print(f"  ERROR: {err}")
        elif verdict:
            print(f"  LLM bucket:     {verdict.get('bucket')}  (confidence: {verdict.get('confidence')})")
            print(f"  One-line risk:  {verdict.get('one_line_risk')}")
            print(f"\n  Grounded claims ({len(verdict.get('grounded_claims', []))}):")
            for c in verdict.get("grounded_claims", []):
                print(f"    [{c.get('fy')}] {c.get('claim')} — {c.get('field')}={c.get('value')}")
            print(f"\n  Training flags ({len(verdict.get('training_flags', []))}):")
            for f in verdict.get("training_flags", []):
                print(f"    [{f.get('urgency','?').upper()}] {f.get('concern')}")
                print(f"          → investigate: {f.get('investigate')}")
            print(f"\n  Unresolved ({len(verdict.get('unresolved', []))}):")
            for u in verdict.get("unresolved", []):
                print(f"    {u.get('screen_flag')}: {u.get('explanation')}")
                print(f"          → {u.get('next_step')}")
            print(f"\n  Narrative:\n  {verdict.get('narrative')}")
    else:
        print("  No LLM key — set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env")
