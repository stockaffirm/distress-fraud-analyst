#!/usr/bin/env python3
"""
massive_api.py -- dual-source news + short interest for distress/fraud ground truth.

TWO news sources, merged and deduplicated:
  1. Massive API  (/v2/reference/news)        — primary; limit=200 (was 50)
  2. Alpha Vantage NEWS_SENTIMENT endpoint    — secondary; adds sentiment scores,
                                                per-ticker relevance, topic tags

Why dual-source?
  * Coverage: Massive alone missed VFS (Vietnamese EV, thin English coverage)
  * Precision: AV's ticker relevance_score >= 0.5 filter is better than our
    manual tickers[0] FOCUS check for foreign / multi-ticker articles
  * Depth: 200+200 = up to 400 deduped articles per ticker vs 50 previously
  * Signal: AV sentiment scores (-1 to +1) expose bearish sentiment not in keywords

Functions:
  * news(ticker, limit=200)         -> Massive headlines (primary source)
  * av_news(ticker, limit=200)      -> AV NEWS_SENTIMENT headlines (normalized)
  * short_interest(ticker)          -> latest days-to-cover (Massive)
  * event_scan(ticker)              -> merged distress/fraud/raise read from both sources

Keys:
  Massive: API_KEY from stockaffirm/.env
  AV:      ALPHAVANTAGE_API_KEY from stockaffirm/.env

  python3 massive_api.py BYND      # dump the live distress/fraud read for one ticker
  python3 massive_api.py VFS       # test thin-coverage foreign name
"""
import os, json, time, urllib.request, urllib.error
from pathlib import Path

BASE    = "https://api.massive.com"
AV_BASE = "https://www.alphavantage.co/query"
_KEY    = None
_AV_KEY = None

