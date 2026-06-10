#!/usr/bin/env python3
"""
data_loader.py -- Analyst Agent data layer (READ-ONLY)

Fetches fundamentals LIVE from Alpha Vantage API, per ticker, on demand.
Caches results in local SQLite (av_cache.db, 24hr TTL) to avoid redundant calls.
Fibonacci retry on rate-limits / server errors.

Self-sustaining: works anywhere with an AV_API_KEY. No local ZIP files or
StockAffirm pipeline required. 75 subagents can run in parallel — each fetches
its own ticker independently; SQLite handles concurrent cache reads/writes.

AV endpoints used per ticker (fundamentals: 4 calls on first fetch, 0 on cache hit):
  INCOME_STATEMENT · BALANCE_SHEET · CASH_FLOW · OVERVIEW

AV endpoints for price history (1 call on first fetch, 0 on cache hit):
  TIME_SERIES_MONTHLY_ADJUSTED  → price_history(ticker, months=24)
  grounding_source = "av_price_data" in LLM verdicts

Key lookup order:
  1. ALPHAVANTAGE_API_KEY env var
  2. AV_API_KEY env var
  3. .env file (next to this script, then project root, then stockaffirm/.env)
"""
import os, csv, json, time, sqlite3, urllib.request, urllib.error, functools
from pathlib import Path

# ---- config -----------------------------------------------------------------
HERE     = Path(__file__).parent
CACHE_DB = HERE / "av_cache.db"
CACHE_TTL_HOURS = 24   # re-fetch after 24 hours
AV_BASE  = "https://www.alphavantage.co/query"
_AV_KEY  = None


def _av_key():
    global _AV_KEY
    if _AV_KEY:
        return _AV_KEY
    k = os.environ.get("ALPHAVANTAGE_API_KEY") or os.environ.get("AV_API_KEY")
    if not k:
        for envp in [HERE / ".env", HERE.parent / ".env",
                     Path("/Users/prasadmenon/Claude/StockAffirmProject/stockaffirm/.env")]:
            if envp.exists():
                for line in open(envp):
                    line = line.strip()
                    for pfx in ("ALPHAVANTAGE_API_KEY=", "AV_API_KEY="):
                        if line.startswith(pfx):
                            k = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
                if k:
                    break
    _AV_KEY = k
    return _AV_KEY


