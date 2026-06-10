"""
data_loader.py  -- Analyst Agent data layer (READ-ONLY)

Loads a ticker's cached fundamentals (10yr annual income statements + balance
sheets) from the StockAffirm raw cache, plus market-cap / sector / Street context
from the engine's recommendations.csv.

NOTHING here writes to the engine. Pure read. Pure-Python (no pandas).
"""
import os, csv, json, zipfile, glob, functools

# ---- paths -----------------------------------------------------------------
ENGINE = "/Users/prasadmenon/Claude/StockAffirmProject/stockaffirm"
FUND_ZIP_DIR = os.path.join(ENGINE, "cache/data/raw/fundamentals_annual_zips")
RECS_CSV = os.path.join(ENGINE, "cache/data/output/2026-06-07/recommendations.csv")


# ---- fundamentals zip index ------------------------------------------------
@functools.lru_cache(maxsize=1)
def _zip_index():
    """Map TICKER -> zip path by scanning member names once."""
    idx = {}
    for z in sorted(glob.glob(os.path.join(FUND_ZIP_DIR, "*.zip"))):
        try:
            for name in zipfile.ZipFile(z).namelist():
                if name.endswith(".json"):
                    idx.setdefault(name[:-5].upper(), z)
        except zipfile.BadZipFile:
            continue
    return idx


def load_fundamentals(ticker):
    """Return parsed fundamentals dict for ticker, or None."""
    t = ticker.upper()
    z = _zip_index().get(t)
    if not z:
        return None
    with zipfile.ZipFile(z) as zf:
        return json.loads(zf.read(t + ".json"))


