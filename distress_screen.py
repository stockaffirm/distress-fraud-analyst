#!/usr/bin/env python3
"""
distress_screen.py -- Distress & Fraud screening SUBAGENT for the Analyst Agent.

Goal (per request): two things you want to AVOID, and one you want to watch:
  1. AVOID -- BANKRUPTCY RISK : firms on the verge of insolvency.
  2. AVOID -- FRAUD / MANIPULATION RISK : firms juicing the numbers.
  3. DISTRESSED-BUT-RECOVERABLE : badly stressed, but solvent with a turnaround
     vector (still throws off operating cash, deleveraging, margins/revenue
     troughing, assets cover the debt) -> can recover slowly.

It composes several peer-reviewed, decades-tested models rather than one score,
because each catches a different failure mode and any one alone false-flags
healthy names (e.g. Altman alone condemns buyback-heavy mega-caps with negative
book equity). A name is only bucketed AVOID when MULTIPLE corroborating signals
agree -- the same multi-signal discipline the valuation agent uses.

Models:
  * Altman Z''-Score (Altman 1968/2000)   -> bankruptcy distance (book, cross-sector)
  * Altman original Z  (where market cap)  -> bankruptcy distance (market-value)
  * Beneish M-Score (Beneish 1999)         -> earnings manipulation (the Enron catcher)
  * Ohlson O-Score (Ohlson 1980)           -> bankruptcy probability (logit) [corroborating]
  * Sloan accruals (Sloan 1996)            -> earnings quality
  * Montier C-Score (Montier 2008)         -> 6 manipulation flags
  * Liquidity / leverage / cash-runway     -> hard solvency signals
  * Recovery signals                       -> the turnaround vector

Cash-flow statements ARE cached, so accruals / Beneish-TATA / FCF are EXACT here.

  python3 distress_screen.py TSLA
  python3 distress_screen.py CCL AAL F GME   # several
  python3 distress_screen.py --json TSLA      # raw dict

Constants are all at the top, auditable and calibratable, mirroring valuation.py.
"""
import sys, json, math, statistics
from data_loader import load_fundamentals, load_context, full_history

# ============================ CALIBRATED CONSTANTS ==========================
# --- Altman Z'' (non-manufacturer / cross-sector; book value) ---
Z2_SAFE      = 2.6     # Z'' > 2.6  -> safe
Z2_DISTRESS  = 1.1     # Z'' < 1.1  -> distress zone
# --- Altman original Z (manufacturer; market value of equity) ---
Z_SAFE       = 2.99
Z_DISTRESS   = 1.81
# --- Beneish M-Score (8-variable) ---
M_THRESHOLD  = -1.78   # M > -1.78 -> likely earnings manipulator
# --- Ohlson O-Score ---
O_HIGH_PROB  = 0.50    # P(default) > 0.5
# --- Sloan accruals ---
ACCRUAL_HI   = 0.10    # |accruals/avg-assets| > 10% -> aggressive
FRAUD_ACCRUAL_MIN = 0.08   # min POSITIVE accruals to call a high-Beneish name manipulation
                           # (necessary condition -- screens out cash-backed fast growers)
CASH_CONV_FLOOR  = 0.70    # cum CFO must be >= 70% of cum NI over ~4y, else "can't
                           # convert earnings to cash" -- the real manipulation signature
# --- Montier C-Score ---
C_HIGH       = 4       # >= 4 of 6 flags -> manipulation risk
# --- liquidity / leverage hard signals ---
ND_EBITDA_SEVERE = 8.0
ND_EBITDA_HIGH   = 5.0
CASH_RUNWAY_MIN  = 12.0   # months
CURRENT_RATIO_LOW = 1.0
LONG_RUNWAY      = 24.0    # months of cash cushion that rules out near-term bankruptcy
# --- recovery gate ---
RECOVERY_MIN_SIGNALS = 3

FIN_SECTORS = {"Financials", "Financial Services", "Real Estate"}
# Sectors that carry high leverage / low Altman by DESIGN (regulated or balance-sheet
# businesses). For these, leverage + Altman are NOT bankruptcy signals on their own --
# judge them on cash flow, losses, and accumulated-deficit insolvency instead.
LEVERED_SECTORS = FIN_SECTORS | {"Utilities"}
OHLSON_SEVERE = 0.70   # P(default) above which Ohlson counts as a hard signal
RUNWAY_SHORT  = 18.0   # months of operating-cash runway that flags imminent stress


# ================================ helpers ===================================
def _div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b

def _safe(*vals):
    return all(v is not None for v in vals)