# ---- key loading -----------------------------------------------------------
def _key():
    global _KEY
    if _KEY:
        return _KEY
    k = os.environ.get("API_KEY")
    if not k:
        envp = "/Users/prasadmenon/Claude/StockAffirmProject/stockaffirm/.env"
        if os.path.exists(envp):
            for line in open(envp):
                line = line.strip()
                if line.startswith("API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    _KEY = k or "JEgcYfjaSr3xhM62a87F_Ez8P5lNVhxh"
    return _KEY


def _av_key():
    global _AV_KEY
    if _AV_KEY:
        return _AV_KEY
    k = os.environ.get("ALPHAVANTAGE_API_KEY") or os.environ.get("AV_API_KEY")
    if not k:
        for envp in [Path(__file__).parent / ".env",
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


# ---- HTTP helpers ----------------------------------------------------------
def _get(path, tries=3):
    sep = "&" if "?" in path else "?"
    url = f"{BASE}{path}{sep}apiKey={_key()}"
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (429, 502, 503, 504):
                time.sleep(1.5 * (i + 1))
                continue
            try:
                return json.loads(e.read().decode())
            except Exception:
                return {"status": "ERROR", "error": last}
        except Exception as e:
            last = str(e)
            time.sleep(1.0 * (i + 1))
    return {"status": "ERROR", "error": last}


def _av_get(params, tries=3):
    k = _av_key()
    if not k:
        return {}
    from urllib.parse import urlencode
    url = f"{AV_BASE}?{urlencode({**params, 'apikey': k})}"
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                d = json.loads(r.read().decode())
            note = d.get("Note") or d.get("Information") or ""
            if "call frequency" in note.lower():
                time.sleep(1.5 * (i + 1))
                continue
            return d
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (429, 502, 503, 504):
                time.sleep(1.5 * (i + 1))
                continue
        except Exception as e:
            last = str(e)
            time.sleep(1.0 * (i + 1))
    return {}


# ---- Massive news ----------------------------------------------------------
def news(ticker, limit=200):
    """Most-recent-first headlines from Massive (limit raised from 50 → 200)."""
    d = _get(f"/v2/reference/news?ticker={ticker.upper()}&order=desc&sort=published_utc&limit={limit}")
    out = []
    for r in (d.get("results") or []):
        out.append({
            "source":    "massive",
            "date":      (r.get("published_utc") or "")[:10],
            "title":     r.get("title") or "",
            "desc":      (r.get("description") or "")[:300],
            "tickers":   r.get("tickers") or [],
            "publisher": (r.get("publisher") or {}).get("name")
                         if isinstance(r.get("publisher"), dict)
                         else r.get("publisher"),
            "relevance": None,      # AV-only field; None for Massive
            "sentiment": None,      # AV-only field; None for Massive
        })
    return out


# ---- Alpha Vantage NEWS_SENTIMENT ------------------------------------------
def av_news(ticker, limit=200):
    """
    Alpha Vantage NEWS_SENTIMENT headlines for a ticker.
    Normalized to the same format as Massive news() output.

    Key advantages over Massive:
      - relevance_score: 0–1, per-ticker (replaces manual FOCUS filter)
      - ticker_sentiment_score: -1 to +1 (exposes negative sentiment not in keywords)
      - topics: Finance / Earnings / IPO / M&A / etc.
      - Up to 1000 articles available
    """
    T = ticker.upper()
    d = _av_get({"function": "NEWS_SENTIMENT", "tickers": T,
                 "limit": limit, "sort": "LATEST"})
    feed = d.get("feed") or []
    out = []
    for r in feed:
        # Extract per-ticker relevance and sentiment (AV provides both)
        ts_list = r.get("ticker_sentiment") or []
        ts = next((x for x in ts_list if x.get("ticker") == T), None)
        relevance = float(ts["relevance_score"])  if ts else 0.0
        sentiment = float(ts["ticker_sentiment_score"]) if ts else None

        # Normalize date: AV format is "20240101T120000" → "2024-01-01"
        tp = r.get("time_published") or ""
        date = f"{tp[0:4]}-{tp[4:6]}-{tp[6:8]}" if len(tp) >= 8 else ""

        out.append({
            "source":    "av",
            "date":      date,
            "title":     r.get("title") or "",
            "desc":      (r.get("summary") or "")[:300],
            "tickers":   [T],           # AV was queried for this ticker specifically
            "publisher": r.get("source"),
            "relevance": relevance,     # 0–1; ≥0.5 = article is primarily about this ticker
            "sentiment": sentiment,     # -1 to +1; negative = bearish tone
        })
    return out


# ---- Deduplication ---------------------------------------------------------
def _title_key(title):
    """Normalize title for deduplication (lowercase, strip punctuation)."""
    import re
    return re.sub(r"[^a-z0-9 ]", "", title.lower().strip())[:120]


def _merge_dedup(massive_arts, av_arts):
    """
    Merge Massive + AV articles, deduplicating by normalized title.
    Massive is primary (keep it when both have the same story).
    """
    seen = set()
    merged = []
    for a in massive_arts:   # Massive first (primary)
        k = _title_key(a["title"])
        if k and k not in seen:
            seen.add(k)
            merged.append(a)
    for a in av_arts:        # AV second (supplement)
        k = _title_key(a["title"])
        if k and k not in seen:
            seen.add(k)
            merged.append(a)
    # Sort merged by date descending
    merged.sort(key=lambda x: x.get("date") or "", reverse=True)
    return merged


def short_interest(ticker):
    """Latest short-interest snapshot (days_to_cover is the key distress/squeeze tell)."""
    d = _get(f"/stocks/v1/short-interest?ticker={ticker.upper()}&sort=settlement_date.desc&limit=1")
    res = d.get("results") or []
    if not res:
        return None
    r = res[0]
    return {"settlement_date": r.get("settlement_date"),
            "short_interest": r.get("short_interest"),
            "avg_daily_volume": r.get("avg_daily_volume"),
            "days_to_cover": r.get("days_to_cover")}


# ---- distress/fraud event scan over LIVE news (richer than the 2-week cache) ----
# distress keywords -- DISTRESS-SPECIFIC only (ambiguous "delisting"/"debt restructuring"
# removed: voluntary delistings & routine refinancings are NOT distress; "filed for
# bankruptcy" handled by the focus + spam filters to avoid counterparty references).
STRONG_BK = ["going concern", "going-concern", "going concern doubt", "substantial doubt about",
             "chapter 11", "chapter 7", "files for bankruptcy", "filed for bankruptcy",
             "bankruptcy protection", "files for chapter", "missed interest payment",
             "covenant breach", "covenant waiver", "out-of-court restructuring",
             "restructuring support agreement", "delisting notice", "notice of delisting",
             "minimum bid price", "regain compliance", "deficiency notice", "faces delisting",
             "plan of liquidation", "chapter 7 liquidation", "insolvency", "forbearance agreement",
             "distressed exchange", "creditor protection"]
# POSITIVE-OUTCOME guard: a headline can contain a distress keyword ("minimum bid price")
# while announcing the OPPOSITE -- the company REGAINED compliance / cured the deficiency.
# If the title is a recovery, it is NOT a distress event (AHG/DARE/OCG/SQFT regained compliance).
BK_POSITIVE = ["regains compliance", "regained compliance", "has regained", "back in compliance",
               "compliance regained", "avoids delisting", "averts delisting", "satisfies nasdaq",
               "no longer deficient", "cured the deficiency"]
STRONG_FRAUD = ["sec charges", "sec investigation", "sec probe", "charged with fraud", "accounting fraud",
                "restate", "restatement", "material weakness", "accounting irregular", "auditor resign",
                "hindenburg", "muddy waters", "grizzly research", "fuzzy panda", "kerrisdale",
                "short-seller report", "short seller report", "short report", "earnings manipulation",
                "securities fraud charges", "delays 10-k", "delayed annual report", "delays annual report"]
# law-firm solicitation spam (filed routinely after ANY drop) -- expanded with the actual
# phrasings/firm names that leaked through (BFA Law "Contact ... if you suffered losses").
LAWFIRM = ["class action", "securities class action", "lead plaintiff", "reminds investors",
           "encourages investors", "encouraged to act", "investigates claims", "investigation on behalf of",
           "law firm", "law offices", "investor alert", "shareholder alert", "deadline reminder",
           "contact bfa", "bfa law", "investors with losses", "if you suffered", "if you lost money",
           "suffered a loss", "rosen law", "pomerantz", "bragar eagel", "schall law", "glancy prongay",
           "kahn swick", "faruqi", "kessler topaz", "bernstein liebhard", "levi & korsinsky",
           "shareholder rights", "securities fraud investigation", "important deadline", "investors who lost",
           "to contact the firm", "lawsuit alert", "robbins llp", "gross law", "johnson fistel",
           "encouraged to reach out", "block & leviton", "wolf haldenstein", "fistel"]
# a RECENT capital raise extends runway -> the #1 "funded cash-burner" false-positive signal
RAISE = ["public offering", "registered direct", "private placement", "prices offering",
         "closes offering", "upsized offering", "at-the-market offering", "atm offering",
         "convertible notes offering", "equity offering", "raises $", "raised $", "secures financing",
         "strategic investment", "common stock offering", "completes offering", "pricing of"]


def _hits(text, kws):
    t = text.lower()
    return [k for k in kws if k in t]


def _is_focused(a, T):
    """
    FOCUS filter: is this article primarily about ticker T?
    - Massive:  tickers[0] == T  (subject-ordered list; first = primary)
    - AV:       relevance_score >= 0.5  (AV computes this per-ticker explicitly)
    Both are better than a simple keyword check; AV's is more precise for
    foreign-listed names (VFS, BABA, etc.) and multi-company stories.
    """
    if a.get("source") == "av":
        return (a.get("relevance") or 0.0) >= 0.5
    tks = [x.upper() for x in (a.get("tickers") or [])]
    return (not tks) or (tks[0] == T)


def event_scan(ticker, massive_limit=200, av_limit=200):
    """
    Dual-source distress/fraud/raise read — Massive + Alpha Vantage, merged and deduped.

    Previous limit was 50 (Massive only). Now: up to 200 Massive + 200 AV = ~300-400
    unique articles after deduplication. Catches thin-coverage names (foreign-listed,
    small-caps) that appeared as AVOID_unconfirmed with 50-article window.

    FOCUS filter:
      Massive: tickers[0] == ticker  (subject-ordered)
      AV:      relevance_score >= 0.5  (AV computes per-ticker relevance explicitly)
    """
    T = ticker.upper()

    # 1. Fetch both sources
    massive_arts = news(ticker, limit=massive_limit)
    av_arts      = av_news(ticker, limit=av_limit)

    # 2. Merge + dedup by normalized title
    arts = _merge_dedup(massive_arts, av_arts)
    n_massive = len(massive_arts)
    n_av      = len(av_arts)

    # 3. Scan merged articles
    bk, fr, spam = [], [], 0
    for a in arts:
        if not _is_focused(a, T):
            continue
        blob     = a["title"] + " \n " + a["desc"]
        is_spam  = bool(_hits(blob, LAWFIRM))
        _tl      = a["title"].lower()
        is_recovery = (bool(_hits(a["title"], BK_POSITIVE))
                       or ("regain" in _tl and "compliance" in _tl and "regains" in _tl))
        b = _hits(blob, STRONG_BK)
        f = _hits(blob, STRONG_FRAUD)
        if is_spam:
            spam += 1
        if b and not is_spam and not is_recovery:
            bk.append({"date": a["date"], "kw": b, "title": a["title"][:130],
                        "source": a.get("source", "massive"),
                        "sentiment": a.get("sentiment")})
        if f and not is_spam:
            fr.append({"date": a["date"], "kw": f, "title": a["title"][:130],
                        "source": a.get("source", "massive"),
                        "sentiment": a.get("sentiment")})

    # 4. Capital raises (title-only — offerings are headline events)
    raises = []
    for a in arts:
        if not _is_focused(a, T):
            continue
        rk = _hits(a["title"], RAISE)
        if rk:
            raises.append({"date": a["date"], "kw": rk, "title": a["title"][:130],
                            "source": a.get("source", "massive")})

    # 5. Average AV sentiment for focused articles (negative = bearish signal)
    av_focused = [a for a in arts
                  if a.get("source") == "av" and _is_focused(a, T)
                  and a.get("sentiment") is not None]
    avg_sentiment = (sum(a["sentiment"] for a in av_focused) / len(av_focused)
                     if av_focused else None)

    # 6. Short interest
    si  = short_interest(ticker)
    dtc = si["days_to_cover"] if si else None

    return {
        "ticker":             T,
        "n_news":             len(arts),        # total deduped articles
        "n_news_massive":     n_massive,        # breakdown for transparency
        "n_news_av":          n_av,
        "bankruptcy_events":  bk,
        "fraud_events":       fr,
        "capital_raises":     raises,
        "lawfirm_spam":       spam,
        "short_days_to_cover":dtc,
        "short_interest":     si,
        "av_avg_sentiment":   round(avg_sentiment, 3) if avg_sentiment is not None else None,
        "api_distress":       bool(bk),
        "api_fraud":          bool(fr),
        "api_recent_raise":   bool(raises),
        "api_high_short":     bool(dtc is not None and dtc >= 10),
    }


def main():
    import sys
    for t in (sys.argv[1:] or ["BYND"]):
        e = event_scan(t)
        print(f"\n{e['ticker']}: {e['n_news']} articles "
              f"(massive={e['n_news_massive']} + av={e['n_news_av']}), "
              f"spam={e['lawfirm_spam']}, dtc={e['short_days_to_cover']}, "
              f"av_sentiment={e['av_avg_sentiment']}")
        print(f"  flags: distress={e['api_distress']} fraud={e['api_fraud']} "
              f"high_short={e['api_high_short']} raise={e['api_recent_raise']}")
        for b in e["bankruptcy_events"][:5]:
            print(f"   [BK/{b.get('source','?')}] {b['date']} {b['kw']}: {b['title']}")
        for f in e["fraud_events"][:5]:
            print(f"   [FRAUD/{f.get('source','?')}] {f['date']} {f['kw']}: {f['title']}")


if __name__ == "__main__":
    main()
