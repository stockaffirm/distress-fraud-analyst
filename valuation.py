"""
valuation.py -- the Analyst Agent "brain": a Morningstar-style intrinsic
valuation built from cached fundamentals.

Pipeline (mirrors how a Morningstar analyst works):
  1. Derive normalized economics: FCFF, ROIC, margins, growth, reinvestment.
  2. ECONOMIC MOAT rating (None / Narrow / Wide) from quantitative proxies:
       ROIC-vs-WACC excess spread + how DURABLE it has been + margin level/stability.
  3. MOAT TREND (Positive / Stable / Negative) from recent-vs-older economics.
  4. UNCERTAINTY rating (Low..Extreme) from volatility of margins/growth + leverage.
  5. WACC (cost of equity via CAPM-lite + after-tax cost of debt, market-weighted).
  6. 3-STAGE DCF: explicit (5y) -> fade (moat-governed length) -> perpetuity.
       Excess ROIC persists through the fade window; fade length is the moat's
       mechanical lever (Wide=15y, Narrow=10y, None=5y), exactly Morningstar's design.
  7. FAIR VALUE = PV(FCFF) + cash - debt  ->  equity value.  Compare to market cap.
  8. STAR RATING from price/FVE scaled by the uncertainty-driven margin of safety.

Every assumption is returned so the report is fully auditable. Pure-Python.
"""
import statistics, os, csv, functools
from data_loader import financial_history


RUNTIME_OVERRIDES = {}   # ticker -> {"g1":..,"target_margin":..}; set in-memory by workers


@functools.lru_cache(maxsize=1)
def load_overrides():
    """Per-name analyst overrides (forward growth / mature margin) — the legitimate
    way to reach per-name accuracy: an analyst's researched judgment replacing the
    trailing-data default, exactly as Morningstar analysts override their quant model.
    File: analyst_overrides.csv (ticker,fwd_growth,mature_margin,note)."""
    p = os.path.join(os.path.dirname(__file__), "analyst_overrides.csv")
    out = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            out[r["ticker"].upper()] = {
                "g1": float(r["fwd_growth"]) if r.get("fwd_growth") else None,
                "target_margin": float(r["mature_margin"]) if r.get("mature_margin") else None,
                "uncertainty": (r.get("uncertainty") or "").strip() or None,
                "note": r.get("note", ""),
            }
    return out

# ---- macro assumptions (2026) ---------------------------------------------
RISK_FREE = 0.043          # ~10y UST
EQUITY_RISK_PREMIUM = 0.050
PRETAX_COST_OF_DEBT = 0.055
DEFAULT_TAX = 0.21
TERMINAL_GROWTH = 0.030    # nominal GDP; Morningstar-consensus calibration (was 0.025)

FADE_YEARS = {"Wide": 15, "Narrow": 10, "None": 5}
# terminal ROIC excess over WACC the moat is allowed to keep in perpetuity
TERMINAL_EXCESS = {"Wide": 0.03, "Narrow": 0.01, "None": 0.0}

UNCERTAINTY_MOS = {       # margin of safety: discount to FVE for a 4/5-star buy
    "Low": 0.10, "Medium": 0.20, "High": 0.30, "Very High": 0.40, "Extreme": 0.55,
}
# Sector asset/equity beta (cost-of-equity driver). Calibrated 2026-06-08 so the
# discount rate matches each sector's real systematic risk: defensives (Utilities,
# Staples) discount cheaply; cyclicals/tech carry more. Fixes the Utilities 4.66 /
# Staples 1.66 over-bearishness from the prior flat beta=1.0.
SECTOR_BETA = {
    "Utilities": 0.45, "Consumer Staples": 0.62, "Real Estate": 0.80,
    "Health Care": 0.88, "Communication Services": 0.95, "Financials": 1.05,
    "Industrials": 1.05, "Materials": 1.10, "Energy": 1.12,
    "Consumer Discretionary": 1.15, "Information Technology": 1.20, "Unknown": 1.00,
}
# Uncertainty adds a systematic-risk PREMIUM to cost of equity (Morningstar-style),
# rather than scaling beta -- keeps defensives cheap to discount.
UNCERTAINTY_PREMIUM = {
    "Low": 0.0, "Medium": 0.005, "High": 0.015, "Very High": 0.030, "Extreme": 0.050,
}
# Morningstar does NOT use CAPM beta -- it sets cost of equity DIRECTLY from its
# Uncertainty rating (their published systematic-risk buckets). This is the faithful
# method and stops us over-discounting wide-moat mega-caps (AAPL WACC 10.7%->~8%).
COST_OF_EQUITY = {     # Morningstar's actual systematic-risk buckets (consensus calib)
    "Low": 0.065, "Medium": 0.075, "High": 0.090, "Very High": 0.110, "Extreme": 0.135,
}


