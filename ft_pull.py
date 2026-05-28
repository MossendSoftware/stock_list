"""Pull FT financials for the small-cap buckets, reusing stock_trainer's scraper.

Reads buckets/under_10M.csv + buckets/10M_to_25M.csv, maps each Lightyear
ticker to an FT symbol (trying candidate exchange suffixes until one resolves),
scrapes the FT summary quote + balance sheet, derives a few valuation metrics,
and writes ft_financials.json.

Needs FT_COOKIE — loaded from ~/stock_trainer/.env. Run: uv run ft_pull.py
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

TRAINER = Path.home() / "stock_trainer"

# Load FT_COOKIE from the trainer's .env before importing its scraper.
env = TRAINER / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line.startswith("FT_COOKIE=") and "FT_COOKIE" not in os.environ:
            os.environ["FT_COOKIE"] = line.split("=", 1)[1].strip()

sys.path.insert(0, str(TRAINER))
import scraper  # noqa: E402

SEARCH_URL = "https://markets.ft.com/data/searchapi/searchsecurities"

# Lightyear exchange code -> FT symbol-suffixes to prefer, most-preferred first.
# FT symbols come from its search API; this just picks the best listing per name.
FT_SUFFIX_PREF = {
    "NASDAQ": ["NSQ", "NAQ"],
    "NYSE": ["NYQ", "NYS"],
    "AMEX": ["ASE", "ASQ", "PCQ"],
    "OTC": ["OBB", "PNK", "OTC"],
    "XETRA": ["GER", "ETR"],
    "PAR": ["PAR"],
    "XOSL": ["OSL"],
    "BUX": ["BUD"],
    "XLIT": ["VIL"],
    "XTAL": ["TAL"],
    "XRIS": ["RIS"],
}

BUCKETS = ["under_10M", "10M_to_25M"]


def resolve_symbol(session, ticker, exchange):
    """Use FT's search API to find the canonical FT symbol for a ticker.

    Prefers an Equities listing whose symbol prefix exactly matches the ticker,
    on a stock exchange consistent with the Lightyear exchange.
    """
    try:
        r = session.get(SEARCH_URL, params={"query": ticker}, timeout=15)
        hits = json.loads(r.text).get("data", {}).get("security", [])
    except Exception:
        return None
    equities = [h for h in hits
                if h.get("assetClass") == "Equities" and h.get("symbol")]
    # exact ticker match before the colon
    exact = [h for h in equities
             if h["symbol"].split(":")[0].upper() == ticker.upper()]
    pool = exact or equities
    if not pool:
        return None
    prefs = FT_SUFFIX_PREF.get(exchange, [])

    def rank(h):
        suf = h["symbol"].split(":")[-1]
        return prefs.index(suf) if suf in prefs else len(prefs)

    return sorted(pool, key=rank)[0]["symbol"]


def derive(bs, price, currency):
    """Compute the trainer's balance-sheet metrics; tolerate missing rows."""
    ta = bs.get("total_assets")
    tl = bs.get("total_liabilities")
    tca = bs.get("total_current_assets")
    tcl = bs.get("total_current_liabilities")
    sh = bs.get("shares_outstanding")
    out = {}
    if ta is not None and tl is not None:
        out["net_assets"] = ta - tl
        equity = ta - tl
        if sh:
            mult = 100 if currency in ("GBX", "GBp") else 1  # pence vs major unit
            bvps = (equity / sh) * mult
            out["book_value_per_share"] = bvps
            if price and bvps:
                out["price_to_book"] = price / bvps
    if tca is not None and tcl:
        out["current_ratio"] = tca / tcl
    if tl is not None and ta is not None:
        eq = ta - tl
        if eq:
            out["debt_to_equity"] = tl / eq
    if tca is not None and tl is not None and sh:
        out["ncav_per_share"] = ((tca - tl) / sh) * (
            100 if currency in ("GBX", "GBp") else 1)
    return out


def main():
    if not os.environ.get("FT_COOKIE"):
        sys.exit("FT_COOKIE not set. Paste the cookie into ~/stock_trainer/.env first.")
    session = scraper.make_session()

    rows = []
    seen = set()
    for b in BUCKETS:
        for r in csv.DictReader(open(f"buckets/{b}.csv")):
            key = (r["ticker"], r["exchange"])
            if key in seen:
                continue
            seen.add(key)
            r["bucket"] = b
            rows.append(r)

    results, failures = [], []
    for i, r in enumerate(rows, 1):
        ft_symbol = resolve_symbol(session, r["ticker"], r["exchange"])
        quote = bs = None
        if ft_symbol:
            try:
                quote = scraper.fetch_quote(session, ft_symbol)
            except Exception:
                quote = None
            if quote:
                try:
                    bs = scraper.fetch_balance_sheet(session, ft_symbol)
                except Exception:
                    bs = {}
        if not quote:
            failures.append({**r, "ft_symbol": ft_symbol})
            print(f"[{i}/{len(rows)}] MISS {r['ticker']}:{r['exchange']} "
                  f"(resolved={ft_symbol})", file=sys.stderr)
            continue
        rec = {
            "name": quote.name,
            "ly_ticker": r["ticker"],
            "ft_symbol": ft_symbol,
            "exchange": r["exchange"],
            "country": r["country"],
            "sector": r["sector"],
            "bucket": r["bucket"],
            "ly_market_cap_usd": float(r["market_cap_usd"]) if r["market_cap_usd"] else None,
            "price": quote.last_price,
            "currency": quote.currency,
            "balance_sheet": bs or {},
            "metrics": derive(bs or {}, quote.last_price, quote.currency),
            "ft_url": f"https://markets.ft.com/data/equities/tearsheet/summary?s={ft_symbol}",
        }
        results.append(rec)
        print(f"[{i}/{len(rows)}] OK   {ft_symbol:14} {quote.name[:34]}", file=sys.stderr)
        time.sleep(0.3)

    json.dump({"results": results, "failures": failures},
              open("ft_financials.json", "w"), indent=2)
    print(f"\n{len(results)} pulled, {len(failures)} missed -> ft_financials.json",
          file=sys.stderr)


if __name__ == "__main__":
    main()
