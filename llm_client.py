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
GROUNDING SOURCES — every claim must name its source
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  "av_financial"    Data came from Alpha Vantage financial statements (income, balance, CF).
                    This is HARD data — cite field name + year.
  "calculated"      Computed from av_financial (e.g. DSRI = recv/rev ratio; runway = cash/burn).
                    Show the formula and the numbers.
  "av_price_data"   From the PRICE HISTORY block (TIME_SERIES_MONTHLY_ADJUSTED).
                    Cite the specific date and price value.
  "massive_news"    Confirmed by a Massive API article in the ARTICLE CORPUS.
                    Cite the headline title + date.
  "av_news"         Confirmed by an AV NEWS_SENTIMENT article in the ARTICLE CORPUS.
                    Cite the headline title + date.
  "training_only"   Your training knowledge — NOT confirmed by any provided data or news.
                    This is the ONLY valid source for a training_flag, and it means you
                    cannot assert the claim as fact.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INVESTIGATION LOOP (run for every notable signal or anomaly)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 1 — HYPOTHESIZE: state what training tells you this pattern could mean
           (list 2–3 candidate explanations, most likely first)
Step 2 — LOOK UP: name the specific fields in the data you need to check.
           For FINANCIAL claims: look in the FULL FINANCIAL DATA block.
           For PRICE claims: look in the PRICE HISTORY block (av_price_data).
           For BUSINESS claims (contracts, partnerships, strategy, market position):
             Read the ARTICLE CORPUS first — discover what is actually there.
             If a matching article exists → grounding_source = "massive_news" or "av_news".
             If NO matching article → grounding_source = "training_only" → training_flag.
Step 3 — EVALUATE: does the data confirm, refute, or not speak to the hypothesis?
           If refuted → try the next candidate. If nothing fits → say so explicitly.
Step 4 — LABEL every claim with its grounding_source.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEWS ANALYSIS — read the complete article corpus, discover freely
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You have been provided with the COMPLETE focused article corpus for this ticker
(ALL focused articles, not a filtered sample). Read them all before forming any
view on the business, strategy, contracts, or events.

Do NOT search for expected terms — discover what is actually there organically.
The most important information may be something you didn't know to look for:
a new partnership, a regulatory action, a product launch, a management change,
or a contract signed after your training cutoff.

After reading the corpus:
  - If a claim is supported by a specific article → grounding_source = "massive_news"
    or "av_news"; cite the headline title and date exactly.
  - If a claim is NOT supported by any article you read → grounding_source =
    "training_only"; put it in training_flags with how_to_ground pointing to a
    specific search (SEC EDGAR 8-K, 10-K §Revenue Recognition, etc.)

RULES (never break these):
  ✗ Never assert a business/strategy fact from training without checking the article corpus
  ✗ Never use training knowledge as the sole source for a factual claim
  ✓ Revenue, CFO, assets, debt, equity — these come from av_financial (hard data)
  ✓ Stock price moves: use av_price_data if PRICE HISTORY is provided; else training_only
  ✓ If data refutes your first hypothesis, say "hypothesis (a) REFUTED — checking (b)"
  ✓ Multi-year trends are stronger evidence than single-year readings
  ✓ "I cannot find grounding for this in the provided data or articles" is correct
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
      "claim": "<factual statement confirmed from data or news>",
      "grounding_source": "av_financial|calculated|massive_news|av_news",
      "field": "<data field name(s), or headline title if news-grounded>",
      "value": "<actual value(s) — number from financials, or headline date if news>",
      "fy": <fiscal year as integer if financial, null if news-grounded>
    }
  ],
  "training_flags": [
    {
      "concern": "<what training knowledge suggests — be specific>",
      "grounding_source": "training_only",
      "why_ungrounded": "<exactly why: not in financials / no matching headline found / price data not provided>",
      "how_to_ground": "<specific query: 'search SEC EDGAR 8-K for X' / '10-K §Revenue Recognition' / 'news search: [exact query]'>",
      "investigate": "<what to check>",
      "urgency": "high|medium|low"
    }
  ],
  "unresolved": [
    {
      "screen_flag": "<Python flag that fired — e.g. beneish_growth_artifact, revenue_decline_2024>",
      "explanation": "<why you cannot explain it from available data or headlines>",
      "next_step": "<specific where to look>"
    }
  ],
  "narrative": "<2-4 sentences connecting the fundamentals to the live signals; explain the bucket choice; cite grounding sources>"
}