# ---- engine / Street context ----------------------------------------------
@functools.lru_cache(maxsize=1)
def _recs():
    out = {}
    with open(RECS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            out[row["ticker"].upper()] = row
    return out


def _num(v):
    try:
        if v in (None, "", "None", "nan", "NaN"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def load_context(ticker):
    """market_cap, sector, Street consensus, engine composite for a ticker."""
    r = _recs().get(ticker.upper())
    if not r:
        return None
    return {
        "ticker": ticker.upper(),
        "sector": r.get("sector") or "Unknown",
        "market_cap": _num(r.get("market_cap")),
        "trailing_pe": _num(r.get("trailing_pe")),
        "n_analysts": _num(r.get("n_analysts")),
        "rec_mean": _num(r.get("rec_mean")),
        "target_upside": _num(r.get("target_upside")),
        "engine_composite": _num(r.get("composite")),
        "engine_tier": r.get("default_tier"),
        "piotroski_f": _num(r.get("piotroski_f")),
        "altman_z": _num(r.get("altman_z")),
    }


# ---- normalized financial series -------------------------------------------
def _series(statements, key):
    """List of (fiscal_year, value) newest-first, skipping None."""
    out = []
    for s in statements or []:
        v = s.get(key)
        if v is not None:
            out.append((s.get("fiscal_year"), float(v)))
    return out


def financial_history(fund):
    """
    Re-shape raw fundamentals into a clean, year-indexed history dict:
        years -> [most-recent-first fiscal years]
        per-year dict of the income + balance fields the model needs.
    Annual statements only.
    """
    inc = [s for s in (fund.get("income_statements") or []) if s.get("timeframe") == "annual"]
    bal = [s for s in (fund.get("balance_sheets") or []) if s.get("timeframe") == "annual"]
    inc.sort(key=lambda s: s.get("fiscal_year", 0), reverse=True)
    bal.sort(key=lambda s: s.get("fiscal_year", 0), reverse=True)
    bal_by_year = {s.get("fiscal_year"): s for s in bal}

    rows = []
    for s in inc:
        fy = s.get("fiscal_year")
        b = bal_by_year.get(fy, {})
        total_debt = (b.get("debt_current") or 0) + (b.get("long_term_debt_and_capital_lease_obligations") or 0)
        cash = (b.get("cash_and_equivalents") or 0) + (b.get("short_term_investments") or 0)
        rows.append({
            "fy": fy,
            "period_end": s.get("period_end"),
            "revenue": s.get("revenue"),
            "gross_profit": s.get("gross_profit"),
            "operating_income": s.get("operating_income"),
            "ebitda": s.get("ebitda"),
            "pretax_income": s.get("income_before_income_taxes"),
            "income_taxes": s.get("income_taxes"),
            "net_income": s.get("net_income_loss_attributable_common_shareholders"),
            "diluted_shares": s.get("diluted_shares_outstanding"),
            "ppe_net": b.get("property_plant_equipment_net"),
            "receivables": b.get("receivables"),
            "inventories": b.get("inventories"),
            "accounts_payable": b.get("accounts_payable"),
            "deferred_rev": b.get("deferred_revenue_current"),
            "total_debt": total_debt,
            "cash": cash,
            "total_equity": b.get("total_equity"),
        })
    return rows


def full_history(fund):
    """
    Richer year-indexed history for the DISTRESS / FRAUD screen.

    Exposes the balance-sheet *and* cash-flow line items that `financial_history`
    leaves out (total assets, current assets/liabilities, retained earnings,
    total liabilities, intangibles, SG&A, CFO, real D&A, real capex). This is
    ADDITIVE — `financial_history` (used by the valuation engine) is untouched.

    Cash-flow statements ARE cached under the top-level `cash_flows` key, so
    accruals / Beneish TATA / FCF here are *exact*, not proxied.
    Returns most-recent-first.
    """
    inc = [s for s in (fund.get("income_statements") or []) if s.get("timeframe") == "annual"]
    bal = [s for s in (fund.get("balance_sheets") or []) if s.get("timeframe") == "annual"]
    cf  = [s for s in (fund.get("cash_flows") or []) if s.get("timeframe") == "annual"]
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
        fy = s.get("fiscal_year")
        b = bal_by.get(fy, {})
        c = cf_by.get(fy, {})
        total_debt = (g(b, "debt_current") or 0) + (g(b, "long_term_debt_and_capital_lease_obligations") or 0)
        cash = (g(b, "cash_and_equivalents") or 0) + (g(b, "short_term_investments") or 0)
        capex = g(c, "purchase_of_property_plant_and_equipment")  # usually negative
        rows.append({
            "fy": fy,
            "period_end": s.get("period_end"),
            # ---- income statement ----
            "revenue": g(s, "revenue"),
            "cost_of_revenue": g(s, "cost_of_revenue"),
            "gross_profit": g(s, "gross_profit"),
            "sga": g(s, "selling_general_administrative"),
            "operating_income": g(s, "operating_income"),   # EBIT proxy
            "ebitda": g(s, "ebitda"),
            "pretax_income": g(s, "income_before_income_taxes"),
            "income_taxes": g(s, "income_taxes"),
            "net_income": g(s, "consolidated_net_income_loss",
                            "net_income_loss_attributable_common_shareholders"),
            "net_income_common": g(s, "net_income_loss_attributable_common_shareholders"),
            "diluted_shares": g(s, "diluted_shares_outstanding", "basic_shares_outstanding"),
            "other_income_expense": g(s, "total_other_income_expense", "other_income_expense"),
            # ---- balance sheet ----
            "total_assets": g(b, "total_assets"),
            "current_assets": g(b, "total_current_assets"),
            "current_liabilities": g(b, "total_current_liabilities"),
            "retained_earnings": g(b, "retained_earnings_deficit"),
            "total_liabilities": g(b, "total_liabilities"),
            "total_equity": g(b, "total_equity"),
            "ppe_net": g(b, "property_plant_equipment_net"),
            "intangibles": g(b, "intangible_assets_net"),
            "receivables": g(b, "receivables"),
            "inventories": g(b, "inventories"),
            "accounts_payable": g(b, "accounts_payable"),
            "deferred_rev": g(b, "deferred_revenue_current"),
            "total_debt": total_debt,
            "long_term_debt": g(b, "long_term_debt_and_capital_lease_obligations"),
            "cash": cash,
            # ---- cash flow (exact) ----
            "cfo": g(c, "net_cash_from_operating_activities",
                     "cash_from_operating_activities_continuing_operations"),
            "dep": g(c, "depreciation_depletion_and_amortization"),
            "capex": (-capex if capex is not None else None),   # report as positive outflow
            "dividends": g(c, "dividends"),
            "ltd_issued_repaid": g(c, "long_term_debt_issuances_repayments"),
            "cf_net_income": g(c, "net_income"),
        })
    return rows


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    f = load_fundamentals(t)
    print("found fundamentals:", bool(f))
    if f:
        h = financial_history(f)
        print(f"{t}: {len(h)} annual periods; latest FY {h[0]['fy']} rev={h[0]['revenue']:,.0f}")
        fh = full_history(f)
        r = fh[0]
        print(f"full_history latest: TA={r['total_assets']:,.0f} CFO={r['cfo']:,.0f} "
              f"dep={r['dep']:,.0f} capex={r['capex']:,.0f} RE={r['retained_earnings']:,.0f}")
    print("context:", load_context(t))