def _safe_div(a, b):
    return a / b if (a is not None and b not in (None, 0)) else None


def _cagr(first, last, years):
    if first is None or last is None or first <= 0 or last <= 0 or years <= 0:
        return None
    return (last / first) ** (1 / years) - 1


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
def derive_economics(hist):
    """Per-year derived economics, newest-first, + normalized summaries."""
    yrs = []
    for i, r in enumerate(hist):
        rev = r["revenue"]
        op = r["operating_income"]
        ebitda = r["ebitda"]
        tax_rate = _clamp((_safe_div(r["income_taxes"], r["pretax_income"]) or DEFAULT_TAX), 0.0, 0.35)
        nopat = op * (1 - tax_rate) if op is not None else None
        da = (ebitda - op) if (ebitda is not None and op is not None and ebitda > op) else (
            0.04 * rev if rev else None)  # fallback D&A ~4% of revenue
        invested = None
        if r["total_equity"] is not None:
            invested = r["total_equity"] + (r["total_debt"] or 0) - (r["cash"] or 0)
        roic = _safe_div(nopat, invested) if (invested and invested > 0) else None

        # capex proxy = net PP&E change + D&A ; dWC from operating items
        capex = dwc = fcff = None
        if i + 1 < len(hist):
            p = hist[i + 1]
            if r["ppe_net"] is not None and p["ppe_net"] is not None and da is not None:
                capex = max((r["ppe_net"] - p["ppe_net"]) + da, 0.0)
            def wc(x):
                return ((x["receivables"] or 0) + (x["inventories"] or 0)
                        - (x["accounts_payable"] or 0) - (x["deferred_rev"] or 0))
            dwc = wc(r) - wc(p)
            if None not in (nopat, da, capex):
                fcff = nopat + da - capex - dwc

        yrs.append({
            "fy": r["fy"], "revenue": rev,
            "op_margin": _safe_div(op, rev),
            "gross_margin": _safe_div(r["gross_profit"], rev),
            "tax_rate": tax_rate, "nopat": nopat, "roic": roic,
            "fcff": fcff, "shares": r["diluted_shares"],
            "total_debt": r["total_debt"], "cash": r["cash"],
            "net_income": r["net_income"],
        })

    rev_series = [y["revenue"] for y in yrs if y["revenue"]]
    roics = [y["roic"] for y in yrs if y["roic"] is not None]
    opm = [y["op_margin"] for y in yrs if y["op_margin"] is not None]
    gm = [y["gross_margin"] for y in yrs if y["gross_margin"] is not None]
    opm_peak = (sorted(opm)[int(0.75 * (len(opm) - 1))] if opm else None)  # p75, ignore spikes

    n = len(rev_series)
    rev_cagr_5 = _cagr(rev_series[min(4, n - 1)], rev_series[0], min(4, n - 1)) if n >= 2 else None
    rev_cagr_3 = _cagr(rev_series[min(2, n - 1)], rev_series[0], min(2, n - 1)) if n >= 2 else None

    norm = {
        "rev_cagr_5": rev_cagr_5,
        "rev_cagr_3": rev_cagr_3,
        "roic_median": statistics.median(roics) if roics else None,
        "roic_recent": statistics.median(roics[:3]) if len(roics) >= 1 else None,
        "roic_old": statistics.median(roics[3:6]) if len(roics) >= 4 else None,
        "opm_median": statistics.median(opm) if opm else None,
        "opm_recent": statistics.median(opm[:3]) if opm else None,
        "opm_old": statistics.median(opm[3:6]) if len(opm) >= 4 else None,
        "opm_peak": opm_peak,
        "gm_median": statistics.median(gm) if gm else None,
        "opm_stdev": statistics.pstdev(opm) if len(opm) >= 3 else None,
        "rev_growth_stdev": _growth_stdev(rev_series),
        "years_positive_roic": sum(1 for y in yrs if (y["roic"] or 0) > 0),
        "n_years": n,
        "latest_shares": next((y["shares"] for y in yrs if y["shares"]), None),
        "latest_debt": yrs[0]["total_debt"] or 0,
        "latest_cash": yrs[0]["cash"] or 0,
    }
    return yrs, norm


