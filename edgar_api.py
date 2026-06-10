#!/usr/bin/env python3
"""
edgar_api.py -- SEC EDGAR 10-K signal extraction for distress/fraud grounding.

Fetches the latest 10-K filing for a ticker and extracts key risk signals:
  - going_concern_flag      Auditor raised going-concern doubt ("substantial doubt")
  - material_weakness_flag  Material weakness in internal controls disclosed
  - covenant_risk_flag      Covenant violation / waiver / forbearance language found
  - mda_excerpt             First ~3000 chars of MD&A (management's own risk narrative)

All data is sourced directly from SEC EDGAR (free, no API key required).
SEC asks for: max 10 req/sec + descriptive User-Agent header (both honoured).

Cache: edgar_cache table in av_cache.db — 7-day TTL (filings don't change).

grounding_source for LLM claims: "edgar_10k"
  Cite as: field="going_concern_flag", value="True", filing_date="YYYY-MM-DD"
  Or for text excerpts: field="auditor_report_excerpt", value="... text ..."

Download strategy:
  Read up to MAX_BYTES of raw HTML (default 2MB) from the primary 10-K document.
  For most distressed companies (the ones that matter), the full filing fits within
  this limit. Large-cap healthy companies rarely need going-concern checks.
  text_truncated=True signals the document was larger and the tail was not read.

Usage:
  from edgar_api import edgar_10k_signals
  signals = edgar_10k_signals("BYND")
  # signals["going_concern_flag"]        True/False
  # signals["material_weakness_flag"]    True/False
  # signals["covenant_risk_flag"]        True/False
  # signals["mda_excerpt"]               str or None
  # signals["going_concern_excerpts"]    list of {keyword, excerpt}
  # signals["text_truncated"]            True if document > MAX_BYTES

  python3 edgar_api.py BYND    # live test with signal output
  python3 edgar_api.py VFS
"""
import os, json, re, time, sqlite3, urllib.request, urllib.error, urllib.parse
from pathlib import Path

HERE          = Path(__file__).parent
CACHE_DB      = HERE / "av_cache.db"          # shared with data_loader
CACHE_TTL_DAYS = 7                             # 10-K filings don't change after filing
MAX_BYTES     = 2_000_000                      # 2MB raw HTML cap (~500K stripped chars)

# SEC requires a descriptive User-Agent
_SEC_UA = "StockAffirm Distress Analyst contact@stockaffirm.com"

EDGAR_BASE  = "https://data.sec.gov"
EDGAR_FILES = "https://www.sec.gov"

# ── Going-concern language in auditor's report ─────────────────────────────
_GOING_CONCERN_KWS = [
    "going concern",
    "substantial doubt",
    "ability to continue as a going concern",
    "going-concern",
    "doubt about the company's ability",
    "substantial doubt exists",
]

# ── Material weakness in internal controls ─────────────────────────────────
# Positive phrases: an actual material weakness was FOUND / IDENTIFIED.
_MATERIAL_WEAKNESS_KWS = [
    "identified a material weakness",
    "identified material weaknesses",
    "material weakness exists",
    "material weaknesses exist",
    "material weakness was identified",
    "has a material weakness",
    "have identified the following material weakness",
    "we have identified material weakness",
]
# Exclude boilerplate audit-process language ("assessing the risk that a material weakness exists")
# These patterns in the excerpt context → false positive; skip the hit.
_MATERIAL_WEAKNESS_EXCLUDE = [
    "assessing the risk that a material weakness",
    "risk that a material weakness exists",
    "risk that a material weakness may",
    "probability that a material weakness",
]

# ── Covenant / debt-default language (debt covenants specifically, not regulatory) ──
# Deliberately narrow: exclude generic "not in compliance with" (catches FCPA, foreign regs).
_COVENANT_KWS = [
    "event of default",
    "forbearance agreement",
    "covenant waiver",
    "covenant violation",
    "breach of covenant",
    "covenant breach",
    "cross-default",
    "in default under",
    "waiver of compliance with",
    "financial covenant",
    "debt covenant",
    "loan covenant",
    "credit agreement covenant",
]

# ── MD&A section markers (try in order) ────────────────────────────────────
# Many modern 10-Ks have contracted apostrophes ("management s") after HTML strip.
_MDA_MARKERS = [
    "management's discussion and analysis",
    "management s discussion and analysis",
    "results of operations",
    "overview of results",
]


