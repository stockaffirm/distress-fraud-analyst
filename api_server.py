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
    "screen_bucket":    "AVOID",
    "effective_bucket": "AVOID",
    "distress_type":    "insolvency",
    "fraud":            false,
    "verdict":          "AVOID_unconfirmed",
    "market_cap":       7509911040,
    "sector":           "CONSUMER CYCLICAL",
    "signals": {
      "api_distress": false, "api_fraud": false,
      "api_high_short": false, "api_recent_raise": false,
      "short_dtc": 4.97, "n_news": 50,
      "n_bk_events": 0, "n_fraud_events": 0
    },
    "note":             "...",
    "effective_reason": "...",
    "explanation":      "... (LLM text, null if explain=false or no key)"
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
    When explain=True, passes FULL multi-year financials + live API signals to
    the LLM so it can investigate and ground every claim in actual data.
    Returns a clean dict ready for JSON serialisation.
    """
    _ensure_imports()
    ticker = ticker.upper().strip()

    # Layer 1 + 2: deterministic Python screen
    try:
        result = _process_one(ticker, write=False)
    except Exception as e:
        return {"ticker": ticker, "error": f"pipeline error: {e}",
                "effective_bucket": "ERROR"}

    # Fetch full financials + raw API signals for LLM investigation
    # (only when explain=True to avoid unnecessary AV calls on fast/batch queries)
    full_hist = None
    api_raw   = None
    if explain and _llm_client and _llm_client.active:
        try:
            from data_loader import load_fundamentals, full_history
            from massive_api import event_scan
            fund      = load_fundamentals(ticker)
            full_hist = full_history(fund) if fund else None
            api_raw   = event_scan(ticker)
        except Exception:
            pass   # LLM will still run with whatever it has

    out = {
        "ticker":           result.get("ticker", ticker),
        "screen_bucket":    result.get("bucket", "UNKNOWN"),
        "effective_bucket": result.get("effective_bucket", "UNKNOWN"),
        "distress_type":    result.get("distress_type") or None,
        "fraud":            bool(result.get("fraud")),
        "fraud_watchlist":  bool(result.get("fraud_watchlist")),
        "verdict":          result.get("verdict", ""),
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
        "note":             result.get("note") or "",
        "effective_reason": result.get("effective_reason") or "",
        "explanation":      None,
    }

    if explain and _llm_client and _llm_client.active:
        client = _llm_client if not model else \
                 type(_llm_client)(provider=_llm_client.provider, model=model)
        # Pass full financials + raw API signals so LLM can ground every claim
        explanation, err = client.explain(
            ticker, result, full_hist=full_hist, api_raw=api_raw
        )
        out["explanation"] = explanation
        if err and not explanation:
            out["explanation_error"] = err

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