# ============================ MODEL: Altman =================================
def altman(hist, market_cap=None):
    """Altman Z'' (book, cross-sector primary) + original Z (market, when cap known)."""
    r = hist[0]
    ta = r["total_assets"]
    if not ta or ta <= 0:
        return {"z2": None, "z_orig": None, "zone": None}
    wc   = _div((r["current_assets"] or 0) - (r["current_liabilities"] or 0), ta)   # X1
    re   = _div(r["retained_earnings"], ta)                                          # X2
    ebit = _div(r["operating_income"], ta)                                           # X3 (EBIT~op inc)
    tl   = r["total_liabilities"]
    x4_book = _div(r["total_equity"], tl)                                             # X4 (book)
    sales_ta = _div(r["revenue"], ta)                                                # X5

    z2 = None
    if _safe(wc, re, ebit, x4_book):
        # Z'' = 6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4   (no sales term, book equity)
        z2 = 6.56 * wc + 3.26 * re + 6.72 * ebit + 1.05 * x4_book

    z_orig = None
    if market_cap and tl and _safe(wc, re, ebit, sales_ta):
        x4_mkt = market_cap / tl
        # Z = 1.2 X1 + 1.4 X2 + 3.3 X3 + 0.6 X4(mkt) + 1.0 X5
        z_orig = 1.2 * wc + 1.4 * re + 3.3 * ebit + 0.6 * x4_mkt + 1.0 * sales_ta

    zone = None
    if z2 is not None:
        zone = "safe" if z2 > Z2_SAFE else "distress" if z2 < Z2_DISTRESS else "grey"
    return {"z2": z2, "z_orig": z_orig, "zone": zone,
            "x1_wc": wc, "x2_re": re, "x3_ebit": ebit, "x4_book": x4_book}


# ============================ MODEL: Beneish M ==============================
def beneish(hist):
    """Beneish 8-variable M-Score. Needs year t and t-1. TATA is EXACT (CFO cached)."""
    if len(hist) < 2:
        return {"m": None}
    t, p = hist[0], hist[1]

    def gm(x):     # gross margin
        return _div(x["gross_profit"], x["revenue"])
    def lev(x):    # (LTD + current liabilities) / TA
        ltd = x["long_term_debt"] or 0
        cl  = x["current_liabilities"] or 0
        return _div(ltd + cl, x["total_assets"])
    def aq(x):     # asset quality = 1 - (CA + net PPE)/TA  (non-current non-PPE share)
        v = _div((x["current_assets"] or 0) + (x["ppe_net"] or 0), x["total_assets"])
        return None if v is None else 1 - v
    def deprate(x):
        dep, ppe = x["dep"], x["ppe_net"]
        if dep is None or ppe is None or (dep + ppe) == 0:
            return None
        return dep / (dep + ppe)

    DSRI = _div(_div(t["receivables"], t["revenue"]), _div(p["receivables"], p["revenue"]))
    GMI  = _div(gm(p), gm(t))
    AQI  = _div(aq(t), aq(p))
    SGI  = _div(t["revenue"], p["revenue"])
    DEPI = _div(deprate(p), deprate(t))
    SGAI = _div(_div(t["sga"], t["revenue"]), _div(p["sga"], p["revenue"]))
    LVGI = _div(lev(t), lev(p))
    # TATA = (net income - cash from operations) / total assets   (exact)
    TATA = _div((t["net_income"] - t["cfo"]) if _safe(t["net_income"], t["cfo"]) else None,
                t["total_assets"])

    comp = dict(DSRI=DSRI, GMI=GMI, AQI=AQI, SGI=SGI, DEPI=DEPI, SGAI=SGAI, LVGI=LVGI, TATA=TATA)
    # M needs the 8 core drivers; SGAI/DEPI tolerate missing by defaulting to 1.0 (neutral)
    core = [DSRI, GMI, AQI, SGI, TATA]
    if any(c is None for c in core):
        return {"m": None, "components": comp}
    DEPI = DEPI if DEPI is not None else 1.0
    SGAI = SGAI if SGAI is not None else 1.0
    LVGI = LVGI if LVGI is not None else 1.0
    m = (-4.84 + 0.920 * DSRI + 0.528 * GMI + 0.404 * AQI + 0.892 * SGI
         + 0.115 * DEPI - 0.172 * SGAI + 4.679 * TATA - 0.327 * LVGI)
    return {"m": m, "components": comp, "flag": m > M_THRESHOLD}


# ============================ MODEL: Ohlson O ===============================
def ohlson(hist):
    """Ohlson 1980 9-variable logit -> P(bankruptcy). Corroborating (size term approximated)."""
    if len(hist) < 2:
        return {"o": None, "p": None}
    t, p = hist[0], hist[1]
    ta, tl = t["total_assets"], t["total_liabilities"]
    ca, cl = t["current_assets"], t["current_liabilities"]
    ni, nip = t["net_income"], p["net_income"]
    cfo = t["cfo"]
    if not _safe(ta, tl, ca, cl, ni) or ta <= 0:
        return {"o": None, "p": None}
    wc = (ca - cl)
    size = math.log(ta / 1e6) if ta > 0 else 0      # TA in $millions (deflator approx)
    TLTA = tl / ta
    WCTA = wc / ta
    CLCA = _div(cl, ca) or 0
    OENEG = 1.0 if tl > ta else 0.0                  # negative equity dummy
    NITA = ni / ta
    FUTL = _div(cfo, tl)                             # funds from ops / TL  (~CFO/TL)
    FUTL = FUTL if FUTL is not None else 0
    INTWO = 1.0 if (ni < 0 and nip is not None and nip < 0) else 0.0
    CHIN = _div((ni - nip), (abs(ni) + abs(nip))) if nip is not None else 0
    CHIN = CHIN if CHIN is not None else 0
    o = (-1.32 - 0.407 * size + 6.03 * TLTA - 1.43 * WCTA + 0.0757 * CLCA
         - 1.72 * OENEG - 2.37 * NITA - 1.83 * FUTL + 0.285 * INTWO - 0.521 * CHIN)
    try:
        prob = 1 / (1 + math.exp(-o))
    except OverflowError:
        prob = 1.0 if o > 0 else 0.0
    return {"o": o, "p": prob, "flag": prob > O_HIGH_PROB}


