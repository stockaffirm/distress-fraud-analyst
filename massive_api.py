#!/usr/bin/env python3
"""
massive_api.py -- direct Massive API client for per-ticker calibration ground truth.

Pulls LIVE, historical signals the cached fundamentals can't see:
  * news(ticker)          -> historical headlines (going-concern / Ch11 / SEC / restatement / short-seller / delisting)
  * short_interest(ticker)-> latest days-to-cover & % of float short (a direct distress/fraud tell)

Key from stockaffirm/.env (env API_KEY); read-only external calls. Polite throttle + retry.

  python3 massive_api.py BYND      # dump the live distress/fraud read for one ticker
"""
import os, json, time, urllib.request, urllib.error

BASE = "https://api.massive.com"
_KEY = None


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


def news(ticker, limit=50):
    """Most-recent-first news headlines for a ticker (with the article's full ticker tags)."""
    d = _get(f"/v2/reference/news?ticker={ticker.upper()}&order=desc&sort=published_utc&limit={limit}")
    out = []
    for r in (d.get("results") or []):
        out.append({"date": (r.get("published_utc") or "")[:10],
                    "title": r.get("title") or "",
                    "desc": (r.get("description") or "")[:300],
                    "tickers": r.get("tickers") or [],
                    "publisher": (r.get("publisher") or {}).get("name") if isinstance(r.get("publisher"), dict) else r.get("publisher")})
    return out


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


def event_scan(ticker, limit=50):
    """Independent distress/fraud read from LIVE news + short interest -- the ground truth
    each ticker's bucket is calibrated against. Law-firm solicitations filtered as noise."""
    arts = news(ticker, limit=limit)
    T = ticker.upper()
    bk, fr, spam = [], [], 0
    for a in arts:
        # FOCUS filter: only treat an article as ABOUT this company if the queried ticker
        # is the PRIMARY subject -- first tag, or a focused (<=2-ticker) article. This kills
        # market roundups / peer stories that tag the ticker incidentally (MU on a Supermicro
        # accounting story; CVX in a fund-holdings "liquidates" piece).
        tks = [x.upper() for x in (a.get("tickers") or [])]
        focused = (not tks) or (tks[0] == T)   # primary subject only (tags are subject-ordered)
        if not focused:
            continue
        blob = a["title"] + " \n " + a["desc"]
        is_spam = bool(_hits(blob, LAWFIRM))
        _tl = a["title"].lower()
        # "regains compliance" / "regains Nasdaq compliance with bid price" = recovery, NOT distress
        is_recovery = bool(_hits(a["title"], BK_POSITIVE)) or ("regain" in _tl and "compliance" in _tl
                                                               and "regains" in _tl)
        b = _hits(blob, STRONG_BK)
        f = _hits(blob, STRONG_FRAUD)
        if is_spam:
            spam += 1
        if b and not is_spam and not is_recovery:
            bk.append({"date": a["date"], "kw": b, "title": a["title"][:130]})
        if f and not is_spam:
            fr.append({"date": a["date"], "kw": f, "title": a["title"][:130]})
    raises = []
    for a in arts:
        tks = [x.upper() for x in (a.get("tickers") or [])]
        focused = (not tks) or (tks[0] == T)   # primary subject only (tags are subject-ordered)
        if not focused:
            continue
        rk = _hits(a["title"], RAISE)        # title-only (offerings are headline events)
        if rk:
            raises.append({"date": a["date"], "kw": rk, "title": a["title"][:130]})
    si = short_interest(ticker)
    dtc = si["days_to_cover"] if si else None
    return {"ticker": ticker.upper(), "n_news": len(arts),
            "bankruptcy_events": bk, "fraud_events": fr, "capital_raises": raises, "lawfirm_spam": spam,
            "short_days_to_cover": dtc, "short_interest": si,
            "api_distress": bool(bk), "api_fraud": bool(fr),
            "api_recent_raise": bool(raises),
            "api_high_short": bool(dtc is not None and dtc >= 10)}


def main():
    import sys
    for t in (sys.argv[1:] or ["BYND"]):
        e = event_scan(t)
        print(f"\n{e['ticker']}: {e['n_news']} news, spam={e['lawfirm_spam']}, "
              f"days_to_cover={e['short_days_to_cover']}  "
              f"[distress={e['api_distress']} fraud={e['api_fraud']} high_short={e['api_high_short']}]")
        for b in e["bankruptcy_events"][:5]:
            print(f"   [BK] {b['date']} {b['kw']}: {b['title']}")
        for f in e["fraud_events"][:5]:
            print(f"   [FRAUD] {f['date']} {f['kw']}: {f['title']}")


if __name__ == "__main__":
    main()
