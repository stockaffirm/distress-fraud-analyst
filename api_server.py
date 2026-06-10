#!/usr/bin/env python3
"""
api_server.py -- HTTP API server for the distress & fraud analyst.

MODE 3: Automated trigger pipeline. Run on any server, call from any language,
trigger from any scheduler. The Python engine (Layer 1 + Layer 2) runs
deterministically; an optional LLM call (via ANTHROPIC_API_KEY / OPENAI_API_KEY)
adds the natural-language explanation.

ENDPOINTS:
  GET  /health                    -> {"status":"ok", "llm_active": bool, "version":"..."}
  POST /analyze                   -> analyze one ticker
  POST /analyze/batch             -> analyze multiple tickers in parallel
  GET  /universe/summary          -> calibrated findings summary (from CALIBRATED_FINDINGS.md)

POST /analyze body:
  {
    "ticker":  "VFS",
    "explain": true,              // call LLM for plain-English verdict (default: false)
    "model":   "claude-3-5-sonnet-20241022"  // optional LLM model override
  }

POST /analyze/batch body:
  {
    "tickers": ["AAPL", "VFS", "TSLA"],
    "explain": false,
    "max_workers": 8              // parallel threads (default: 4, max: 32)
  }

Response schema (single ticker):
  {
    "ticker":           "VFS",
    "effective_bucket": "AVOID(insolvency)",   // LLM verdict when explain=true; Python screen when explain=false
    "effective_source": "llm",                 // "llm" or "screen"

    "llm_verdict": {                           // null when explain=false or no LLM key
      "bucket":          "AVOID(insolvency)",  // LLM's own verdict — AVOID/WATCH/CLEAR/TRAINING-FLAG(*)
      "confidence":      "high",               // "high"|"medium"|"low"
      "one_line_risk":   "...",
      "grounded_claims": [{"claim":"...","field":"...","value":"...","fy":2024}],
      "training_flags":  [{"concern":"...","why_ungrounded":"...","investigate":"...","urgency":"high"}],
      "unresolved":      [{"screen_flag":"...","explanation":"...","next_step":"..."}],
      "narrative":       "2-4 sentence WHY..."
    },

    "screen_bucket":    "AVOID",               // Python 7-model screen (secondary evidence)
    "screen_flags": {                          // Python screen details (secondary)
      "distress_type":   "insolvency",
      "fraud":           false,
      "fraud_watchlist": false,
      "verdict":         "AVOID_unconfirmed",
      "note":            "...",
      "effective_reason":"..."
    },

    "market_cap":       7509911040,
    "sector":           "CONSUMER CYCLICAL",
    "signals": {
      "api_distress": false, "api_fraud": false,
      "api_high_short": false, "api_recent_raise": false,
      "short_dtc": 4.97, "n_news": 50,
      "n_bk_events": 0, "n_fraud_events": 0
    },
    "explanation": "..."                       // convenience alias for llm_verdict.narrative (null if no LLM)
  }

Run:
  python3 api_server.py                  # port 8080
  python3 api_server.py --port 9000
  PORT=9000 python3 api_server.py

  # test:
  curl http://localhost:8080/health
  curl -X POST http://localhost:8080/analyze -H "Content-Type: application/json" \
       -d '{"ticker":"AAPL","explain":false}'
"""
import os, sys, json, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

VERSION = "1.0.0"
MAX_BATCH = 200   # safety cap on batch size
MAX_WORKERS_CAP = 32

# lazy imports (heavy; loaded once on first request)
_process_one = None
_llm_client  = None
_lock        = threading.Lock()

def _ensure_imports():
    global _process_one, _llm_client
    if _process_one is not None:
        return
    with _lock:
        if _process_one is not None:
            return
        from calibrate import process_one
        from llm_client import LLMClient
        _process_one = process_one
        _llm_client  = LLMClient()