# ============================ MODEL: accruals ===============================
def cash_conversion(hist, n=4):
    """Multi-year cumulative CFO vs net income. A genuine earnings manipulator can't
    turn reported profit into cash OVER TIME; a hyper-grower's single-year accrual
    spike (receivables/inventory build) washes out across years. Returns (cum_ni,
    cum_cfo, ratio)."""
    yrs = hist[:n]
    cni = sum(x["net_income"] for x in yrs if x["net_income"] is not None)
    ccfo = sum(x["cfo"] for x in yrs if x["cfo"] is not None)
    ratio = (ccfo / cni) if cni and cni > 0 else None
    return cni, ccfo, ratio


def sloan_accruals(hist):
    """(Net income - CFO) / average total assets. High positive = low earnings quality."""
    if len(hist) < 2:
        return {"accrual_ratio": None}
    t, p = hist[0], hist[1]
    if not _safe(t["net_income"], t["cfo"], t["total_assets"], p["total_assets"]):
        return {"accrual_ratio": None}
    avg_ta = (t["total_assets"] + p["total_assets"]) / 2
    if avg_ta == 0:
        return {"accrual_ratio": None}
    ar = (t["net_income"] - t["cfo"]) / avg_ta
    return {"accrual_ratio": ar, "flag": ar > ACCRUAL_HI}


# ============================ MODEL: Montier C ==============================
def montier_c(hist):
    """6 binary earnings-manipulation flags (Montier 2008). Score 0-6."""
    if len(hist) < 2:
        return {"c": None}
    t, p = hist[0], hist[1]
    flags = {}
    # 1) growing gap between net income and operating cash flow
    gap_t = (t["net_income"] - t["cfo"]) if _safe(t["net_income"], t["cfo"]) else None
    gap_p = (p["net_income"] - p["cfo"]) if _safe(p["net_income"], p["cfo"]) else None
    flags["ni_cfo_divergence"] = (gap_t is not None and gap_p is not None
                                  and gap_t > gap_p and gap_t > 0)
    # 2) rising DSO (receivables / revenue)
    dso_t, dso_p = _div(t["receivables"], t["revenue"]), _div(p["receivables"], p["revenue"])
    flags["dso_rising"] = (dso_t is not None and dso_p is not None and dso_t > dso_p)
    # 3) rising DSI (inventory / COGS)
    dsi_t = _div(t["inventories"], t["cost_of_revenue"])
    dsi_p = _div(p["inventories"], p["cost_of_revenue"])
    flags["dsi_rising"] = (dsi_t is not None and dsi_p is not None and dsi_t > dsi_p)
    # 4) rising other-current-assets / revenue  (other CA = CA - cash - recv - inv)
    def other_ca(x):
        ca = x["current_assets"]
        if ca is None:
            return None
        return ca - (x["cash"] or 0) - (x["receivables"] or 0) - (x["inventories"] or 0)
    oca_t = _div(other_ca(t), t["revenue"]); oca_p = _div(other_ca(p), p["revenue"])
    flags["other_ca_rising"] = (oca_t is not None and oca_p is not None and oca_t > oca_p)
    # 5) declining depreciation rate  dep/(dep+ppe)
    def deprate(x):
        if x["dep"] is None or x["ppe_net"] is None or (x["dep"] + x["ppe_net"]) == 0:
            return None
        return x["dep"] / (x["dep"] + x["ppe_net"])
    dr_t, dr_p = deprate(t), deprate(p)
    flags["dep_rate_declining"] = (dr_t is not None and dr_p is not None and dr_t < dr_p)
    # 6) high total-asset growth (serial-acquirer / soft growth)
    ta_g = _div(t["total_assets"], p["total_assets"])
    flags["asset_growth_high"] = (ta_g is not None and ta_g - 1 > 0.15)
    c = sum(1 for v in flags.values() if v)
    return {"c": c, "flags": flags, "flag": c >= C_HIGH}


