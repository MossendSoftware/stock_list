"""Per-country macro series: total market cap, money supply, risk-free rate.

  market cap  -> World Bank CM.MKT.LCAP.CD (listed domestic companies, US$)
  money       -> our FRED/curated money supply (relative.MONEY, annual levels)
  RFR         -> FRED IR3TIB01{cc}M156N (3-month interbank rate, % p.a.)

Writes country_report.json. Run: uv run country_data.py  (needs FRED_API_KEY)
"""

import json
import os
from collections import defaultdict
from pathlib import Path

import datetime as _dt

import requests
import yfinance as yf

from relative import MONEY

for line in Path(".env").read_text().splitlines():
    if line.startswith("FRED_API_KEY="):
        os.environ["FRED_API_KEY"] = line.split("=", 1)[1].strip()
KEY = os.environ["FRED_API_KEY"]
FRED = "https://api.stlouisfed.org/fred/series/observations"
WB = "https://api.worldbank.org/v2/country/{cc}/indicator/{ind}"

# name, World Bank code, money region, FRED risk-free-rate series or None.
# RFR = 10-year government bond yield (IRLTLT01) — the true default-free rate used
# in valuation. No clean sovereign yield on FRED for China / India / Hong Kong.
COUNTRIES = [
    ("United States", "US", "US", "IRLTLT01USM156N"),
    ("United Kingdom", "GB", "UK", "IRLTLT01GBM156N"),
    ("Euro area",      "XC", "EZ", "IRLTLT01EZM156N"),
    ("Japan",          "JP", "JP", "IRLTLT01JPM156N"),
    ("South Korea",    "KR", "KR", "IRLTLT01KRM156N"),
    ("China",          "CN", "CN", None),
    ("India",          "IN", "IN", None),
    ("Hong Kong",      "HK", "HK", None),
]
START = 2004


def wb_series(cc, ind):
    r = requests.get(WB.format(cc=cc, ind=ind),
                     params={"format": "json", "per_page": 70}, timeout=30).json()
    out = {}
    if isinstance(r, list) and len(r) > 1 and r[1]:
        for d in r[1]:
            if d["value"] is not None and int(d["date"]) >= START:
                out[int(d["date"])] = d["value"]
    return out


def wb_marketcap(cc):
    return wb_series(cc, "CM.MKT.LCAP.CD")


def index_annual(ticker, start):
    """Yahoo index -> {year: annual-average level}."""
    df = yf.Ticker(ticker).history(start=f"{start}-01-01", interval="1d",
                                   auto_adjust=True)
    buckets = defaultdict(list)
    for ts, row in df["Close"].items():
        v = float(row)
        if v == v:
            buckets[ts.year].append(v)
    return {y: sum(v) / len(v) for y, v in buckets.items()}


def backfill_marketcap(mktcap, ticker, upto):
    """Extend a market-cap series past its last year using a price index's growth.
    Returns (series, first_estimated_year or None)."""
    if not mktcap:
        return mktcap, None
    last = max(mktcap)
    idx = index_annual(ticker, last)
    if last not in idx:
        return mktcap, None
    first_est = None
    for y in range(last + 1, upto + 1):
        if y in idx:
            mktcap[y] = mktcap[last] * idx[y] / idx[last]
            first_est = first_est or y
    return mktcap, first_est


def fred_rate_annual(sid):
    """Monthly rate series -> {year: annual mean %}."""
    r = requests.get(FRED, params={"series_id": sid, "api_key": KEY,
                                   "file_type": "json", "observation_start": f"{START}-01-01"},
                     timeout=30).json()
    buckets = defaultdict(list)
    for o in r.get("observations", []):
        if o["value"] not in (".", ""):
            buckets[int(o["date"][:4])].append(float(o["value"]))
    return {y: sum(v) / len(v) for y, v in buckets.items() if v}


def fred_annual_value(sid):
    """Annual series -> {year: value}. Empty dict if series missing."""
    r = requests.get(FRED, params={"series_id": sid, "api_key": KEY,
                                   "file_type": "json", "observation_start": f"{START}-01-01"},
                     timeout=30).json()
    out = {}
    for o in r.get("observations", []):
        if o["value"] not in (".", ""):
            out[int(o["date"][:4])] = float(o["value"])
    return out


def main():
    this_year = _dt.date.today().year
    countries = []
    for name, cc, region, rfr_sid in COUNTRIES:
        mktcap = wb_marketcap(cc)
        est_from = None
        if name == "United Kingdom":  # World Bank UK series stops at 2022
            mktcap, est_from = backfill_marketcap(mktcap, "^FTAS", this_year)
        gdp = wb_series(cc, "NY.GDP.MKTP.CD")
        # government debt: gross debt (% GDP) x local-currency GDP -> debt in LCU
        debt_pct = fred_annual_value(f"GGGDTA{cc}A188N")
        gdp_lcu = wb_series(cc, "NY.GDP.MKTP.CN")
        debt_lcu = {y: debt_pct[y] / 100 * gdp_lcu[y]
                    for y in debt_pct if y in gdp_lcu}
        money = {y: v for y, v in MONEY.get(region, {}).items() if y >= START}
        rfr = fred_rate_annual(rfr_sid) if rfr_sid else {}
        countries.append({
            "name": name, "code": cc, "region": region,
            "market_cap_usd": {str(y): v for y, v in sorted(mktcap.items())},
            "market_cap_est_from": est_from,
            "gdp_usd": {str(y): v for y, v in sorted(gdp.items())},
            "govt_debt_lcu": {str(y): v for y, v in sorted(debt_lcu.items())},
            "debt_pct_gdp": {str(y): round(v, 1) for y, v in sorted(debt_pct.items())},
            "money": {str(y): v for y, v in sorted(money.items())},
            "rfr_pct": {str(y): round(v, 2) for y, v in sorted(rfr.items())},
        })
        tag = f" (est from {est_from})" if est_from else ""
        print(f"  {name:16} mktcap={len(mktcap)}y{tag} gdp={len(gdp)}y "
              f"debt={len(debt_lcu)}y money={len(money)}y rfr={len(rfr)}y")

    Path("country_report.json").write_text(json.dumps(
        {"start_year": START, "countries": countries}, indent=2))
    print("\nWrote country_report.json")


if __name__ == "__main__":
    main()