# ── HTTP helpers ────────────────────────────────────────────────────────────
def _sec_get_json(url, max_tries=3):
    """GET JSON from SEC EDGAR with required User-Agent + polite retry."""
    headers = {"User-Agent": _SEC_UA, "Accept": "application/json"}
    a, b = 1, 1
    for attempt in range(max_tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 and attempt < max_tries - 1:
                time.sleep(a); a, b = b, a + b
                continue
            return None
        except Exception:
            if attempt < max_tries - 1:
                time.sleep(a); a, b = b, a + b
            continue
    return None


def _sec_get_html(url, max_bytes=MAX_BYTES, max_tries=3):
    """
    GET HTML/text from EDGAR, limited to max_bytes.
    Returns (text_str, truncated_bool).
    """
    headers = {"User-Agent": _SEC_UA, "Accept": "text/html,text/plain"}
    for attempt in range(max_tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read(max_bytes)
                # If we read exactly max_bytes the document was probably larger
                truncated = len(data) == max_bytes
            return data.decode("utf-8", errors="replace"), truncated
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, False
            if e.code in (429, 502, 503) and attempt < max_tries - 1:
                time.sleep(2 ** attempt)
                continue
            return None, False
        except Exception:
            if attempt < max_tries - 1:
                time.sleep(1)
            continue
    return None, False


# ── HTML → plain text ────────────────────────────────────────────────────────
def _strip_html(html):
    """Strip HTML tags and normalise whitespace for keyword search."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&amp;',  '&',  text)
    text = re.sub(r'&lt;',   '<',  text)
    text = re.sub(r'&gt;',   '>',  text)
    text = re.sub(r'&nbsp;', ' ',  text)
    text = re.sub(r'&#\d+;', ' ',  text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s{3,}', '  ', text)
    return text.strip()


# ── Cache (edgar_cache table in av_cache.db) ─────────────────────────────────
def _cache_init(con):
    con.execute("""CREATE TABLE IF NOT EXISTS edgar_cache (
        ticker       TEXT PRIMARY KEY,
        signals_json TEXT,
        fetched_utc  INTEGER
    )""")
    con.commit()


def _cache_get(ticker):
    try:
        con = sqlite3.connect(str(CACHE_DB))
        _cache_init(con)
        row = con.execute(
            "SELECT signals_json, fetched_utc FROM edgar_cache WHERE ticker=?",
            (ticker.upper(),)
        ).fetchone()
        if not row:
            return None
        age_days = (time.time() - (row[1] or 0)) / 86400
        if age_days > CACHE_TTL_DAYS:
            return None
        return json.loads(row[0]) if row[0] else None
    except Exception:
        return None


def _cache_set(ticker, signals):
    try:
        con = sqlite3.connect(str(CACHE_DB))
        _cache_init(con)
        con.execute(
            "INSERT OR REPLACE INTO edgar_cache (ticker, signals_json, fetched_utc) "
            "VALUES (?,?,?)",
            (ticker.upper(), json.dumps(signals), int(time.time()))
        )
        con.commit()
    except Exception:
        pass


# ── CIK lookup (module-level in-memory cache) ────────────────────────────────
_TICKER_MAP: dict = {}
_TICKER_MAP_LOADED = False


def _load_ticker_map():
    global _TICKER_MAP, _TICKER_MAP_LOADED
    if _TICKER_MAP_LOADED:
        return
    data = _sec_get_json("https://www.sec.gov/files/company_tickers.json")
    if data:
        for entry in data.values():
            t = (entry.get("ticker") or "").upper()
            c = entry.get("cik_str")
            if t and c is not None:
                _TICKER_MAP[t] = int(c)
    _TICKER_MAP_LOADED = True


def _cik(ticker):
    """Return integer CIK for ticker, or None if not found."""
    _load_ticker_map()
    return _TICKER_MAP.get(ticker.upper())


# ── 10-K filing lookup ────────────────────────────────────────────────────────
def _latest_10k_info(cik):
    """
    Return (accession_nodash, filing_date, fy_end, primary_doc_url) for the
    most recent 10-K or 10-K/A filing.
    Uses the primaryDocument field from submissions JSON — one API call, no index fetch.
    """
    url = f"{EDGAR_BASE}/submissions/CIK{cik:010d}.json"
    time.sleep(0.15)   # polite rate limiting
    data = _sec_get_json(url)
    if not data:
        return None, None, None, None

    recent       = (data.get("filings") or {}).get("recent") or {}
    forms        = recent.get("form") or []
    accs         = recent.get("accessionNumber") or []
    dates        = recent.get("filingDate") or []
    periods      = recent.get("reportDate") or []
    primary_docs = recent.get("primaryDocument") or []

    for i, form in enumerate(forms):
        if form in ("10-K", "10-K/A"):
            acc = accs[i] if i < len(accs) else None
            if not acc:
                continue
            acc_nodash = acc.replace("-", "")
            fd  = dates[i]        if i < len(dates)        else None
            fy  = periods[i]      if i < len(periods)      else None
            pd  = primary_docs[i] if i < len(primary_docs) else None
            if pd:
                doc_url = (f"{EDGAR_FILES}/Archives/edgar/data"
                           f"/{cik}/{acc_nodash}/{pd}")
            else:
                doc_url = None
            return acc_nodash, fd, fy, doc_url

    return None, None, None, None


# ── Signal extraction from stripped 10-K text ─────────────────────────────────
def _context_window(text, pos, before=150, after=450):
    """Extract text window around position `pos`."""
    start = max(0, pos - before)
    end   = min(len(text), pos + after)
    return text[start:end].strip()


def _find_excerpts(text, keywords, max_hits=3, exclude_patterns=None):
    """
    Find up to max_hits non-overlapping excerpts matching any keyword.
    exclude_patterns: list of strings — if any appear in the excerpt context,
                      skip the hit (used to filter boilerplate / false-positive phrases).
    Returns list of {keyword, excerpt} dicts.
    """
    tl      = text.lower()
    excl_lc = [p.lower() for p in (exclude_patterns or [])]
    hits    = []
    seen_positions: list = []

    for kw in keywords:
        pos = 0
        while len(hits) < max_hits:
            idx = tl.find(kw.lower(), pos)
            if idx == -1:
                break
            # Skip if too close to a previous hit (avoids near-duplicates)
            if all(abs(idx - s) > 600 for s in seen_positions):
                excerpt = _context_window(text, idx)
                excerpt_lc = excerpt.lower()
                # Apply exclusion filter
                if not any(ep in excerpt_lc for ep in excl_lc):
                    hits.append({"keyword": kw, "excerpt": excerpt[:600]})
                    seen_positions.append(idx)
            pos = idx + len(kw)

    return hits


def _extract_mda(text, max_chars=3000):
    """
    Extract the start of the MD&A section, skipping Table-of-Contents entries.

    ToC entries look like: "Item 7.  MD&A ... 74  Item 7A."
    (a page number followed immediately by another Item marker).
    Real content has paragraphs of text with no immediate page-number-then-item pattern.
    """
    tl = text.lower()

    for marker in _MDA_MARKERS:
        pos = 0
        while True:
            idx = tl.find(marker, pos)
            if idx == -1:
                break
            # Check the 400 chars after the marker for a ToC-like pattern
            ahead = text[idx: idx + 400]
            # ToC pattern: "  74  Item 7A." or "  108\n  Item"
            is_toc = bool(re.search(r'\b\d{1,3}\s{1,8}item\s+\d', ahead.lower()))
            if not is_toc:
                # Real content — return the excerpt
                return text[idx: idx + max_chars].strip()
            pos = idx + len(marker)

    return None


def _extract_signals(text):
    """
    Scan stripped 10-K text for distress / fraud signals.
    Returns dict with flags and excerpt lists.
    """
    gc  = _find_excerpts(text, _GOING_CONCERN_KWS,     max_hits=3)
    mw  = _find_excerpts(text, _MATERIAL_WEAKNESS_KWS, max_hits=3,
                         exclude_patterns=_MATERIAL_WEAKNESS_EXCLUDE)
    cov = _find_excerpts(text, _COVENANT_KWS,          max_hits=3)
    mda = _extract_mda(text, max_chars=3000)
    return {
        "going_concern_flag":         bool(gc),
        "going_concern_excerpts":     gc,
        "material_weakness_flag":     bool(mw),
        "material_weakness_excerpts": mw,
        "covenant_risk_flag":         bool(cov),
        "covenant_excerpts":          cov,
        "mda_excerpt":                mda,
    }


# ── Public API ────────────────────────────────────────────────────────────────
def edgar_10k_signals(ticker):
    """
    Fetch key risk signals from the latest SEC EDGAR 10-K filing.

    Returns a dict with:
      ticker                          UPPER
      filing_date                     "YYYY-MM-DD"  (date 10-K was filed)
      fiscal_year_end                 "YYYY-MM-DD"  (period the 10-K covers)
      edgar_url                       Full URL of the 10-K document
      going_concern_flag              True if auditor's report has going-concern doubt
      going_concern_excerpts          [{keyword, excerpt}] text windows
      material_weakness_flag          True if material weakness disclosed
      material_weakness_excerpts      [{keyword, excerpt}]
      covenant_risk_flag              True if covenant violation/waiver language found
      covenant_excerpts               [{keyword, excerpt}]
      mda_excerpt                     First ~3000 chars of MD&A section (may be None)
      text_truncated                  True if doc exceeded MAX_BYTES (signals from tail missed)
      error                           None on success, error string on failure

    grounding_source for LLM claims: "edgar_10k"
    Cite as: field="going_concern_flag", value="True", filing_date="YYYY-MM-DD"
    For excerpts: field="auditor_report_excerpt", value="<quoted text>"

    Cache: 7-day TTL — filings don't change after their filing date.
    """
    T = ticker.upper()

    cached = _cache_get(T)
    if cached is not None:
        return cached

    _empty = {
        "ticker": T, "filing_date": None, "fiscal_year_end": None,
        "edgar_url": None,
        "going_concern_flag": False, "going_concern_excerpts": [],
        "material_weakness_flag": False, "material_weakness_excerpts": [],
        "covenant_risk_flag": False, "covenant_excerpts": [],
        "mda_excerpt": None, "text_truncated": False, "error": None,
    }

    # Step 1: CIK
    cik = _cik(T)
    if not cik:
        result = {**_empty, "error": f"CIK not found for {T} — not in EDGAR company_tickers.json"}
        _cache_set(T, result)
        return result

    # Step 2: Latest 10-K filing info
    acc_nodash, filing_date, fy_end, doc_url = _latest_10k_info(cik)
    if not acc_nodash:
        result = {**_empty, "error": f"No 10-K filing found for {T} (CIK {cik})"}
        _cache_set(T, result)
        return result

    base_url = (f"{EDGAR_FILES}/cgi-bin/browse-edgar?"
                f"action=getcompany&CIK={cik}&type=10-K")
    result = {
        **_empty,
        "filing_date":    filing_date,
        "fiscal_year_end": fy_end,
        "edgar_url":      doc_url or base_url,
    }

    if not doc_url:
        result["error"] = "No primary document URL found in filing manifest"
        _cache_set(T, result)
        return result

    # Step 3: Download (capped at MAX_BYTES) and extract
    time.sleep(0.2)   # polite rate limiting
    html, truncated = _sec_get_html(doc_url, max_bytes=MAX_BYTES)
    if html is None:
        result["error"] = f"Could not download 10-K from {doc_url}"
        _cache_set(T, result)
        return result

    stripped_text = _strip_html(html)
    extracted = _extract_signals(stripped_text)
    result.update(extracted)
    result["text_truncated"] = truncated

    _cache_set(T, result)
    return result


# ── CLI test ──────────────────────────────────────────────────────────────────
def main():
    import sys
    tickers = sys.argv[1:] or ["BYND", "ORCL"]
    for t in tickers:
        print(f"\n{'='*60}")
        print(f"EDGAR 10-K signals: {t}")
        s = edgar_10k_signals(t)
        print(f"  Filing date:    {s.get('filing_date')}  FY: {s.get('fiscal_year_end')}")
        print(f"  URL:            {s.get('edgar_url')}")
        print(f"  going_concern:  {s['going_concern_flag']}")
        print(f"  mat_weakness:   {s['material_weakness_flag']}")
        print(f"  covenant_risk:  {s['covenant_risk_flag']}")
        print(f"  text_truncated: {s['text_truncated']}")
        if s.get("error"):
            print(f"  Error: {s['error']}")
        for ex in s.get("going_concern_excerpts", []):
            print(f"\n  [GOING-CONCERN] kw='{ex['keyword']}'")
            print(f"    {ex['excerpt'][:300]}")
        for ex in s.get("material_weakness_excerpts", []):
            print(f"\n  [MATERIAL-WEAKNESS] kw='{ex['keyword']}'")
            print(f"    {ex['excerpt'][:300]}")
        for ex in s.get("covenant_excerpts", []):
            print(f"\n  [COVENANT] kw='{ex['keyword']}'")
            print(f"    {ex['excerpt'][:300]}")
        if s.get("mda_excerpt"):
            print(f"\n  [MD&A excerpt] {s['mda_excerpt'][:400]}...")


if __name__ == "__main__":
    main()