# ---- fibonacci retry HTTP ---------------------------------------------------
def _fib_fetch(url, max_tries=7):
    """GET url; fibonacci backoff (1,1,2,3,5,8,13s) on rate-limit / server error."""
    a, b = 1, 1
    for attempt in range(max_tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.loads(r.read().decode())
            # AV returns {"Note":...} or {"Information":...} on rate-limit
            note = data.get("Note") or data.get("Information") or ""
            if note and ("call frequency" in note.lower() or "api key" in note.lower()):
                if attempt < max_tries - 1:
                    time.sleep(a); a, b = b, a + b
                    continue
                return None
            return data
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_tries - 1:
                time.sleep(a); a, b = b, a + b
                continue
            return None
        except Exception:
            if attempt < max_tries - 1:
                time.sleep(a); a, b = b, a + b
            continue
    return None


def _av_get(function, symbol):
    key = _av_key()
    if not key:
        return None
    url = f"{AV_BASE}?function={function}&symbol={symbol.upper()}&apikey={key}"
    return _fib_fetch(url)


# ---- SQLite cache -----------------------------------------------------------
def _cache_init():
    con = sqlite3.connect(str(CACHE_DB))
    con.execute("""CREATE TABLE IF NOT EXISTS av_cache (
        ticker       TEXT PRIMARY KEY,
        income_json  TEXT,
        balance_json TEXT,
        cashflow_json TEXT,
        overview_json TEXT,
        fetched_utc  INTEGER
    )""")
    # Separate table for monthly price history (TIME_SERIES_MONTHLY_ADJUSTED).
    # Kept separate from fundamentals so price refreshes independently.
    con.execute("""CREATE TABLE IF NOT EXISTS av_price_cache (
        ticker      TEXT PRIMARY KEY,
        price_json  TEXT,
        fetched_utc INTEGER
    )""")
    con.commit()
    return con


# ---- Price cache helpers ---------------------------------------------------
def _price_cache_get(ticker):
    """Return cached monthly price list if fresh (< TTL), else None."""
    try:
        con = sqlite3.connect(str(CACHE_DB))
        con.execute("""CREATE TABLE IF NOT EXISTS av_price_cache (
            ticker TEXT PRIMARY KEY, price_json TEXT, fetched_utc INTEGER
        )""")
        row = con.execute(
            "SELECT price_json, fetched_utc FROM av_price_cache WHERE ticker=?",
            (ticker.upper(),)
        ).fetchone()
        if not row:
            return None
        age_hours = (time.time() - (row[1] or 0)) / 3600
        if age_hours > CACHE_TTL_HOURS:
            return None
        return json.loads(row[0]) if row[0] else None
    except Exception:
        return None


def _price_cache_set(ticker, price_data):
    try:
        con = sqlite3.connect(str(CACHE_DB))
        con.execute("""CREATE TABLE IF NOT EXISTS av_price_cache (
            ticker TEXT PRIMARY KEY, price_json TEXT, fetched_utc INTEGER
        )""")
        con.execute(
            "INSERT OR REPLACE INTO av_price_cache (ticker, price_json, fetched_utc) "
            "VALUES (?,?,?)",
            (ticker.upper(), json.dumps(price_data), int(time.time()))
        )
        con.commit()
    except Exception:
        pass


def _cache_get(ticker):
    """Return cached AV blobs if fresh (< TTL), else None."""
    try:
        con = sqlite3.connect(str(CACHE_DB))
        row = con.execute(
            "SELECT income_json, balance_json, cashflow_json, overview_json, fetched_utc "
            "FROM av_cache WHERE ticker=?", (ticker.upper(),)
        ).fetchone()
        if not row:
            return None
        age_hours = (time.time() - (row[4] or 0)) / 3600
        if age_hours > CACHE_TTL_HOURS:
            return None   # stale — refetch
        return {"income":    json.loads(row[0]) if row[0] else None,
                "balance":   json.loads(row[1]) if row[1] else None,
                "cashflow":  json.loads(row[2]) if row[2] else None,
                "overview":  json.loads(row[3]) if row[3] else None}
    except Exception:
        return None


def _cache_set(ticker, income, balance, cashflow, overview):
    try:
        con = _cache_init()
        con.execute(
            "INSERT OR REPLACE INTO av_cache "
            "(ticker, income_json, balance_json, cashflow_json, overview_json, fetched_utc) "
            "VALUES (?,?,?,?,?,?)",
            (ticker.upper(),
             json.dumps(income)   if income   else None,
             json.dumps(balance)  if balance  else None,
             json.dumps(cashflow) if cashflow else None,
             json.dumps(overview) if overview else None,
             int(time.time()))
        )
        con.commit()
    except Exception:
        pass


# ---- AV → internal format translation --------------------------------------
def _n(v):
    """Parse AV numeric string ('123456' or 'None') → float or None."""
    if v is None or v == "None" or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _av_to_fund(income_data, balance_data, cashflow_data):
    """
    Translate Alpha Vantage annualReports dicts → the internal fund format
    (income_statements / balance_sheets / cash_flows with field names that
    financial_history() and full_history() already know).
    """
    def parse_income(r):
        fy = int(r["fiscalDateEnding"][:4]) if r.get("fiscalDateEnding") else None
        return {
            "timeframe":   "annual",
            "fiscal_year": fy,
            "period_end":  r.get("fiscalDateEnding"),
            "revenue":     _n(r.get("totalRevenue")),
            "cost_of_revenue":  _n(r.get("costOfRevenue")),
            "gross_profit":     _n(r.get("grossProfit")),
            "selling_general_administrative": _n(r.get("sellingGeneralAndAdministrative")),
            "operating_income": _n(r.get("operatingIncome")),
            "ebitda":           _n(r.get("ebitda")),
            "income_before_income_taxes":   _n(r.get("incomeBeforeTax")),
            "income_taxes":     _n(r.get("incomeTaxExpense")),
            # two synonyms so full_history's g(*keys) fallback works
            "net_income_loss_attributable_common_shareholders": _n(r.get("netIncome")),
            "consolidated_net_income_loss":  _n(r.get("netIncome")),
            "diluted_shares_outstanding":    _n(r.get("dilutedAverageShares")),
            "basic_shares_outstanding":      _n(r.get("commonStockSharesOutstanding")),
            "total_other_income_expense":    _n(r.get("nonOperatingIncome")),
            "other_income_expense":          _n(r.get("nonOperatingIncome")),
            "interest_expense":              _n(r.get("interestAndDebtExpense")),
        }

    def parse_balance(r):
        fy = int(r["fiscalDateEnding"][:4]) if r.get("fiscalDateEnding") else None
        lt_debt   = _n(r.get("longTermDebtNoncurrent")) or _n(r.get("longTermDebt")) or 0
        cap_lease = _n(r.get("capitalLeaseObligations")) or 0
        curr_debt = _n(r.get("currentDebt")) or _n(r.get("shortTermDebt")) or 0
        return {
            "timeframe":   "annual",
            "fiscal_year": fy,
            "period_end":  r.get("fiscalDateEnding"),
            "total_assets":             _n(r.get("totalAssets")),
            "total_current_assets":     _n(r.get("totalCurrentAssets")),
            "total_current_liabilities":_n(r.get("totalCurrentLiabilities")),
            "total_liabilities":        _n(r.get("totalLiabilities")),
            "total_equity":             _n(r.get("totalShareholderEquity")),
            "retained_earnings_deficit":_n(r.get("retainedEarnings")),
            "cash_and_equivalents":     _n(r.get("cashAndCashEquivalentsAtCarryingValue")),
            "short_term_investments":   _n(r.get("shortTermInvestments")),
            "receivables":              _n(r.get("currentNetReceivables")),
            "inventories":              _n(r.get("inventory")),
            "property_plant_equipment_net": _n(r.get("propertyPlantEquipmentNet")),
            "intangible_assets_net":    _n(r.get("intangibleAssets")),
            "accounts_payable":         _n(r.get("currentAccountsPayable")),
            "deferred_revenue_current": _n(r.get("deferredRevenue")),
            "debt_current":             curr_debt,
            # lt_debt + capital leases combined (matches what full_history sums)
            "long_term_debt_and_capital_lease_obligations": lt_debt + cap_lease,
            "treasury_stock":           _n(r.get("treasuryStock")),
        }

    def parse_cashflow(r):
        fy    = int(r["fiscalDateEnding"][:4]) if r.get("fiscalDateEnding") else None
        capex = _n(r.get("capitalExpenditures"))   # AV reports as negative outflow
        return {
            "timeframe":   "annual",
            "fiscal_year": fy,
            "period_end":  r.get("fiscalDateEnding"),
            # two synonyms so full_history's g(*keys) fallback works
            "net_cash_from_operating_activities":                    _n(r.get("operatingCashflow")),
            "cash_from_operating_activities_continuing_operations":  _n(r.get("operatingCashflow")),
            "depreciation_depletion_and_amortization": _n(r.get("depreciationDepletionAndAmortization")),
            "purchase_of_property_plant_and_equipment": capex,   # kept negative; full_history negates it
            "dividends":               _n(r.get("dividendPayout")),
            "net_income":              _n(r.get("netIncome")),
            "long_term_debt_issuances_repayments": None,          # not directly exposed by AV
        }

    income_rpts  = (income_data   or {}).get("annualReports") or []
    balance_rpts = (balance_data  or {}).get("annualReports") or []
    cf_rpts      = (cashflow_data or {}).get("annualReports") or []

    return {
        "income_statements": [parse_income(r)    for r in income_rpts],
        "balance_sheets":    [parse_balance(r)   for r in balance_rpts],
        "cash_flows":        [parse_cashflow(r)  for r in cf_rpts],
    }


# ---- public API (same signatures as before) --------------------------------
def load_fundamentals(ticker):
    """
    Return internal fund dict for ticker (cache-first, AV API on miss).
    Returns None if no data (delisted / too new / no AV key).
    Callers: distress_screen.py, valuation.py, analyst.py
    """
    t = ticker.upper()

    # 1. cache hit
    cached = _cache_get(t)
    if cached:
        return _av_to_fund(cached["income"], cached["balance"], cached["cashflow"])

    # 2. cache miss — fetch all 4 AV endpoints
    income   = _av_get("INCOME_STATEMENT", t)
    balance  = _av_get("BALANCE_SHEET",    t)
    cashflow = _av_get("CASH_FLOW",        t)
    overview = _av_get("OVERVIEW",         t)

    if not income and not balance:
        return None   # no data available

    _cache_set(t, income, balance, cashflow, overview)
    return _av_to_fund(income, balance, cashflow)


def load_context(ticker):
    """
    Return market_cap, sector, and basic context for a ticker.
    Source: AV OVERVIEW endpoint (cached alongside fundamentals).
    """
    t = ticker.upper()

    # try to get overview from cache
    cached = _cache_get(t)
    if cached and cached.get("overview"):
        ov = cached["overview"]
    else:
        # need to fetch — do all 4 at once so we pay the 4-call cost only once
        income   = _av_get("INCOME_STATEMENT", t)
        balance  = _av_get("BALANCE_SHEET",    t)
        cashflow = _av_get("CASH_FLOW",        t)
        ov       = _av_get("OVERVIEW",         t)
        _cache_set(t, income, balance, cashflow, ov)

    if not ov:
        return None

    return {
        "ticker":           t,
        "sector":           ov.get("Sector") or "Unknown",
        "market_cap":       _n(ov.get("MarketCapitalization")),
        "trailing_pe":      _n(ov.get("TrailingPE")),
        "n_analysts":       _n(ov.get("AnalystRatingCount")),
        "rec_mean":         None,   # not in AV OVERVIEW
        "target_upside":    None,
        "engine_composite": None,
        "engine_tier":      None,
        "piotroski_f":      None,
        "altman_z":         None,
        # bonus fields exposed by AV (useful for capital-return context)
        "name":             ov.get("Name"),
        "description":      (ov.get("Description") or "")[:300],
        "exchange":         ov.get("Exchange"),
        "industry":         ov.get("Industry"),
        "shares_outstanding": _n(ov.get("SharesOutstanding")),
        "dividend_yield":   _n(ov.get("DividendYield")),
        "52w_high":         _n(ov.get("52WeekHigh")),
        "52w_low":          _n(ov.get("52WeekLow")),
    }


# ---- Price history ----------------------------------------------------------
def price_history(ticker, months=24):
    """
    Return monthly price history from Alpha Vantage TIME_SERIES_MONTHLY_ADJUSTED.

    Returns list of {date, close, adj_close, volume} sorted newest-first,
    limited to `months` entries (default 24 = 2 years).

    grounding_source for LLM claims: "av_price_data"
    Cite as: field="adj_close", value="$NNN", date="YYYY-MM-DD"

    Returns empty list if no AV key or data unavailable.
    """
    t = ticker.upper()

    # Cache hit
    cached = _price_cache_get(t)
    if cached is not None:
        return cached[:months]

    # Fetch from AV
    key = _av_key()
    if not key:
        return []
    url = (f"{AV_BASE}?function=TIME_SERIES_MONTHLY_ADJUSTED"
           f"&symbol={t}&apikey={key}")
    data = _fib_fetch(url)
    if not data:
        return []

    ts = data.get("Monthly Adjusted Time Series") or {}
    rows = []
    for date_str, vals in sorted(ts.items(), reverse=True):
        rows.append({
            "date":      date_str,
            "close":     _n(vals.get("4. close")),
            "adj_close": _n(vals.get("5. adjusted close")),
            "volume":    _n(vals.get("6. volume")),
        })

    _price_cache_set(t, rows)
    return rows[:months]


# ---- _recs compatibility shim ----------------------------------------------
# calibrate.py imports _recs to build the ordered calibration universe.
# If the local StockAffirm recommendations.csv exists, read it (local install);
# otherwise return an empty dict (shipped/standalone install — universe comes
# from the caller, not from _recs).
_RECS_PATHS = [
    Path("/Users/prasadmenon/Claude/StockAffirmProject/stockaffirm") /
    "cache/data/output/2026-06-07/recommendations.csv",
]

@functools.lru_cache(maxsize=1)
def _recs():
    for p in _RECS_PATHS:
        if p.exists():
            out = {}
            try:
                with open(p, newline="") as f:
                    for row in csv.DictReader(f):
                        out[row["ticker"].upper()] = row
                return out
            except Exception:
                pass
    return {}   # standalone mode — caller supplies tickers directly


# ---- financial_history and full_history ------------------------------------
# These reshape the internal fund dict — they don't know or care where the
# data came from (ZIP cache, AV API, or anything else).

def _series(statements, key):
    out = []
    for s in statements or []:
        v = s.get(key)
        if v is not None:
            out.append((s.get("fiscal_year"), float(v)))
    return out


def financial_history(fund):
    """Valuation-engine-friendly annual history (income + balance, no CF)."""
    inc = [s for s in (fund.get("income_statements") or []) if s.get("timeframe") == "annual"]
    bal = [s for s in (fund.get("balance_sheets")    or []) if s.get("timeframe") == "annual"]
    inc.sort(key=lambda s: s.get("fiscal_year", 0), reverse=True)
    bal.sort(key=lambda s: s.get("fiscal_year", 0), reverse=True)
    bal_by_year = {s.get("fiscal_year"): s for s in bal}

    rows = []
    for s in inc:
        fy = s.get("fiscal_year")
        b  = bal_by_year.get(fy, {})
        total_debt = (b.get("debt_current") or 0) + \
                     (b.get("long_term_debt_and_capital_lease_obligations") or 0)
        cash = (b.get("cash_and_equivalents") or 0) + (b.get("short_term_investments") or 0)
        rows.append({
            "fy":           fy,
            "period_end":   s.get("period_end"),
            "revenue":      s.get("revenue"),
            "gross_profit": s.get("gross_profit"),
            "operating_income": s.get("operating_income"),
            "ebitda":       s.get("ebitda"),
            "pretax_income":s.get("income_before_income_taxes"),
            "income_taxes": s.get("income_taxes"),
            "net_income":   s.get("net_income_loss_attributable_common_shareholders"),
            "diluted_shares": s.get("diluted_shares_outstanding"),
            "ppe_net":      b.get("property_plant_equipment_net"),
            "receivables":  b.get("receivables"),
            "inventories":  b.get("inventories"),
            "accounts_payable": b.get("accounts_payable"),
            "deferred_rev": b.get("deferred_revenue_current"),
            "total_debt":   total_debt,
            "cash":         cash,
            "total_equity": b.get("total_equity"),
        })
    return rows


def full_history(fund):
    """
    Distress/fraud screen — full year-indexed history including exact CF data.
    Returns most-recent-first list of dicts.
    """
    inc = [s for s in (fund.get("income_statements") or []) if s.get("timeframe") == "annual"]
    bal = [s for s in (fund.get("balance_sheets")    or []) if s.get("timeframe") == "annual"]
    cf  = [s for s in (fund.get("cash_flows")        or []) if s.get("timeframe") == "annual"]
    inc.sort(key=lambda s: s.get("fiscal_year", 0), reverse=True)
    bal_by = {s.get("fiscal_year"): s for s in bal}
    cf_by  = {s.get("fiscal_year"): s for s in cf}

    def g(d, *keys):
        for k in keys:
            v = d.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
        return None

    rows = []
    for s in inc:
        fy    = s.get("fiscal_year")
        b     = bal_by.get(fy, {})
        c     = cf_by.get(fy, {})
        total_debt = (g(b, "debt_current") or 0) + \
                     (g(b, "long_term_debt_and_capital_lease_obligations") or 0)
        cash       = (g(b, "cash_and_equivalents") or 0) + \
                     (g(b, "short_term_investments") or 0)
        capex      = g(c, "purchase_of_property_plant_and_equipment")
        rows.append({
            "fy":           fy,
            "period_end":   s.get("period_end"),
            # income statement
            "revenue":      g(s, "revenue"),
            "cost_of_revenue": g(s, "cost_of_revenue"),
            "gross_profit": g(s, "gross_profit"),
            "sga":          g(s, "selling_general_administrative"),
            "operating_income": g(s, "operating_income"),
            "ebitda":       g(s, "ebitda"),
            "pretax_income":g(s, "income_before_income_taxes", "pretax_income"),
            "income_taxes": g(s, "income_taxes"),
            "net_income":   g(s, "consolidated_net_income_loss",
                               "net_income_loss_attributable_common_shareholders"),
            "net_income_common": g(s, "net_income_loss_attributable_common_shareholders"),
            "diluted_shares":    g(s, "diluted_shares_outstanding", "basic_shares_outstanding"),
            "other_income_expense": g(s, "total_other_income_expense", "other_income_expense"),
            "interest_expense": g(s, "interest_expense"),
            # balance sheet
            "total_assets":      g(b, "total_assets"),
            "current_assets":    g(b, "total_current_assets"),
            "current_liabilities": g(b, "total_current_liabilities"),
            "retained_earnings": g(b, "retained_earnings_deficit"),
            "total_liabilities": g(b, "total_liabilities"),
            "total_equity":      g(b, "total_equity"),
            "ppe_net":           g(b, "property_plant_equipment_net"),
            "intangibles":       g(b, "intangible_assets_net"),
            "receivables":       g(b, "receivables"),
            "inventories":       g(b, "inventories"),
            "accounts_payable":  g(b, "accounts_payable"),
            "deferred_rev":      g(b, "deferred_revenue_current"),
            "total_debt":        total_debt,
            "long_term_debt":    g(b, "long_term_debt_and_capital_lease_obligations"),
            "cash":              cash,
            "treasury_stock":    g(b, "treasury_stock"),
            # cash flow (exact — not proxied)
            "cfo":   g(c, "net_cash_from_operating_activities",
                        "cash_from_operating_activities_continuing_operations"),
            "dep":   g(c, "depreciation_depletion_and_amortization"),
            "capex": (-capex if capex is not None else None),   # report as positive outflow
            "dividends":        g(c, "dividends"),
            "ltd_issued_repaid":g(c, "long_term_debt_issuances_repayments"),
            "cf_net_income":    g(c, "net_income", "cf_net_income"),
        })
    return rows


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Fetching {t} from Alpha Vantage (cache TTL={CACHE_TTL_HOURS}h, db={CACHE_DB})...")
    f = load_fundamentals(t)
    print("found fundamentals:", bool(f))
    if f:
        h = financial_history(f)
        if h:
            r0 = h[0]
            print(f"{t}: {len(h)} annual periods; latest FY {r0['fy']} "
                  f"rev={r0['revenue']:,.0f}")
        fh = full_history(f)
        if fh:
            r = fh[0]
            print(f"full_history [{r['fy']}]: "
                  f"TA={r.get('total_assets') or 0:,.0f}  "
                  f"CFO={r.get('cfo') or 0:,.0f}  "
                  f"dep={r.get('dep') or 0:,.0f}  "
                  f"capex={r.get('capex') or 0:,.0f}  "
                  f"RE={r.get('retained_earnings') or 0:,.0f}  "
                  f"treasury={r.get('treasury_stock') or 0:,.0f}")
    ctx = load_context(t)
    if ctx:
        print(f"context: sector={ctx['sector']}  mcap=${(ctx['market_cap'] or 0)/1e9:.1f}B  "
              f"name={ctx.get('name')}  shares={ctx.get('shares_outstanding')}")