def _growth_stdev(rev_series):
    g = []
    for i in range(len(rev_series) - 1):
        if rev_series[i + 1]:
            g.append(rev_series[i] / rev_series[i + 1] - 1)
    return statistics.pstdev(g) if len(g) >= 3 else None


# ---------------------------------------------------------------------------
def assess_moat(norm, wacc_guess=0.09):
    """Economic moat from ROIC excess + durability + margin profile."""
    roic = norm["roic_median"]
    gm = norm["gm_median"] or 0
    g5 = norm.get("rev_cagr_5") or 0
    scalable = gm > 0.60 and g5 > 0.10           # high-GM business still scaling fast
    # ROIC may be None/negative for young reinvestors or buyback-distorted equity;
    # don't bail before the scalable check (that mis-rated CRWD "None" vs MS Wide).
    if roic is None:
        if scalable:
            return "Narrow", (f"ROIC not computable but scalable: gross margin {gm*100:.0f}%, "
                              f"5y growth {g5*100:.0f}% -> reinvestment-suppressed moat"), 2.0
        return "None", "no positive invested-capital returns computable", 0.0
    excess = roic - wacc_guess
    durable = norm["years_positive_roic"] >= 8
    stable = (norm["opm_stdev"] is None) or (norm["opm_stdev"] < 0.05)

    score = 0.0
    score += _clamp(excess / 0.10, -1, 2)        # excess returns (dominant)
    score += 1.0 if durable else 0.0             # durability
    score += 0.5 if gm > 0.45 else 0.0           # pricing power proxy
    score += 0.5 if stable else 0.0              # earnings stability
    # young high-gross-margin compounders have moats (network/switching/scale) that
    # today's reinvestment-suppressed ROIC understates -- credit them so CRWD/PANW/
    # AMD-type names aren't mis-rated "None" (validated vs Morningstar 2026-06-08)
    score += 1.0 if scalable else 0.0

    # Thresholds calibrated 2026-06-08 toward Morningstar's ~10/40/50 Wide/Narrow/None
    # mix (prior 7/18/75 was too strict -> too many "None" -> over-short fade windows).
    if (score >= 2.6 and excess > 0.08 and durable) or (scalable and score >= 2.8):
        rating = "Wide"
    elif (excess > 0.0 and (score >= 0.7 or durable)) or scalable:
        rating = "Narrow"
    else:
        rating = "None"
    reason = (f"median ROIC {roic*100:.1f}% vs ~WACC {wacc_guess*100:.1f}% "
              f"(excess {excess*100:+.1f}pp), {norm['years_positive_roic']}/{norm['n_years']}y positive, "
              f"gross margin {gm*100:.0f}%, op-margin stdev "
              f"{(norm['opm_stdev'] or 0)*100:.1f}pp")
    return rating, reason, score


def assess_moat_trend(norm):
    rr, ro = norm["roic_recent"], norm["roic_old"]
    mr, mo = norm["opm_recent"], norm["opm_old"]
    if None in (rr, ro):
        return "Stable", "insufficient history"
    droic = rr - ro
    dmargin = (mr - mo) if None not in (mr, mo) else 0
    if droic > 0.02 or (droic > 0 and dmargin > 0.01):
        return "Positive", f"ROIC {ro*100:.1f}%->{rr*100:.1f}%, op-margin {(mo or 0)*100:.1f}->{(mr or 0)*100:.1f}%"
    if droic < -0.02 or (droic < 0 and dmargin < -0.01):
        return "Negative", f"ROIC {ro*100:.1f}%->{rr*100:.1f}%, op-margin {(mo or 0)*100:.1f}->{(mr or 0)*100:.1f}%"
    return "Stable", f"ROIC {ro*100:.1f}%->{rr*100:.1f}%"