confidence rules:
  "high"   — all major claims are av_financial / calculated / news-grounded; training_only items minor or zero
  "medium" — some claims grounded; one or more significant training_only items present
  "low"    — primarily training_only; limited data confirmation; Python screen is the better primary signal

SELF-CHECK before returning:
  1. Every grounded_claim has a grounding_source that is NOT "training_only"
  2. Every training_flag has grounding_source = "training_only" AND a specific how_to_ground
  3. No business/strategy claim is in grounded_claims with grounding_source = "training_only"
     (training knowledge about strategy → training_flags, never grounded_claims)
  4. Stock price moves: if PRICE HISTORY is provided → av_price_data (grounded).
     If no price history block → training_only (put in training_flags).
     Never state a specific price move without citing a specific date from price data.

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
def _build_prompt(ticker, result, full_hist=None, api_raw=None, price_hist=None):
    """
    Build the investigation prompt.
    full_hist:  list of dicts from data_loader.full_history() — last 5 years passed
    api_raw:    dict from massive_api.event_scan() — full live signals with article corpus
    price_hist: list of dicts from data_loader.price_history() — monthly price history
                grounding_source = "av_price_data"; cite date + adj_close value
    """
    def _f(v, d=3):
        """Safe float formatter — returns 'n/a' for None."""
        return "n/a" if v is None else f"{v:.{d}f}"

    # ---- Python screen evidence block (secondary — starting hypothesis) ----
    gs        = result.get("growth_stage", "UNKNOWN")
    cagr_3y   = result.get("growth_cagr_3y")
    ben_comp  = result.get("beneish_components") or {}
    b_artifact= result.get("beneish_growth_artifact", False)
    cagr_str  = f", 3y CAGR {cagr_3y*100:.0f}%" if cagr_3y is not None else ""

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

GROWTH STAGE: {gs}{cagr_str}
  {"⚠ HIGH-GROWTH / PRE-SCALE: Altman Z'', Beneish M, and Ohlson were calibrated on MATURE companies." if gs in ("HIGH-GROWTH", "HIGH-GROWTH-PRE-SCALE") else "Distress models are appropriate for this growth stage."}
  {"Use growth-stage context when interpreting model flags — do NOT suppress them entirely, but weigh them against runway, capital access, and revenue trajectory." if gs in ("HIGH-GROWTH", "HIGH-GROWTH-PRE-SCALE", "MEDIUM-GROWTH") else ""}

BENEISH M COMPONENTS (calculated from AV financials — grounding_source=calculated):
  DSRI={_f(ben_comp.get('DSRI'))}  GMI={_f(ben_comp.get('GMI'))}  AQI={_f(ben_comp.get('AQI'))}  SGI={_f(ben_comp.get('SGI'))}
  DEPI={_f(ben_comp.get('DEPI'))}  SGAI={_f(ben_comp.get('SGAI'))}  LVGI={_f(ben_comp.get('LVGI'))}  TATA={_f(ben_comp.get('TATA'), 4)}
  {"⚠ beneish_growth_artifact=True: DSRI={} + SGI={} are the drivers; TATA={} ≤ 0 is anti-manipulation. Investigate receivables spike in data, not as fraud signal.".format(_f(ben_comp.get('DSRI')), _f(ben_comp.get('SGI')), _f(ben_comp.get('TATA'),4)) if b_artifact else "Investigate which components drove the M-score."}