# ---- core analysis logic ---------------------------------------------------
def analyze_ticker(ticker, explain=False, model=None):
    """
    Run the full pipeline for one ticker.

    explain=False (default, fast):
      Layers 1+2 only (Python screen). effective_bucket = Python verdict.
      No LLM call, no AV fetch beyond the cache.

    explain=True (full investigation):
      Layers 1+2+3. Full financials + live API signals passed to LLM.
      LLM issues its OWN verdict — effective_bucket = LLM bucket (primary).
      Python screen moves to screen_bucket / screen_flags (secondary evidence).
      If LLM fails, falls back to Python screen bucket.

    Returns a clean dict ready for JSON serialisation.
    """
    _ensure_imports()
    ticker = ticker.upper().strip()

    # Layer 1 + 2: deterministic Python screen (always runs — source of evidence)
    try:
        result = _process_one(ticker, write=False)
    except Exception as e:
        return {"ticker": ticker, "error": f"pipeline error: {e}",
                "effective_bucket": "ERROR", "effective_source": "error"}

    # Python screen details (always secondary when LLM runs)
    python_effective = result.get("effective_bucket", "UNKNOWN")
    screen_flags = {
        "distress_type":    result.get("distress_type") or None,
        "fraud":            bool(result.get("fraud")),
        "fraud_watchlist":  bool(result.get("fraud_watchlist")),
        "verdict":          result.get("verdict", ""),
        "note":             result.get("note") or "",
        "effective_reason": result.get("effective_reason") or "",
    }

    out = {
        "ticker":           result.get("ticker", ticker),
        # effective_bucket and effective_source set below (LLM or Python)
        "effective_bucket": python_effective,
        "effective_source": "screen",
        "llm_verdict":      None,        # filled when explain=True and LLM succeeds
        "screen_bucket":    result.get("bucket", "UNKNOWN"),   # Python 7-model verdict
        "screen_flags":     screen_flags,                       # Python details
        "market_cap":       result.get("market_cap"),
        "sector":           result.get("sector") or "Unknown",
        "signals": {
            "api_distress":     bool(result.get("api_distress")),
            "api_fraud":        bool(result.get("api_fraud")),
            "api_high_short":   bool(result.get("api_high_short")),
            "api_recent_raise": bool(result.get("api_recent_raise")),
            "short_dtc":        result.get("short_dtc"),
            "n_news":           result.get("n_news", 0),
            "n_bk_events":      result.get("n_bk_events", 0),
            "n_fraud_events":   result.get("n_fraud_events", 0),
        },
        "explanation": None,    # convenience alias for llm_verdict.narrative
    }

    if explain and _llm_client and _llm_client.active:
        # Fetch all grounding data for LLM investigation
        full_hist     = None
        api_raw       = None
        price_hist    = None
        edgar_signals = None
        try:
            from data_loader import load_fundamentals, full_history, price_history
            from massive_api import event_scan
            from edgar_api  import edgar_10k_signals
            fund          = load_fundamentals(ticker)
            full_hist     = full_history(fund) if fund else None
            price_hist    = price_history(ticker, months=24)     # 2yr monthly price
            api_raw       = event_scan(ticker)                    # news + short interest
            edgar_signals = edgar_10k_signals(ticker)            # 10-K: going-concern, MW, covenants
        except Exception:
            pass   # LLM still runs with whatever it has

        client = _llm_client if not model else \
                 type(_llm_client)(provider=_llm_client.provider, model=model)

        # Layer 3 — LLM investigation: returns structured verdict dict
        verdict, err = client.explain(
            ticker, result, full_hist=full_hist, api_raw=api_raw,
            price_hist=price_hist, edgar_signals=edgar_signals
        )

        if verdict and isinstance(verdict, dict) and verdict.get("bucket"):
            # LLM succeeded — it is the primary effective_bucket
            out["llm_verdict"]      = verdict
            out["effective_bucket"] = verdict["bucket"]
            out["effective_source"] = "llm"
            out["explanation"]      = verdict.get("narrative")   # convenience alias
        else:
            # LLM failed — fall back to Python screen; surface the error
            out["effective_source"] = "screen"
            if err:
                out["llm_error"] = err

    return out


# ---- HTTP request handler --------------------------------------------------
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[api] {self.address_string()} {fmt % args}")

    def _send_json(self, code, obj):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except Exception:
            return {}

    # ---- GET routes --------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path == "/health":
            _ensure_imports()
            self._send_json(200, {
                "status":     "ok",
                "version":    VERSION,
                "llm_active": bool(_llm_client and _llm_client.active),
                "llm_provider": getattr(_llm_client, "provider", None),
            })

        elif path == "/universe/summary":
            findings_path = HERE / "CALIBRATED_FINDINGS.md"
            if findings_path.exists():
                content = findings_path.read_text()[:8000]   # first 8k chars
                self._send_json(200, {"summary": content})
            else:
                self._send_json(404, {"error": "CALIBRATED_FINDINGS.md not found"})

        else:
            self._send_json(404, {"error": f"unknown route: {path}",
                                   "routes": ["GET /health",
                                              "POST /analyze",
                                              "POST /analyze/batch",
                                              "GET /universe/summary"]})

    # ---- POST routes -------------------------------------------------------
    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        body = self._read_body()

        # ---- single ticker -------------------------------------------------
        if path == "/analyze":
            ticker = (body.get("ticker") or "").strip()
            if not ticker:
                self._send_json(400, {"error": "missing 'ticker' field"})
                return
            explain = bool(body.get("explain", False))
            model   = body.get("model")
            result  = analyze_ticker(ticker, explain=explain, model=model)
            self._send_json(200, result)

        # ---- batch ---------------------------------------------------------
        elif path == "/analyze/batch":
            tickers = body.get("tickers") or []
            if not tickers:
                self._send_json(400, {"error": "missing 'tickers' list"})
                return
            if len(tickers) > MAX_BATCH:
                self._send_json(400, {"error": f"batch too large (max {MAX_BATCH})"})
                return
            explain     = bool(body.get("explain", False))
            model       = body.get("model")
            max_workers = min(int(body.get("max_workers", 4)), MAX_WORKERS_CAP)
            results     = [None] * len(tickers)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {
                    pool.submit(analyze_ticker, t, explain, model): i
                    for i, t in enumerate(tickers)
                }
                for future in as_completed(futures):
                    i = futures[future]
                    try:
                        results[i] = future.result()
                    except Exception as e:
                        results[i] = {"ticker": tickers[i], "error": str(e),
                                      "effective_bucket": "ERROR"}
            self._send_json(200, {"count": len(results), "results": results})

        else:
            self._send_json(404, {"error": f"unknown route: {path}"})


# ---- server setup ----------------------------------------------------------
class ThreadingHTTPServer(HTTPServer):
    """Handle each request in a separate thread."""
    def process_request(self, request, client_address):
        t = threading.Thread(target=self.__process_request,
                             args=(request, client_address), daemon=True)
        t.start()

    def __process_request(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Distress & Fraud Analyst API server")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PORT", 8080)))
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    args = parser.parse_args()

    print(f"[api] Distress & Fraud Analyst v{VERSION}")
    print(f"[api] Warming up imports...")
    _ensure_imports()
    print(f"[api] LLM: {_llm_client}")
    print(f"[api] Listening on {args.host}:{args.port}")
    print(f"[api]   GET  http://{args.host}:{args.port}/health")
    print(f"[api]   POST http://{args.host}:{args.port}/analyze")
    print(f"[api]   POST http://{args.host}:{args.port}/analyze/batch")
    print(f"[api]   GET  http://{args.host}:{args.port}/universe/summary")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[api] shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