def assess_uncertainty(norm, ctx):
    """Fair-value uncertainty -> margin of safety band. Calibrated to LOOK THROUGH
    the cycle (Morningstar-style): commodity/cyclical margin swings don't make a
    durable franchise 'Very High'. Most large names land Medium, as at Morningstar."""
    pts = 0
    om = norm["opm_stdev"]
    if om is not None:
        pts += 0 if om < 0.03 else 1 if om < 0.06 else 2 if om < 0.11 else 3
    gv = norm["rev_growth_stdev"]
    if gv is not None:
        pts += 0 if gv < 0.08 else 1 if gv < 0.20 else 2     # cap 2: look through cycle
    # leverage
    debt, cash = norm["latest_debt"], norm["latest_cash"]
    nd = debt - cash
    mc = ctx.get("market_cap") or 0
    if mc and nd > 0:
        lev = nd / mc
        pts += 0 if lev < 0.20 else 1 if lev < 0.55 else 2
    # profitability cushion (only genuinely thin)
    if (norm["roic_median"] or 0) < 0.03:
        pts += 1
    if (norm["opm_median"] or 0) < 0.03:
        pts += 1
    # large, durable, scaled businesses are inherently lower-uncertainty
    if (mc > 50e9) and norm["years_positive_roic"] >= 8:
        pts -= 1
    pts = max(pts, 0)
    rating = ("Low" if pts <= 1 else "Medium" if pts <= 4 else
              "High" if pts <= 6 else "Very High" if pts <= 8 else "Extreme")
    return rating, pts


def compute_wacc(norm, ctx, uncertainty):
    # Morningstar method: cost of equity straight from the Uncertainty bucket.
    ke = COST_OF_EQUITY[uncertainty]
    if ctx.get("sector") == "Utilities":
        ke = min(ke, COST_OF_EQUITY["Low"])     # regulated franchise = low systematic risk
    beta = (ke - RISK_FREE) / EQUITY_RISK_PREMIUM         # implied beta, for display
    kd = PRETAX_COST_OF_DEBT * (1 - DEFAULT_TAX)
    e = ctx.get("market_cap") or 0
    d = norm["latest_debt"] or 0
    tot = e + d
    if tot <= 0:
        return ke, beta, ke, kd
    wacc = (e / tot) * ke + (d / tot) * kd
    return wacc, beta, ke, kd


# ---------------------------------------------------------------------------
def _equity_value(rev_latest, margin_start, margin_target, ramp_years, tax,
                  roic_norm, wacc, moat, g1, fade_n, net_debt, explicit_n=5,
                  want_schedule=False):
    """Core 3-stage FCFF DCF -> equity value (refactored so it can be inverted).

    Operating margin RAMPS linearly from margin_start (today) to margin_target
    (mature) over ramp_years -- this is the margin-expansion fix that lets young
    high-gross-margin growers be valued on their mature economics, not today's
    depressed margin (the root cause of the 0.37x under-valuation vs Morningstar).
    """
    def reinvest_rate(g, roic):
        # g/ROIC identity assumes ALL growth is bought with reinvested capital;
        # real firms also grow via pricing/operating leverage, so cap the drag at
        # 0.70 (calibrated 2026-06-08).
        return _clamp(g / roic, 0.0, 0.60) if roic > 0 else 0.45

    def margin_at(t):
        return margin_start + (margin_target - margin_start) * min(t / ramp_years, 1.0)

    pv = 0.0
    rev = rev_latest
    disc = 1.0
    sched = []
    for t in range(1, explicit_n + 1):          # Stage 1: explicit high-growth
        rev *= (1 + g1)
        fcff = rev * margin_at(t) * (1 - tax) * (1 - reinvest_rate(g1, roic_norm))
        disc *= (1 + wacc)
        pv += fcff / disc
        if want_schedule:
            sched.append((t, g1, rev, fcff, fcff / disc))
    roic_term = wacc + TERMINAL_EXCESS[moat]
    for k in range(1, fade_n + 1):              # Stage 2: fade
        g = g1 + (TERMINAL_GROWTH - g1) * (k / fade_n)
        roic_k = roic_norm + (roic_term - roic_norm) * (k / fade_n)
        rev *= (1 + g)
        fcff = rev * margin_at(explicit_n + k) * (1 - tax) * (1 - reinvest_rate(g, roic_k))
        disc *= (1 + wacc)
        pv += fcff / disc
        if want_schedule:
            sched.append((explicit_n + k, g, rev, fcff, fcff / disc))
    nopat_term = rev * (1 + TERMINAL_GROWTH) * margin_target * (1 - tax)  # Stage 3
    fcff_term = nopat_term * (1 - reinvest_rate(TERMINAL_GROWTH, roic_term))
    tv = fcff_term / (wacc - TERMINAL_GROWTH)
    pv_tv = tv / disc
    ev = pv + pv_tv
    return ev, ev + net_debt_adj(net_debt), pv_tv, roic_term, sched