# ====================== liquidity / leverage / runway =======================
def solvency(hist, ctx):
    r = hist[0]
    ebitda = r["ebitda"]
    net_debt = (r["total_debt"] or 0) - (r["cash"] or 0)
    nd_ebitda = _div(net_debt, ebitda) if (ebitda and ebitda > 0) else None
    current_ratio = _div(r["current_assets"], r["current_liabilities"])
    quick_ratio = _div((r["current_assets"] or 0) - (r["inventories"] or 0), r["current_liabilities"])
    neg_equity = (r["total_equity"] is not None and r["total_equity"] < 0)
    # negative equity is only a *solvency* signal when it comes from accumulated
    # LOSSES (negative retained earnings), not from buybacks/treasury stock/goodwill
    # (ABBV, ADP, MCD, HD run negative book equity while gushing cash -> not distress).
    neg_re = (r["retained_earnings"] is not None and r["retained_earnings"] < 0)
    insolvent_equity = neg_equity and neg_re
    ebitda_neg = (ebitda is not None and ebitda <= 0)
    cfo = r["cfo"]
    cfo_neg = (cfo is not None and cfo < 0)          # core business consumes cash
    fcf = (cfo - r["capex"]) if _safe(cfo, r["capex"]) else None
    fcf_neg = (fcf is not None and fcf < 0)
    # cash runway (months) -- on OPERATING cash burn (CFO<0), not FCF. Capex-driven
    # negative FCF funded by debt issuance (utilities, growth capex) is NOT a burn.
    runway = None
    if cfo_neg and r["cash"]:
        runway = (r["cash"] / (-cfo)) * 12.0
    # tangible asset coverage of debt
    tang = None
    if r["total_assets"] is not None:
        tang = r["total_assets"] - (r["intangibles"] or 0)
    asset_cover = (tang is not None and r["total_debt"] is not None and r["total_debt"] > 0
                   and tang > r["total_debt"])
    # interest coverage (APPROX -- interest not separately disclosed; uses other inc/exp)
    int_proxy = None
    oie = r["other_income_expense"]
    if oie is not None and oie < 0 and r["operating_income"]:
        int_proxy = _div(r["operating_income"], -oie)
    return {
        "net_debt": net_debt, "nd_ebitda": nd_ebitda,
        "current_ratio": current_ratio, "quick_ratio": quick_ratio,
        "neg_equity": neg_equity, "neg_retained_earnings": neg_re,
        "insolvent_equity": insolvent_equity, "ebitda_neg": ebitda_neg,
        "cfo": cfo, "cfo_neg": cfo_neg,
        "fcf": fcf, "fcf_neg": fcf_neg, "cash_runway_months": runway,
        "asset_cover_debt": asset_cover, "int_cover_approx": int_proxy,
    }


# ============================== recovery vector =============================
def recovery(hist, ctx, alt):
    """Signals that a distressed name can recover SLOWLY rather than die."""
    sig = {}
    r = hist[0]
    # still generating operating cash (the linchpin)
    sig["cfo_positive"] = (r["cfo"] is not None and r["cfo"] > 0)
    # deleveraging: debt down YoY OR net long-term-debt repayment
    if len(hist) > 1 and _safe(r["total_debt"], hist[1]["total_debt"]):
        sig["deleveraging"] = r["total_debt"] < hist[1]["total_debt"]
    else:
        sig["deleveraging"] = (r["ltd_issued_repaid"] is not None and r["ltd_issued_repaid"] < 0)
    # operating margin improving (recent vs older)
    def opm(x):
        return _div(x["operating_income"], x["revenue"])
    recent = [opm(x) for x in hist[:2] if opm(x) is not None]
    older  = [opm(x) for x in hist[2:5] if opm(x) is not None]
    sig["margin_improving"] = bool(recent and older and statistics.mean(recent) > statistics.mean(older))
    # revenue decline decelerating / re-growth
    revs = [x["revenue"] for x in hist if x["revenue"]]
    sig["revenue_stabilizing"] = False
    if len(revs) >= 3:
        g_recent = revs[0] / revs[1] - 1 if revs[1] else 0
        g_prev   = revs[1] / revs[2] - 1 if revs[2] else 0
        sig["revenue_stabilizing"] = (g_recent >= g_prev) or (g_recent >= -0.02)
    # tangible assets cover total debt (liquidation headroom)
    tang = (r["total_assets"] - (r["intangibles"] or 0)) if r["total_assets"] is not None else None
    sig["asset_coverage"] = (tang is not None and r["total_debt"] and tang > r["total_debt"])
    # quality: Piotroski decent or improving
    pf = ctx.get("piotroski_f") if ctx else None
    qd = ctx.get("quality_delta_yoy") if ctx else None
    sig["piotroski_ok"] = (pf is not None and pf >= 5) or (qd is not None and qd > 0)
    # Altman trending up
    sig["z_improving"] = False
    if len(hist) > 1:
        a_prev = altman(hist[1:], None).get("z2")
        if alt.get("z2") is not None and a_prev is not None:
            sig["z_improving"] = alt["z2"] > a_prev
    score = sum(1 for v in sig.values() if v)
    return {"signals": sig, "score": score}


