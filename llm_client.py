#!/usr/bin/env python3
"""
llm_client.py -- LLM explanation layer for the distress/fraud pipeline.

Calls an external LLM (Anthropic Claude or OpenAI) with the structured
screen + API output and returns a natural-language verdict.

The Python pipeline (Layer 1 + Layer 2) is 100% deterministic — no LLM needed
for the bucket. The LLM only adds the plain-English explanation + calibration
judgment. This file is optional: the API server works without it (returns
structured JSON only when no LLM key is configured).

Provider auto-detection from env:
  ANTHROPIC_API_KEY  → Anthropic Claude (default, recommended)
  OPENAI_API_KEY     → OpenAI GPT-4o

Key lookup order: env var → .env next to this file → stockaffirm/.env

Usage:
  from llm_client import LLMClient
  client = LLMClient()
  explanation = client.explain(ticker, process_result, screen_detail=None)

  python3 llm_client.py AAPL      # test explanation for one ticker
"""
import os, json, time, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).parent

# ---- condensed system prompt (brain docs distilled to ~600 tokens) ---------
SYSTEM_PROMPT = """You are the Distress & Fraud Analyst. You receive structured output
from a 7-model Python screen (Altman Z'', Beneish M, Ohlson O, Sloan accruals, Montier C,
liquidity/leverage/cash-runway) cross-checked against live Massive API signals
(news events, short interest, capital raises). Your job is to translate this into a
concise, plain-English verdict.

BUCKET MEANINGS:
- AVOID(insolvency): over-levered / loss-eroded operating business genuinely failing
- AVOID(cash_burn): pre-profit, burning cash, runway-dependent, no lifeline
- AVOID(fraud): earnings can't convert to cash + live news/SEC/short-seller confirms
- DISTRESSED-RECOVERABLE: badly stressed but solvent, CFO>0, turning around
- WATCH: stress signals or demoted forensic flag — not terminal
- CLEAR: no material distress or manipulation signal

VERDICT FORMAT (always follow this exactly):
<TICKER> — <Company> (<Sector>, $<mcap>)
BUCKET: <effective_bucket>
RISK: <one line — what would hurt you or why it's safe>
  Fundamentals: <key model reads — Altman / Beneish / Ohlson / accruals / runway / leverage>
  Direct-API: <live events · days-to-cover · recent raise> → CORROBORATES or CONTRADICTS
  WHY: <2-4 sentences tying fundamentals to live evidence>
  Not in the data: <what a fresh filing/event could change>

RULES:
- Lead with the effective_bucket (screen adjusted by API overlay), not the raw screen_bucket
- Distinguish insolvency vs cash_burn; fraud vs forensic-watchlist
- A fundamentals-only fraud flag is "investigate", not a verdict — confirm with news
- Short interest alone never flags — it only corroborates
- You are not a licensed advisor; provide risk analysis, not personalized advice
- Keep it under 200 words
"""

# ---- key loading -----------------------------------------------------------
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

def _anthropic_key():
    return _load_key(["ANTHROPIC_API_KEY"])

def _openai_key():
    return _load_key(["OPENAI_API_KEY"])


# ---- fibonacci retry HTTP --------------------------------------------------
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
                err = json.loads(e.read().decode())
                return {"error": err}
            except Exception:
                return {"error": f"HTTP {e.code}"}
        except Exception as ex:
            if attempt < max_tries - 1:
                time.sleep(a); a, b = b, a + b
            else:
                return {"error": str(ex)}
    return {"error": "exhausted retries"}


# ---- LLM providers ---------------------------------------------------------
def _call_anthropic(prompt, model="claude-3-5-sonnet-20241022", max_tokens=512):
    key = _anthropic_key()
    if not key:
        return None, "no ANTHROPIC_API_KEY"
    resp = _post(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key,
         "anthropic-version": "2023-06-01",
         "content-type": "application/json"},
        {"model": model,
         "max_tokens": max_tokens,
         "system": SYSTEM_PROMPT,
         "messages": [{"role": "user", "content": prompt}]}
    )
    if "error" in resp:
        return None, str(resp["error"])
    try:
        text = resp["content"][0]["text"]
        return text, None
    except (KeyError, IndexError, TypeError) as e:
        return None, f"parse error: {e} — raw: {str(resp)[:200]}"