def net_debt_adj(net_debt):
    # equity = EV - debt + cash ; net_debt passed as (debt - cash) so subtract
    return -net_debt


def dcf(norm, ctx, moat, uncertainty):
    """3-stage FCFF DCF + reverse-DCF + sensitivity. Returns full audit dict."""
    wacc, beta, ke, kd = compute_wacc(norm, ctx, uncertainty)
    yrs = ctx["_yrs"]
    rev_latest = yrs[0]["revenue"]
    tax = yrs[0]["tax_rate"]
    net_debt = (norm["latest_debt"] or 0) - (norm["latest_cash"] or 0)
    fade_n = FADE_YEARS[moat]

    # ---- MATURE operating-margin target (margin-expansion model) ------------
    recent_margin = norm["opm_recent"] or norm["opm_median"] or 0.08
    gm = norm["gm_median"] or 0
    peak = norm["opm_peak"] or recent_margin
    # high-gross-margin businesses mature to a fraction of gross margin even if
    # today's operating margin is thin (software/platforms reinvesting for growth)
    if gm > 0.65:
        gm_mature = 0.42 * gm          # best-in-class software matures to ~40%+ op margin
    elif gm > 0.55:
        gm_mature = 0.34 * gm
    elif gm > 0.40:
        gm_mature = 0.22 * gm
    else:
        gm_mature = 0.0
    target_margin = max(recent_margin, peak, gm_mature)
    if gm > 0:
        target_margin = min(target_margin, 0.90 * gm)   # can't exceed gross margin
    target_margin = _clamp(target_margin, 0.02, 0.45)
    margin_start = _clamp(recent_margin, -0.10, target_margin)
    expanding = target_margin > recent_margin + 0.03
    ramp_years = 6.0 if expanding else 1.0

    # ROIC for reinvestment: mature high-margin growers earn high returns at scale,
    # so don't let today's reinvestment-suppressed ROIC understate it.
    roic_norm = _clamp(norm["roic_median"] or wacc, 0.02, 0.60)
    if expanding:
        roic_norm = max(roic_norm, wacc + 0.06)
    if ctx.get("sector") == "Utilities":
        # regulated allowed return sits just above cost of capital -> growth into the
        # rate base is roughly value-neutral, not value-destroying as a 6% ROIC implies
        roic_norm = max(roic_norm, wacc + 0.015)
    if gm > 0.65:
        # asset-light software/platforms earn very high returns on the little CAPITAL
        # they use (growth is funded via opex S&M/R&D, already inside margin) -> the
        # g/ROIC reinvestment identity must NOT double-count it. Floor ROIC high so
        # reinvestment drag is low. (fixes PANW/CRWD-type software under-valuation)
        roic_norm = max(roic_norm, 0.40)

    # Base growth: blend 5y & 3y trend, light 5% haircut, cap 25%, floor at terminal.
    # Calibrated up from prior (0.85 haircut / 0.20 cap) which left a systematic
    # +11pp gap vs market-implied growth across the population.
    g5, g3 = norm["rev_cagr_5"], norm["rev_cagr_3"]
    base = (0.6 * g5 + 0.4 * g3) if (g5 is not None and g3 is not None) else (g5 or g3 or 0.04)
    # Moaty hyper-growth names get a LONGER, HIGHER growth runway (8y explicit, 32%
    # cap) instead of being crushed to 25%/5y -- the remaining cause of NVDA/CRWD-type
    # under-valuation vs Morningstar (validated 2026-06-08).
    high_growth = base > 0.20 and moat in ("Wide", "Narrow")
    cap = 0.28 if high_growth else 0.25                  # reined in from 0.32 (CAVA/NVDA 5x overshoot)
    explicit_n = 6 if high_growth else 5                 # shorter high-growth runway (was 8)
    g1 = _clamp(base, TERMINAL_GROWTH, cap)              # no haircut (consensus calib)

    # ---- per-name analyst OVERRIDE (researched forward judgment) -------------
    tk = (ctx.get("ticker") or "").upper()
    ov = dict(load_overrides().get(tk) or {})
    rt = RUNTIME_OVERRIDES.get(tk)            # in-memory override (workflow workers)
    if rt:
        ov.update({k: v for k, v in rt.items() if v is not None})
    override_note = None
    if ov:
        if ov.get("g1") is not None:
            g1 = ov["g1"]
        if ov.get("target_margin") is not None:
            target_margin = ov["target_margin"]
            margin_start = _clamp(recent_margin, -0.10, target_margin)
            ramp_years = 6.0 if target_margin > recent_margin + 0.03 else 1.0
        override_note = ov.get("note")

    ev, equity_value, pv_tv, roic_term, sched = _equity_value(
        rev_latest, margin_start, target_margin, ramp_years, tax, roic_norm,
        wacc, moat, g1, fade_n, net_debt, explicit_n=explicit_n, want_schedule=True)
    shares = norm["latest_shares"]
    fv_per_share = _safe_div(equity_value, shares)

    # ---- reverse DCF: stage-1 growth implied by today's market cap ----------
    implied_g = None
    mc = ctx.get("market_cap")
    if mc and mc > 0:
        lo, hi = -0.10, 0.40
        for _ in range(60):
            mid = (lo + hi) / 2
            _, eqv, *_ = _equity_value(rev_latest, margin_start, target_margin,
                                       ramp_years, tax, roic_norm, wacc, moat, mid,
                                       fade_n, net_debt, explicit_n=explicit_n)
            if eqv > mc:
                hi = mid
            else:
                lo = mid
        implied_g = (lo + hi) / 2

    # ---- sensitivity grid: equity value across g1 +/- and wacc +/- ---------
    sens = []
    for dg in (-0.02, 0.0, 0.02):
        row = []
        for dw in (-0.01, 0.0, 0.01):
            _, eqv, *_ = _equity_value(rev_latest, margin_start, target_margin,
                                       ramp_years, tax, roic_norm,
                                       max(wacc + dw, TERMINAL_GROWTH + 0.01), moat,
                                       _clamp(g1 + dg, 0.0, cap), fade_n, net_debt,
                                       explicit_n=explicit_n)
            row.append(eqv)
        sens.append((dg, _clamp(g1 + dg, 0.0, 0.25), row))

    return {
        "wacc": wacc, "beta": beta, "ke": ke, "kd": kd,
        "g1": g1, "fade_years": fade_n, "target_margin": target_margin,
        "roic_norm": roic_norm, "roic_terminal": roic_term,
        "ev": ev, "pv_explicit_fade": ev - pv_tv, "pv_terminal": pv_tv,
        "terminal_pct": pv_tv / ev if ev else None,
        "equity_value": equity_value, "fv_per_share": fv_per_share,
        "shares": shares, "schedule": sched,
        "implied_g": implied_g, "sensitivity": sens, "net_debt": net_debt,
        "override": override_note,
    }