# =============================== the screen =================================
def screen(ticker, ctx, hist, news=None):
    sector = (ctx or {}).get("sector", "Unknown")
    mcap = (ctx or {}).get("market_cap")
    fin_sector = sector in FIN_SECTORS
    # news events (optional): going-concern/Chapter-11/default = bankruptcy corroboration;
    # SEC/short-seller/restatement = fraud corroboration. (Law-firm spam already filtered.)
    news_bk_event = bool(news and news.get("n_bankruptcy", 0) > 0)
    news_fraud_event = bool(news and news.get("n_strong_fraud", 0) > 0)

    alt = altman(hist, mcap)
    ben = beneish(hist)
    ohl = ohlson(hist)
    acc = sloan_accruals(hist)
    mon = montier_c(hist)
    sol = solvency(hist, ctx)
    rec = recovery(hist, ctx, alt)

    reasons = []   # bankruptcy reasons
    fraud_reasons = []
    z2 = alt["z2"]
    r0 = hist[0]
    recent_net_loss = (r0["net_income"] is not None and r0["net_income"] < 0)
    prior_net_loss = (len(hist) > 1 and hist[1]["net_income"] is not None and hist[1]["net_income"] < 0)
    sustained_losses = recent_net_loss and prior_net_loss
    short_runway = (sol["cash_runway_months"] is not None and sol["cash_runway_months"] < RUNWAY_SHORT)
    long_runway = (sol["cash_runway_months"] is not None and sol["cash_runway_months"] > LONG_RUNWAY)
    pays_dividend = (r0["dividends"] is not None and r0["dividends"] < 0
                     and abs(r0["dividends"]) > 0.05 * abs(r0["net_income"] or 1))

    # Float / finance-arm distortion: firms that hold CLIENT money (payroll processors
    # ADP/PAYX, exchanges, brokers, captive-finance arms) carry huge current liabilities
    # and gross "debt" that are pass-through, not corporate leverage. Signature: current
    # liabilities exceed revenue, REAL (long-term) debt is small vs EBITDA, and the firm
    # is profitable & cash-generative. Treat like a structurally-levered sector so
    # Altman / leverage / Ohlson (all balance-sheet ratios) don't false-flag them.
    float_distortion = bool(
        r0["current_liabilities"] is not None and r0["revenue"]
        and r0["current_liabilities"] > 1.0 * r0["revenue"]
        and r0["long_term_debt"] is not None and r0["ebitda"] and r0["ebitda"] > 0
        and r0["long_term_debt"] < 1.5 * r0["ebitda"]
        and (sol["cfo"] is not None and sol["cfo"] > 0)
        and not recent_net_loss
    )
    levered_sector = (sector in LEVERED_SECTORS) or float_distortion
    ohlson_severe = (ohl.get("p") is not None and ohl["p"] > OHLSON_SEVERE) and not levered_sector

    # multi-year cash conversion + real (long-term) leverage
    cum_ni, cum_cfo, conv_ratio = cash_conversion(hist)
    if cum_ni and cum_ni > 0:
        poor_conversion = (cum_cfo is not None and cum_cfo < CASH_CONV_FLOOR * cum_ni)
    else:   # cumulatively unprofitable but reporting a recent profit while burning cash
        poor_conversion = (cum_cfo is not None and cum_cfo <= 0
                           and r0["net_income"] is not None and r0["net_income"] > 0)
    real_leverage = (r0["long_term_debt"] / r0["ebitda"]
                     if (r0["long_term_debt"] is not None and r0["ebitda"] and r0["ebitda"] > 0)
                     else None)

    # ---------- BANKRUPTCY gate (cash-serviceability first, not leverage) ----------
    # Bankruptcy = the firm can't sustain itself / service its debt -- a CASH and
    # SOLVENCY question. High-but-serviceable leverage (utilities, REITs) and
    # buyback-driven negative equity are NOT bankruptcy. Two signal classes:
    cfo_positive = (sol["cfo"] is not None and sol["cfo"] > 0)
    # Lenders/financials (mortgage originators RKT, BDCs) post structurally NEGATIVE
    # operating cash flow -- loans held for sale / loan deployment flow through operating
    # activities. That is NOT a cash burn, so CFO-based insolvency signals are suppressed
    # for them; they're judged on losses, negative-equity-from-losses, Ohlson, and news.
    cfo_burn = sol["cfo_neg"] and not fin_sector
    # FORTRESS balance sheet: net cash + positive free cash flow -> cannot be a near-term
    # bankruptcy regardless of GAAP losses / Altman (cash-rich SaaS like RBRK).
    fortress = (sol["net_debt"] is not None and sol["net_debt"] < 0
                and sol["fcf"] is not None and sol["fcf"] > 0)
    cash_insolvency = {
        "operating_cash_flow_negative": cfo_burn,                             # burns operating cash
        # negative EBITDA matters for serviceability ONLY if cash flow isn't covering it.
        # Ford posted an operating loss yet generated +$21B CFO -> it can service debt.
        "cant_service_debt_ebitda_negative": sol["ebitda_neg"] and (sol["net_debt"] or 0) > 0 and not cfo_positive and not fin_sector,
        "insolvent_from_accumulated_losses": sol["insolvent_equity"] and (recent_net_loss or prior_net_loss),
        "cash_runway_under_18mo": short_runway and not fin_sector,            # running out of cash
    }
    corroborators = {
        "ohlson_high_default_prob": ohlson_severe,
        "altman_deep_distress": (z2 is not None and z2 < Z2_DISTRESS) and not levered_sector,
        "leverage_severe": (sol["nd_ebitda"] is not None and sol["nd_ebitda"] > ND_EBITDA_SEVERE) and not levered_sector,
        "sustained_losses_2y": sustained_losses,
    }
    n_cash = sum(1 for v in cash_insolvency.values() if v)
    n_corr = sum(1 for v in corroborators.values() if v)

    # strong solvency override: a profitable cash generator with serviceable leverage
    # cannot be a near-term bankruptcy, regardless of book-equity sign or Altman.
    solvent_override = (
        (sol["cfo"] is not None and sol["cfo"] > 0)
        and not sol["ebitda_neg"]
        and not sustained_losses
        and (sol["nd_ebitda"] is None or sol["nd_ebitda"] < 4.0 or levered_sector)
        and not ohlson_severe
    )
    # profitability override: a solidly PROFITABLE firm (positive net income AND EBIT)
    # with positive equity and modest REAL (long-term) leverage is not a near-term
    # bankruptcy even when operating cash flow is temporarily negative from a working
    # -capital build -- homebuilders buying land (TOL), automakers (STLA), BDCs (ARCC).
    profitable_override = (
        r0["net_income"] is not None and r0["net_income"] > 0
        and not sol["neg_equity"]
        and not sustained_losses
        and not ohlson_severe
        and (
            # profitable with positive operating income and modest real leverage
            (r0["operating_income"] is not None and r0["operating_income"] > 0
             and (real_leverage is None or real_leverage < 4.0))
            # OR a profitable DIVIDEND-PAYER -- boards cut the dividend long before
            # bankruptcy; negative CFO here is structural (lending/financial: ARCC).
            or pays_dividend
        )
    )
    # Global vetoes: a fortress balance sheet or a long cash runway means NOT a
    # near-term bankruptcy (a funded burner can fund years of losses + raise more).
    # The audit showed well-capitalised growth/biotech (GH, RBRK, NVDA-adjacent) get
    # mis-flagged on backward-looking GAAP losses; cash runway is the real arbiter.
    bankruptcy = False
    if not (solvent_override or profitable_override or fortress or long_runway):
        # 1) insolvent from accumulated losses AND still losing money -- definitive
        if cash_insolvency["insolvent_from_accumulated_losses"]:
            bankruptcy = True
        # 2) burning operating cash with a SHORT runway -- the classic death spiral
        if cfo_burn and short_runway:
            bankruptcy = True
        # 3) burning operating cash AND broad corroboration (deep distress, no cushion)
        if cfo_burn and (n_cash + n_corr) >= 3:
            bankruptcy = True
        # 4) genuinely can't service debt (neg EBITDA, no offsetting CFO) + corroboration
        if cash_insolvency["cant_service_debt_ebitda_negative"] and (n_cash + n_corr) >= 2:
            bankruptcy = True
        # 5) Ohlson screams default AND at least one hard cash signal
        if ohlson_severe and n_cash >= 1:
            bankruptcy = True
    # NEWS escalation: an actual going-concern / Chapter-11 / default headline confirms
    # distress even when the snapshot fundamentals were borderline.
    if news_bk_event and (n_cash + n_corr) >= 1:
        bankruptcy = True
    # classify the FLAVOUR of distress -- honest labelling (the audit's key lesson):
    #  * insolvency       = an over-levered / loss-eroded operating business genuinely failing
    #  * cash_burn        = a pre-profit company burning cash, dependent on raising more
    distress_type = None
    if bankruptcy:
        if sol["insolvent_equity"] or (sol["nd_ebitda"] is not None and sol["nd_ebitda"] > ND_EBITDA_HIGH) or news_bk_event:
            distress_type = "insolvency"
        else:
            distress_type = "cash_burn"
        for k, v in {**cash_insolvency, **corroborators}.items():
            if v:
                reasons.append(k)
        if news_bk_event:
            reasons.append("news:going_concern/default/ch11")

    # ---------- FRAUD gate ----------
    beneish_flag = bool(ben.get("flag"))
    ar = acc.get("accrual_ratio")
    m = ben.get("m")
    # The CORE "pumping the numbers" signature is reported earnings that OUTRUN cash
    # = high POSITIVE accruals (Sloan). Beneish/Montier ALONE over-flag fast GROWERS
    # (AAON, AGI build receivables/inventory to fund growth -> high SGI/DSO/DSI, but
    # cash-backed earnings). So require elevated positive accruals as a NECESSARY
    # condition, then demand corroboration. This also auto-excludes the meme/melting
    # -ice-cube false positives (GME), whose accruals are negative.
    high_pos_accruals = (ar is not None and ar > FRAUD_ACCRUAL_MIN)
    # Require a DISTINCT second signal beyond the (necessary) high accruals -- not just
    # "even higher accruals", which would still flag structural inventory-builders.
    # Homebuilders (TOL) sink reported profit into real INVENTORY (land/homes) -> high
    # accruals + poor conversion, but Beneish barely clears -1.78 and Montier is low.
    corroborate = {
        "montier_c_high": bool(mon.get("flag")),                      # >= 4 of 6 flags
        "receivables_spike": bool((ben.get("components", {}).get("DSRI") or 0) > 1.4),
        "beneish_strong": (m is not None and m > -1.0),               # well above the -1.78 line
    }
    n_corrob = sum(1 for v in corroborate.values() if v)
    # NECESSARY: the firm can't convert reported earnings into cash over ~4y. NVDA's
    # single-year accrual spike (hyper-growth) washes out -> cum CFO/NI 0.88 -> cleared.
    fraud_fundamental = beneish_flag and high_pos_accruals and poor_conversion and n_corrob >= 1

    # CASH-GENERATIVE VETO (the audit's lesson): a profitable firm that DOES convert to
    # cash over time (positive latest CFO and positive cumulative CFO) almost always has
    # high accruals from a ONE-TIME non-cash item -- a deferred-tax-asset release (AUPH),
    # lease accounting (FTAI), a milestone -- not manipulation. Demote it to the forensic
    # WATCHLIST rather than calling it fraud, UNLESS news corroborates (SEC/short/restate).
    net_cash = (sol["net_debt"] is not None and sol["net_debt"] < 0)
    profitable = (r0["net_income"] is not None and r0["net_income"] > 0)
    cash_generative = ((cfo_positive and cum_cfo is not None and cum_cfo > 0 and profitable)
                       # a PROFITABLE, NET-CASH firm almost never manipulates to survive --
                       # the high accruals are a one-time non-cash item (AEHR/NVAX): demote.
                       or (profitable and net_cash))
    fraud = fraud_fundamental and (news_fraud_event or not cash_generative)
    fraud_watchlist = fraud_fundamental and not fraud      # demoted, still worth a look
    if fraud:
        fraud_reasons.append(f"beneish_m({m:.2f}>-1.78)")
        fraud_reasons.append(f"accruals_{ar*100:.0f}pct")
        if conv_ratio is not None:
            fraud_reasons.append(f"cfo/ni_{conv_ratio:.2f}")
        for k, v in corroborate.items():
            if v:
                fraud_reasons.append(k)
        if news_fraud_event:
            fraud_reasons.append("news:sec/short/restatement")
    # soft earnings-quality note -- surfaced for transparency even when NOT bucketed
    # AVOID (fast growers with elevated Beneish but cash-backed earnings, or the demoted
    # one-time-accrual names above).
    earnings_quality_flag = bool(beneish_flag or fraud_watchlist or (ar is not None and ar > ACCRUAL_HI))

    # ---------- RECOVERY gate ----------
    # A name is "distressed" only on a GENUINE signal -- not merely Altman grey-zone
    # or thin working capital (AAPL runs negative working capital and negative
    # retained earnings from buybacks; ABBV/ADP run negative book equity). Require
    # real financial stress: losses, cash burn, or leverage corroborated by Altman.
    # "Distressed" = genuine financial stress NOW. A FORTRESS balance sheet -- NET CASH
    # plus positive free cash flow -- is never distressed, no matter the GAAP loss: that
    # is the cash-rich growth-SaaS case (CRWD/NET/SNOW lose money on paper from stock
    # comp but gush cash and hold net cash). Everything with an operating loss + net debt
    # (BA, F) or burning operating cash (STLA) is. Leverage/Altman triggers also need a
    # cash strain so buyback-levered healthy names (LOW/AMGN: high debt, strong cash) pass.
    fortress = (sol["net_debt"] is not None and sol["net_debt"] < 0
                and sol["fcf"] is not None and sol["fcf"] > 0)
    weak_cash = sol["cfo_neg"] or sol["fcf_neg"]
    # (insolvent_equity is intentionally NOT a standalone trigger here: negative equity
    #  + negative retained earnings is usually buybacks > cumulative earnings, not losses
    #  -- LOW/MCD/HD/SBUX. Genuine insolvency-from-losses always shows a loss or cash
    #  burn too, which the triggers below catch; the bankruptcy gate handles the rest.)
    distress_present = (not fortress) and (
        sol["cfo_neg"]                                             # burning operating cash
        or sustained_losses                                       # two straight years of losses
        or sol["ebitda_neg"]                                      # operating loss
        or recent_net_loss                                        # GAAP loss (non-fortress)
        or (sol["nd_ebitda"] is not None and sol["nd_ebitda"] > ND_EBITDA_HIGH
            and weak_cash and not levered_sector)                 # high leverage + cash strain
        or (z2 is not None and z2 < Z2_DISTRESS and weak_cash and not levered_sector
            and sol["nd_ebitda"] is not None and sol["nd_ebitda"] > 2.5)  # Altman distress + leverage + strain
    )
    recoverable = (distress_present and rec["signals"]["cfo_positive"]
                   and rec["score"] >= RECOVERY_MIN_SIGNALS and not bankruptcy and not fraud)

    # ---------- bucket (AVOID dominates; fraud + bankruptcy can co-occur) ----------
    bk_label = ("insolvency — over-levered / loss-eroded operating business"
                if distress_type == "insolvency"
                else "cash-burn — pre-profit, dependent on raising more capital")
    if fraud and bankruptcy:
        bucket = "AVOID"
        headline = f"AVOID — earnings-manipulation risk + bankruptcy ({bk_label})"
    elif fraud:
        bucket = "AVOID"
        headline = "AVOID — earnings-manipulation risk (investigate)"
    elif bankruptcy:
        bucket = "AVOID"
        headline = f"AVOID — bankruptcy / {bk_label}"
    elif recoverable:
        bucket = "DISTRESSED-RECOVERABLE"
        headline = "Distressed but recoverable — solvent with a turnaround vector"
    elif fraud_watchlist:
        bucket = "WATCH"
        headline = "Watch — forensic earnings-quality flag (high accruals, but cash-backed / one-time — investigate, not a fraud call)"
    elif distress_present:
        bucket = "WATCH"
        headline = "Watch — stress signals but neither terminal nor clearly recovering"
    else:
        bucket = "CLEAR"
        headline = "Clear — no material distress or manipulation signal"

    # severity scores (0-100) for ranking
    bankruptcy_severity = min(100, 18 * (n_cash + n_corr)
                              + (20 if sol["insolvent_equity"] else 0)
                              + (15 if ohlson_severe else 0)
                              + (10 if (z2 is not None and z2 < Z2_DISTRESS) else 0))
    fraud_severity = 0
    if ben.get("m") is not None:
        fraud_severity = min(100, max(0, (ben["m"] - M_THRESHOLD) * 25) + 15 * n_corrob)

    return {
        "ticker": ticker, "sector": sector, "market_cap": mcap,
        "bucket": bucket, "headline": headline,
        "bankruptcy": bankruptcy, "distress_type": distress_type,
        "fraud": fraud, "fraud_watchlist": fraud_watchlist, "recoverable": recoverable,
        "news_bk_event": news_bk_event, "news_fraud_event": news_fraud_event,
        "reasons": reasons, "fraud_reasons": fraud_reasons,
        "bankruptcy_severity": bankruptcy_severity, "fraud_severity": fraud_severity,
        "recovery_score": rec["score"], "recovery_signals": rec["signals"],
        "altman": alt, "beneish": ben, "ohlson": ohl, "accruals": acc,
        "montier": mon, "solvency": sol,
        "earnings_quality_flag": earnings_quality_flag,
        "fin_sector_caveat": fin_sector, "float_distortion": float_distortion,
        "n_years": len(hist),
    }