Investigate the notable signals above. Confirm or refute each one from the data below.
You may disagree with the Python screen bucket — explain why in the narrative.
REMEMBER: search RECENT FOCUSED HEADLINES before writing any business/strategy claim."""

    # ---- Full financials block (last 5 years — all fields) ----
    if full_hist:
        years = full_hist[:5]   # most-recent 5 years
        fin_block = "FULL FINANCIAL DATA (last 5 years — use this to ground every claim):\n"
        fin_block += json.dumps(years, indent=2, default=str)
    else:
        fin_block = "FULL FINANCIAL DATA: not available — base verdict on Python screen + live signals only"

    # ---- Price history block (monthly, 2 years) ----
    if price_hist:
        price_block = (
            f"PRICE HISTORY (monthly adj_close, newest first — grounding_source='av_price_data'):\n"
            f"[{len(price_hist)} months — cite date + adj_close when making any price-move claim]\n"
        )
        for p in price_hist:
            ac = p.get("adj_close")
            price_block += f"  {p.get('date','?')}  adj_close=${ac:.2f}\n" if ac is not None else \
                           f"  {p.get('date','?')}  adj_close=n/a\n"
    else:
        price_block = (
            "PRICE HISTORY: not available — stock price move claims are training_only; "
            "put them in training_flags, not grounded_claims."
        )

    # ---- Live API signals block ----
    if api_raw:
        # Use all_focused_articles if available (new); fall back to recent_focused_headlines (compat)
        articles = api_raw.get("all_focused_articles") or api_raw.get("recent_focused_headlines", [])
        n_focused = api_raw.get("n_focused_articles", len(articles))
        api_block = "LIVE API SIGNALS:\n" + json.dumps({
            "n_news":            api_raw.get("n_news", 0),
            "n_news_massive":    api_raw.get("n_news_massive", 0),
            "n_news_av":         api_raw.get("n_news_av", 0),
            "n_focused_articles":n_focused,
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
        if articles:
            # Pass the COMPLETE focused article corpus — LLM reads all, discovers freely
            api_block += (
                f"\n\nARTICLE CORPUS (complete — {len(articles)} focused articles):\n"
                f"Read ALL articles before forming any business/strategy/contract view.\n"
                f"Do NOT search for expected terms — discover what is there organically.\n"
                f"If a claim is supported by an article → cite title+date as grounding_source.\n"
                f"If no article supports a claim → training_only → training_flags.\n\n"
            )
            for a in articles:
                src  = a.get("source", "?")
                date = a.get("date", "")
                title= a.get("title", "")
                desc = (a.get("desc") or "").strip()
                sent = a.get("sentiment")
                sent_str = f"  [sentiment={sent:.2f}]" if sent is not None else ""
                api_block += f"  [{src}|{date}]{sent_str} {title}\n"
                if desc:
                    # Indent description under title for readability
                    api_block += f"    {desc}\n"
    else:
        api_block = "LIVE API SIGNALS: not available (Python screen only)"

    instruction = """
Investigate every notable signal. Read the full article corpus before any business/strategy claim.
Use av_price_data for price moves if the PRICE HISTORY block is present.
Return ONLY the JSON verdict object. No prose before or after it."""

    return f"{screen_block}\n\n{fin_block}\n\n{price_block}\n\n{api_block}\n{instruction}"


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

    def explain(self, ticker, result, full_hist=None, api_raw=None, price_hist=None):
        """
        Investigate and return (verdict_dict_or_None, error_str_or_None).
        full_hist:  from data_loader.full_history()    — 5-year financials for grounding
        api_raw:    from massive_api.event_scan()      — full article corpus + live signals
        price_hist: from data_loader.price_history()   — monthly price history
                    (grounding_source="av_price_data"; grounds stock price move claims)

        On success: (dict with bucket/grounded_claims/training_flags/unresolved/narrative, None)
        On failure: (None, error_str)
        """
        if self.provider == "none":
            return None, "no LLM key (set ANTHROPIC_API_KEY or OPENAI_API_KEY)"
        prompt = _build_prompt(ticker, result, full_hist=full_hist, api_raw=api_raw,
                               price_hist=price_hist)
        if self.provider == "anthropic":
            return _call_anthropic(prompt, model=self.model or "claude-3-5-sonnet-20241022",
                                   max_tokens=3000)   # bumped for larger article corpus
        if self.provider == "openai":
            return _call_openai(prompt, model=self.model or "gpt-4o", max_tokens=3000)
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
    from data_loader import load_fundamentals, full_history, price_history
    from massive_api import event_scan

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Running full investigation pipeline for {ticker}...\n")

    result     = process_one(ticker, write=False)
    fund       = load_fundamentals(ticker)
    hist       = full_history(fund) if fund else None
    api_raw    = event_scan(ticker)
    price_hist = price_history(ticker, months=24)

    n_focused = api_raw.get("n_focused_articles", len(api_raw.get("all_focused_articles", [])))
    print(f"  Python screen:   {result['bucket']}")
    print(f"  Python effective:{result['effective_bucket']}  verdict={result['verdict']}")
    print(f"  {len(hist) if hist else 0} years of financials · {api_raw['n_news']} news articles "
          f"({n_focused} focused) · {len(price_hist)} months of price history\n")

    client = LLMClient()
    print(f"  LLM provider: {client}")
    if client.active:
        print("  Calling LLM for grounded investigation...\n")
        verdict, err = client.explain(ticker, result, full_hist=hist, api_raw=api_raw,
                                      price_hist=price_hist)
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