def star_rating(equity_value, market_cap, uncertainty):
    """Morningstar-style: price/FVE scaled by uncertainty margin of safety."""
    if not market_cap or not equity_value or equity_value <= 0:
        return None, None
    pf = market_cap / equity_value          # price-to-fair-value
    mos = UNCERTAINTY_MOS[uncertainty]
    # 5-star at >=mos discount, 1-star at >=mos premium, linear bands
    if pf <= 1 - mos:
        stars = 5
    elif pf <= 1 - mos / 2:
        stars = 4
    elif pf < 1 + mos / 2:
        stars = 3
    elif pf < 1 + mos:
        stars = 2
    else:
        stars = 1
    return stars, pf


# ---------------------------------------------------------------------------
# Sectors where an enterprise FCFF DCF is NOT valid (deposits/float are operating,
# leverage is the business). Morningstar values these with excess-return / DDM models.
DCF_NA_SECTORS = {"Financials", "Real Estate"}
MOAT_RANK = {"None": 0, "Narrow": 1, "Wide": 2}


def _sector_moat_floor(ctx, norm, moat):
    """Morningstar gives regulated utilities and large cost-advantage energy/
    midstream a moat from their FRANCHISE, not from excess ROIC (which a pure
    ROIC-vs-WACC test misses). Floor those to Narrow when returns are durable."""
    sec = ctx.get("sector"); mc = ctx.get("market_cap") or 0
    durable = norm["years_positive_roic"] >= 7
    floor = None
    if sec == "Utilities" and durable:
        floor = "Narrow"                       # regulated/efficient-scale franchise
    elif sec == "Energy" and mc > 40e9 and durable:
        floor = "Narrow"                       # integrated major / large midstream: cost advantage / scale
    if floor and MOAT_RANK[moat] < MOAT_RANK[floor]:
        return floor, f" | floored to {floor}: {sec} franchise moat (ROIC test understates)"
    return moat, ""