# ================================ CLI ======================================
def _pct(x, d=1):
    return "n/a" if x is None else f"{x*100:.{d}f}%"

def _f(x, d=2):
    return "n/a" if x is None else f"{x:.{d}f}"

def render(res):
    L = []
    cap = res["market_cap"]
    caps = (f"${cap/1e9:.1f}B" if cap and cap >= 1e9 else f"${cap/1e6:.0f}M" if cap else "n/a")
    L.append(f"\n===== {res['ticker']}  ({res['sector']}, mcap {caps}) =====")
    L.append(f"  BUCKET: {res['bucket']}  —  {res['headline']}")
    if res["fin_sector_caveat"]:
        L.append("  [caveat] Financials/Real Estate: Altman/Beneish are unreliable here "
                 "(different balance sheet); treat as indicative only.")
    if res.get("float_distortion"):
        L.append("  [caveat] Float business (holds client funds / captive finance) — gross "
                 "leverage & Altman are distorted; judged on cash flow + real (LT) debt.")
    a, b, o = res["altman"], res["beneish"], res["ohlson"]
    s, m, ac = res["solvency"], res["montier"], res["accruals"]
    L.append(f"  Altman Z'' {_f(a['z2'])} ({a['zone']})"
             + (f" | orig Z {_f(a['z_orig'])}" if a['z_orig'] is not None else ""))
    L.append(f"  Beneish M {_f(b.get('m'))} (manip if > -1.78)  | "
             f"Ohlson P(default) {_pct(o.get('p'))}  | accruals {_pct(ac.get('accrual_ratio'))}  | "
             f"Montier C {m.get('c')}/6")
    L.append(f"  Solvency: net-debt/EBITDA {_f(s['nd_ebitda'],1)} | current ratio {_f(s['current_ratio'])} | "
             f"FCF {'neg' if s['fcf_neg'] else 'pos' if s['fcf'] is not None else 'n/a'} | "
             f"equity {'NEGATIVE' if s['neg_equity'] else 'positive'} | "
             f"runway {('%.0f mo' % s['cash_runway_months']) if s['cash_runway_months'] else 'n/a'}")
    if res["reasons"]:
        L.append("  Bankruptcy flags: " + ", ".join(res["reasons"]))
    if res["fraud_reasons"]:
        L.append("  Fraud flags: " + ", ".join(res["fraud_reasons"]))
    elif res.get("earnings_quality_flag") and res["bucket"] != "AVOID":
        kind = ("forensic earnings-quality flag (high accruals, but cash-backed / one-time)"
                if res.get("fraud_watchlist")
                else "elevated Beneish/accruals but earnings broadly cash-backed")
        L.append(f"  [note] {kind} — watch the accounting, not a manipulation call.")
    if res.get("news_bk_event") or res.get("news_fraud_event"):
        ev = ("going-concern/Ch11/default" if res.get("news_bk_event") else "") + \
             (" + " if res.get("news_bk_event") and res.get("news_fraud_event") else "") + \
             ("SEC/short-seller/restatement" if res.get("news_fraud_event") else "")
        L.append(f"  📰 News event (cache): {ev}")
    if res["bucket"] == "DISTRESSED-RECOVERABLE":
        on = [k for k, v in res["recovery_signals"].items() if v]
        L.append(f"  Recovery signals ({res['recovery_score']}/7): " + ", ".join(on))
    return "\n".join(L)


def run_one(ticker, as_json=False):
    ctx = load_context(ticker)
    fund = load_fundamentals(ticker)
    if not fund or not ctx:
        print(f"\n{ticker.upper()}: no cached fundamentals/context — skipped")
        return None
    hist = full_history(fund)
    if len(hist) < 2:
        print(f"\n{ticker.upper()}: <2y history — distress screen needs 2y")
        return None
    try:
        from distress_news import scan_ticker
        news = scan_ticker(ticker.upper())
    except Exception:
        news = None
    res = screen(ticker.upper(), ctx, hist, news=news)
    if as_json:
        print(json.dumps(res, default=str, indent=2))
    else:
        print(render(res))
    return res


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    for t in (args or ["TSLA"]):
        run_one(t, as_json=as_json)


if __name__ == "__main__":
    main()
