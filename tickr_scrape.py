"""Capture full FT financials (income statement, balance sheet, cash flow; ~5y)
for every company in the small-cap buckets, one normalised JSON per ticker.

Resumable: skips tickers already saved in tickr/data/. Run: uv run tickr_scrape.py
"""

import csv
import json
import os
import re
import sys
import time
from pathlib import Path

TRAINER = Path.home() / "stock_trainer"
env = TRAINER / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if line.startswith("FT_COOKIE=") and "FT_COOKIE" not in os.environ:
            os.environ["FT_COOKIE"] = line.split("=", 1)[1].strip()

sys.path.insert(0, str(TRAINER))
import scraper  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from ft_pull import resolve_symbol, derive  # noqa: E402

BUCKETS = ["under_10M", "10M_to_25M"]
SUBVIEWS = {"income": "IncomeStatement", "balance": "BalanceSheet",
            "cashflow": "CashFlow"}
DATA_DIR = Path("tickr/data")


def slug(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def parse_statement(html):
    """Full statement table -> {periods:[...], rows:[{label,values,raw,section}]}."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="mod-ui-table")
    if table is None:
        return None
    head = table.find("thead")
    body = table.find("tbody") or table
    if head:
        period_cells = head.find_all(["th", "td"])
        trs = body.find_all("tr")
    else:
        trs = table.find_all("tr")
        period_cells = trs[0].find_all(["th", "td"]) if trs else []
        trs = trs[1:]
    periods = [c.get_text(" ", strip=True) for c in period_cells][1:]

    rows = []
    for tr in trs:
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        label = cells[0].get_text(" ", strip=True)
        if not label or label.startswith("Fiscal data as of"):
            continue
        vcells = cells[1:]
        if not vcells:  # single-cell row = section header
            rows.append({"label": label, "section": True, "values": [], "raw": []})
            continue
        raw = [c.get_text(" ", strip=True) for c in vcells]
        values = [scraper.parse_value(t) for t in raw]
        rows.append({"label": label, "section": False, "values": values, "raw": raw})
    return {"periods": periods, "rows": rows}


def fetch_statement(session, symbol, subview):
    r = session.get(scraper.FINANCIALS_URL,
                    params={"s": symbol, "subView": subview}, timeout=20)
    return parse_statement(r.text)


def main():
    if not os.environ.get("FT_COOKIE"):
        sys.exit("FT_COOKIE not set in ~/stock_trainer/.env")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = scraper.make_session()

    rows, seen = [], set()
    for b in BUCKETS:
        for r in csv.DictReader(open(f"buckets/{b}.csv")):
            key = (r["ticker"], r["exchange"])
            if key not in seen:
                seen.add(key)
                r["bucket"] = b
                rows.append(r)

    done = miss = skip = 0
    for i, r in enumerate(rows, 1):
        out = DATA_DIR / f"{slug(r['ticker'])}__{slug(r['exchange'])}.json"
        if out.exists():
            skip += 1
            continue
        sym = resolve_symbol(session, r["ticker"], r["exchange"])
        quote = None
        if sym:
            try:
                quote = scraper.fetch_quote(session, sym)
            except Exception:
                quote = None
        if not quote:
            miss += 1
            out.write_text(json.dumps({"missed": True, **r, "ft_symbol": sym}))
            print(f"[{i}/{len(rows)}] MISS {r['ticker']}:{r['exchange']}", file=sys.stderr)
            time.sleep(0.2)
            continue

        statements = {}
        for name, sub in SUBVIEWS.items():
            try:
                statements[name] = fetch_statement(session, sym, sub)
            except Exception:
                statements[name] = None
            time.sleep(0.15)

        bs = {}
        try:
            bs = scraper.fetch_balance_sheet(session, sym)
        except Exception:
            bs = {}

        rec = {
            "name": quote.name, "ly_ticker": r["ticker"], "ft_symbol": sym,
            "exchange": r["exchange"], "country": r["country"],
            "sector": r["sector"], "bucket": r["bucket"],
            "ly_market_cap_usd": float(r["market_cap_usd"]) if r["market_cap_usd"] else None,
            "price": quote.last_price, "currency": quote.currency,
            "balance_sheet_summary": bs,
            "metrics": derive(bs, quote.last_price, quote.currency),
            "statements": statements,
            "ft_url": f"https://markets.ft.com/data/equities/tearsheet/financials?s={sym}",
        }
        out.write_text(json.dumps(rec, indent=2))
        done += 1
        print(f"[{i}/{len(rows)}] OK   {sym:13} {quote.name[:32]}", file=sys.stderr)
        time.sleep(0.25)

    print(f"\nnew={done} missed={miss} skipped={skip} -> {DATA_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