def analyze(ticker, ctx, hist):
    dcf_applicable = ctx.get("sector") not in DCF_NA_SECTORS
    yrs, norm = derive_economics(hist)
    # first-pass WACC guess for moat, then refine
    moat0, _, _ = assess_moat(norm)
    uncertainty, upts = assess_uncertainty(norm, ctx)
    # analyst UNCERTAINTY override (qualitative risk the model can't see: regulatory,
    # litigation, political, accounting). Mirrors Morningstar's analyst-set uncertainty.
    _tk = (ctx.get("ticker") or "").upper()
    _unc = (RUNTIME_OVERRIDES.get(_tk) or {}).get("uncertainty") or \
           (load_overrides().get(_tk) or {}).get("uncertainty")
    if _unc in COST_OF_EQUITY:
        uncertainty = _unc
    wacc_guess, *_ = compute_wacc(norm, ctx, uncertainty)
    moat, moat_reason, moat_score = assess_moat(norm, wacc_guess)
    moat, floor_note = _sector_moat_floor(ctx, norm, moat)
    moat_reason += floor_note
    trend, trend_reason = assess_moat_trend(norm)
    ctx["_yrs"] = yrs
    val = dcf(norm, ctx, moat, uncertainty)
    stars, pf = star_rating(val["equity_value"], ctx.get("market_cap"), uncertainty)

    # ---- out-of-model detection: names a fundamentals DCF structurally can't value
    oom = []
    revs = [y["revenue"] for y in yrs if y["revenue"]]
    # spin-off/restructuring = a big single-year COLLAPSE in revenue (not a cyclical
    # swing, which goes both ways). Drop = older>newer by >45%.
    max_drop = max(((revs[i + 1] - revs[i]) / revs[i + 1] for i in range(len(revs) - 1)
                    if revs[i + 1]), default=0)
    if max_drop > 0.45:
        oom.append("revenue collapsed >45% in a year (spin-off / restructuring)")
    if val["implied_g"] is not None and val["implied_g"] >= 0.40:
        oom.append("market prices >=40% growth (extreme optionality beyond fundamentals)")
    mc = ctx.get("market_cap")
    if mc and val["equity_value"] and val["equity_value"] < 0.18 * mc:
        oom.append("model fair value <18% of price (optionality / ADR / data-distorted)")
    return {
        "ticker": ticker, "ctx": ctx, "norm": norm, "yrs": yrs,
        "moat": moat, "moat_reason": moat_reason, "moat_score": moat_score,
        "moat_trend": trend, "moat_trend_reason": trend_reason,
        "uncertainty": uncertainty, "uncertainty_points": upts,
        "valuation": val, "stars": stars, "price_to_fv": pf,
        "margin_of_safety": UNCERTAINTY_MOS[uncertainty],
        "dcf_applicable": dcf_applicable,
        "out_of_model": bool(oom), "out_of_model_reasons": oom,
    }
