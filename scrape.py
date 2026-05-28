"""Scrape the full Lightyear public stock universe and sort by market cap.

Source: https://lightyear.com/en/stocks/explore  (the "Browse all stocks" page),
which lists every instrument (~6000) paginated 20 per page via ?page=N.

Run:  uv run scrape.py
Output: stocks.csv  (sorted by market cap, descending, in USD)
"""

import csv
import html
import re
import sys
import time

import requests

BASE = "https://lightyear.com/en/stocks/explore"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# Currency prefix shown in the ticker cell -> ISO code.
# Order matters: check longer/more specific tokens first.
CURRENCY_PREFIXES = [
    ("Nkr", "NOK"), ("Skr", "SEK"), ("DKr", "DKK"), ("C$", "CAD"),
    ("Fr.", "CHF"), ("Fr", "CHF"), ("zł", "PLN"), ("Ft", "HUF"),
    ("kr", "DKK"), ("$", "USD"), ("€", "EUR"), ("£", "GBP"),
]

# Approximate FX rates: USD per 1 unit of currency (mid-2026, for sorting only).
FX_TO_USD = {
    "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CHF": 1.12, "CAD": 0.73,
    "NOK": 0.092, "SEK": 0.095, "DKK": 0.145, "PLN": 0.25, "HUF": 0.0028,
}

UNIT = {"tn": 1e12, "bn": 1e9, "m": 1e6, "k": 1e3}

# Exchange suffix (after the colon in TICKER:EXCHANGE) -> country.
EXCHANGE_COUNTRY = {
    "NASDAQ": "United States", "NYSE": "United States", "ARCA": "United States",
    "BATS": "United States", "OTC": "United States",
    "LSE": "United Kingdom", "XOSL": "Norway", "XSTO": "Sweden",
    "CSE": "Denmark", "XSWX": "Switzerland", "WSE": "Poland", "BUX": "Hungary",
    "PAR": "France", "AMS": "Netherlands", "BRU": "Belgium", "XETRA": "Germany",
    "ETR": "Germany", "FRA": "Germany", "BME": "Spain", "MCE": "Spain",
    "TSX": "Canada", "TSE": "Canada", "TAL": "Estonia", "RIS": "Latvia",
    "VSE": "Lithuania", "MIL": "Italy", "LIS": "Portugal",
    "AMEX": "United States", "XGAT": "Germany", "AEX": "Netherlands",
    "XHEL": "Finland", "XLIT": "Lithuania", "XTAL": "Estonia",
    "XLIS": "Portugal", "XRIS": "Latvia", "XBRU": "Belgium", "XAMS": "Netherlands",
    "BSE": "Belgium",
}

MARKETCAP_RE = re.compile(r"([\d][\d.,]*)\s*(tn|bn|m|k)\b")


def parse_marketcap(raw):
    """'kr 844bn' / '$91bn' / 'Ft 10.838tn' -> float in original currency, or None."""
    m = MARKETCAP_RE.search(raw)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    return num * UNIT[m.group(2)]


def detect_currency(ticker_cell):
    """The ticker cell looks like 'Skr INVE B' or '£HSBA' -> ISO currency code."""
    for prefix, code in CURRENCY_PREFIXES:
        if ticker_cell.startswith(prefix):
            return code
    return None


def clean(body):
    txt = re.sub(r"<[^>]+>", "|", body)
    txt = html.unescape(txt)
    parts = [p.strip() for p in txt.split("|")]
    return [p for p in parts if p and p != "·" and p != ">"]


def parse_page(htmltext):
    rows = []
    for href, body in re.findall(r'<a[^>]*href="(/en/stock/[^"]+)"(.*?)</a>',
                                 htmltext, re.S):
        toks = clean(body)
        if len(toks) < 4:
            continue
        ticker_full = href.rsplit("/", 1)[-1]          # e.g. "INVE B:XSTO"
        ticker, _, exchange = ticker_full.partition(":")
        name = toks[0]
        ticker_cell = toks[1]
        currency = detect_currency(ticker_cell)
        sector = toks[2]
        # Find the token that looks like a market cap (has a tn/bn/m/k unit).
        mcap_raw = next((t for t in toks[3:] if MARKETCAP_RE.search(t)), "")
        idx = toks.index(mcap_raw) if mcap_raw else 3
        # explore columns after market cap: dividend yield, P/E ratio, price
        rest = toks[idx + 1:]
        div_yield = rest[0] if len(rest) > 0 else ""
        pe = rest[1] if len(rest) > 1 else ""
        price = rest[2] if len(rest) > 2 else ""

        mcap = parse_marketcap(mcap_raw)
        mcap_usd = mcap * FX_TO_USD.get(currency or "", float("nan")) if mcap else None

        rows.append({
            "name": name,
            "ticker": ticker,
            "exchange": exchange,
            "country": EXCHANGE_COUNTRY.get(exchange, ""),
            "sector": sector,
            "currency": currency or "",
            "market_cap_raw": mcap_raw,
            "market_cap_local": mcap,
            "market_cap_usd": mcap_usd,
            "dividend_yield": div_yield,
            "pe_ratio": pe,
            "price": price,
            "url": "https://lightyear.com" + href,
        })
    return rows


def scrape_all():
    session = requests.Session()
    session.headers.update(HEADERS)
    seen = {}
    page = 1
    while True:
        url = BASE if page == 1 else f"{BASE}?page={page}"
        r = session.get(url, timeout=30)
        r.raise_for_status()
        rows = parse_page(r.text)
        new = 0
        for row in rows:
            key = (row["ticker"], row["exchange"])
            if key not in seen:
                seen[key] = row
                new += 1
        print(f"page {page:>3}: {len(rows):>2} rows, {new:>2} new "
              f"(total {len(seen)})", file=sys.stderr)
        if not rows or new == 0:
            break
        page += 1
        time.sleep(0.25)
    return list(seen.values())


def main():
    stocks = scrape_all()
    stocks.sort(key=lambda s: s["market_cap_usd"] or -1, reverse=True)
    fields = ["rank", "name", "ticker", "exchange", "country", "sector",
              "currency", "market_cap_raw", "market_cap_local", "market_cap_usd",
              "dividend_yield", "pe_ratio", "price", "url"]
    with open("stocks.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, s in enumerate(stocks, 1):
            s["rank"] = i
            w.writerow({k: s.get(k, "") for k in fields})
    print(f"\nWrote {len(stocks)} stocks to stocks.csv", file=sys.stderr)
    print("\nTop 15 by market cap (USD):", file=sys.stderr)
    for s in stocks[:15]:
        cap = s["market_cap_usd"]
        cap_s = f"${cap/1e9:,.1f}bn" if cap else "n/a"
        print(f"  {s['name'][:34]:34} {s['ticker']:10} {cap_s:>12} "
              f"({s['market_cap_raw']})", file=sys.stderr)


if __name__ == "__main__":
    main()
