#!/usr/bin/env python3
"""
distress_news.py -- NEWS / EVENT layer for the distress & fraud screen.

The fundamentals models (Altman/Beneish/Ohlson/accruals) catch the financial
FOOTPRINT of distress and manipulation. News catches the EVENT -- and for fraud
especially the event (SEC charge, restatement, short-seller report, going-concern
opinion, Chapter 11 filing) is the decisive, often-earlier signal. This module adds
that layer by scanning the engine's news cache (read-only) for distress/fraud events
and folding them in as corroboration + surfacing.

TWO layers, by design:
  1. CACHE SCAN (this module, fast, offline) -- reads stockaffirm/cache/.../news.jsonl.
     IMPORTANT: that cache is only a ~2-WEEK ROLLING WINDOW (the live news poll), so it
     catches RECENT catalysts, not historical allegations. Good for "what just broke".
  2. LIVE ENRICHMENT (on-demand, per flagged ticker) -- historical/web news via
     AlphaVantage NEWS_SENTIMENT or a web-search agent. The adversarial audit workflow
     (`distress-avoid-audit`) is the reference implementation; see enrich_live_hint().

Keywords are TIERED so law-firm solicitation spam ("class action ... investigates")
doesn't masquerade as a real fraud signal.

  python3 distress_news.py TSLA NVAX MSTR      # show recent news events per ticker
"""
import os, json, functools

ENGINE = "/Users/prasadmenon/Claude/StockAffirmProject/stockaffirm"
NEWS_JSONL = os.path.join(ENGINE, "cache/data/raw/news.jsonl")

# --- tiered keyword sets -- STRONG sets are matched against the TITLE ONLY (real
# going-concern / SEC / Chapter-11 news names the company in the headline; matching the
# rambling description tags peers mentioned incidentally, which false-flagged NVDA/GOOG).
# Loose terms ("restructuring", "overstated", "default on", "internal investigation") were
# removed -- they appear constantly in routine corporate news.
STRONG_FRAUD = [
    "sec charges", "sec investigation", "sec probe", "charged with fraud", "accounting fraud",
    "restate", "restates earnings", "restatement", "material weakness", "accounting irregular",
    "auditor resign", "hindenburg", "muddy waters", "grizzly research", "short-seller report",
    "short seller report", "accounting probe", "earnings manipulation", "securities fraud charges",
    "delays 10-k", "delays annual report", "delayed 10-k", "going-concern doubt",
]
# law-firm solicitation noise -- filed routinely after ANY stock drop; matched anywhere
WEAK_FRAUD = [
    "class action", "securities class action", "investor alert", "shareholder alert",
    "investigates claims", "investigation on behalf", "reminds investors", "deadline reminder",
    "lead plaintiff", "encourages investors", "law firm",
]
STRONG_BANKRUPTCY = [
    "going concern", "going-concern", "chapter 11", "chapter 7", "files for bankruptcy",
    "filed for bankruptcy", "bankruptcy protection", "files chapter", "missed interest payment",
    "covenant breach", "covenant waiver", "debt restructuring", "restructuring support agreement",
    "delisting notice", "to be delisted", "liquidation", "insolvency", "forbearance agreement",
    "distressed exchange", "creditor protection", "out-of-court restructuring", "files for chapter",
]


@functools.lru_cache(maxsize=1)
def _news_index():
    """ticker -> list of {title, description, published_utc, publisher} (read-only)."""
    idx = {}
    if not os.path.exists(NEWS_JSONL):
        return idx
    for line in open(NEWS_JSONL):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        rec = {"title": d.get("title") or "", "description": d.get("description") or "",
               "published_utc": d.get("published_utc") or "", "publisher": d.get("publisher") or ""}
        for t in (d.get("tickers") or []):
            idx.setdefault(t.upper(), []).append(rec)
    return idx


def _hits(text, keywords):
    t = text.lower()
    return [k for k in keywords if k in t]


def news_window():
    """Return (earliest, latest) ISO dates present in the cache (for honesty in reports)."""
    dates = []
    for arts in _news_index().values():
        for a in arts:
            if a["published_utc"]:
                dates.append(a["published_utc"][:10])
    return (min(dates), max(dates)) if dates else (None, None)


def scan_ticker(ticker):
    """Scan cached news for distress/fraud EVENTS. Returns a structured signal."""
    arts = _news_index().get(ticker.upper(), [])
    strong_fraud, weak_fraud, bankruptcy = [], [], []
    for a in arts:
        title = a["title"]
        blob = a["title"] + " \n " + a["description"]
        # STRONG events: title-only (precision -- the company is the subject of the headline)
        sf = _hits(title, STRONG_FRAUD)
        bk = _hits(title, STRONG_BANKRUPTCY)
        # law-firm spam: match anywhere (it's always about the named ticker)
        wf = _hits(blob, WEAK_FRAUD)
        # law-firm solicitations QUOTE the complaint ("misled investors", "overstated"),
        # so a strong-fraud keyword that co-occurs with law-firm-spam markers is NOT an
        # independent signal -- it's the same plaintiff-firm press release. Demote it.
        if sf and not wf:
            strong_fraud.append({"title": a["title"][:160], "kw": sf, "date": a["published_utc"][:10],
                                 "pub": a["publisher"]})
        elif wf:
            weak_fraud.append({"title": a["title"][:160], "kw": (wf + sf), "date": a["published_utc"][:10]})
        if bk:
            bankruptcy.append({"title": a["title"][:160], "kw": bk, "date": a["published_utc"][:10],
                               "pub": a["publisher"]})
    # classify the dominant recent event
    if bankruptcy:
        event = "bankruptcy_event"
    elif strong_fraud:
        event = "fraud_event"
    elif weak_fraud:
        event = "litigation_noise"     # law-firm spam only -- do NOT escalate on this alone
    else:
        event = None
    return {
        "ticker": ticker.upper(),
        "n_articles": len(arts),
        "strong_fraud": strong_fraud, "weak_fraud": weak_fraud, "bankruptcy": bankruptcy,
        "n_strong_fraud": len(strong_fraud), "n_weak_fraud": len(weak_fraud),
        "n_bankruptcy": len(bankruptcy),
        "news_event": event,
        # the only news signals strong enough to MOVE a verdict (not law-firm spam):
        "actionable": bool(bankruptcy or strong_fraud),
    }


def enrich_live_hint():
    """How to get HISTORICAL / comprehensive news (beyond the 2-week cache):
    run the `distress-avoid-audit` workflow (web-search agent per ticker) or call
    AlphaVantage NEWS_SENTIMENT (function=NEWS_SENTIMENT&tickers=TICKER). Returns the
    same shape as scan_ticker so the screen consumes either identically."""
    return "see distress-avoid-audit workflow / AlphaVantage NEWS_SENTIMENT"


# ================================ CLI ======================================
def main():
    import sys
    lo, hi = news_window()
    print(f"news cache window: {lo} -> {hi}  ({sum(len(v) for v in _news_index().values())} ticker-tags)")
    for t in (sys.argv[1:] or ["NVAX"]):
        s = scan_ticker(t)
        print(f"\n{s['ticker']}: {s['n_articles']} articles | event={s['news_event']} | actionable={s['actionable']}")
        for label, items in (("BANKRUPTCY", s["bankruptcy"]), ("STRONG-FRAUD", s["strong_fraud"]),
                             ("litigation-noise", s["weak_fraud"])):
            for it in items[:4]:
                print(f"   [{label}] {it['date']} {it['kw']}: {it['title']}")


if __name__ == "__main__":
    main()