def _call_openai(prompt, model="gpt-4o", max_tokens=512):
    key = _openai_key()
    if not key:
        return None, "no OPENAI_API_KEY"
    resp = _post(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {key}",
         "content-type": "application/json"},
        {"model": model,
         "max_tokens": max_tokens,
         "messages": [
             {"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user",   "content": prompt}
         ]}
    )
    if "error" in resp:
        return None, str(resp["error"])
    try:
        text = resp["choices"][0]["message"]["content"]
        return text, None
    except (KeyError, IndexError, TypeError) as e:
        return None, f"parse error: {e} — raw: {str(resp)[:200]}"


# ---- prompt builder --------------------------------------------------------
def _build_prompt(ticker, result, screen_detail=None):
    """Build the user message from the pipeline's structured output."""
    r = result
    lines = [
        f"Ticker: {ticker.upper()}",
        f"Sector: {r.get('sector','?')}  Market cap: ${(r.get('market_cap') or 0)/1e9:.1f}B",
        f"",
        f"SCREEN BUCKET:    {r.get('bucket','?')}",
        f"EFFECTIVE BUCKET: {r.get('effective_bucket','?')}  (screen + API overlay)",
        f"Distress type:    {r.get('distress_type') or 'none'}",
        f"Fraud flag:       {bool(r.get('fraud'))}   Watchlist: {bool(r.get('fraud_watchlist'))}",
        f"",
        f"CALIBRATION VERDICT: {r.get('verdict','?')}",
        f"  API distress events: {r.get('n_bk_events',0)}  fraud events: {r.get('n_fraud_events',0)}",
        f"  Short days-to-cover: {r.get('short_dtc','n/a')}  High-short flag: {bool(r.get('api_high_short'))}",
        f"  Recent capital raise: {bool(r.get('api_recent_raise'))}",
        f"  Note: {r.get('note','') or 'none'}",
        f"  Effective reason: {r.get('effective_reason','') or 'none'}",
    ]
    if screen_detail:
        lines += ["", "RAW SCREEN OUTPUT:", screen_detail]
    lines += ["", "Produce the verdict in the standard format."]
    return "\n".join(lines)


# ---- public API ------------------------------------------------------------
class LLMClient:
    """
    LLM explanation wrapper. Auto-detects provider from available API keys.
    Falls back gracefully if no key is present (returns None explanation).

    provider: "auto" (default) | "anthropic" | "openai"
    model: override the default model for the chosen provider
    """
    def __init__(self, provider="auto", model=None):
        self.model    = model
        self.provider = provider
        if provider == "auto":
            # prefer Anthropic; fall back to OpenAI
            self.provider = "anthropic" if _anthropic_key() else \
                            "openai"    if _openai_key()    else "none"

    def explain(self, ticker, result, screen_detail=None):
        """
        Return (explanation_str, error_str). explanation is None on failure.
        screen_detail: optional raw distress_screen output string for richer context.
        """
        if self.provider == "none":
            return None, "no LLM API key configured (ANTHROPIC_API_KEY or OPENAI_API_KEY)"
        prompt = _build_prompt(ticker, result, screen_detail)
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


# ---- CLI test --------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(HERE))
    from calibrate import process_one

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Running pipeline for {ticker}...")
    result = process_one(ticker, write=False)
    print(f"  bucket={result['bucket']}  effective={result['effective_bucket']}  verdict={result['verdict']}")

    client = LLMClient()
    print(f"  LLM provider: {client}")
    if client.active:
        print("  Calling LLM for explanation...")
        explanation, err = client.explain(ticker, result)
        if err:
            print(f"  ERROR: {err}")
        else:
            print("\n" + explanation)
    else:
        print("  No LLM key — explanation skipped. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")
