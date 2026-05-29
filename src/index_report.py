"""Build the index real-return dataset: nominal vs after-money-creation, by region.

Fetches each index (total-return variant where one exists on Yahoo), deflates by
its own money supply via relative.returns(), and writes index_report.json.
Slow part (network) lives here; the PDF/HTML renderers read the JSON.

Run: uv run index_report.py
"""

import datetime as dt
import json
import time

from realreturn import fetch_adjclose, price_near
from relative import returns, CURRENCY
from paths import DATA

START = 2004

# display name, yahoo ticker, region, basis ("TR" total-return / "price")
INDEXES = [
    ("S&P 500",        "^SP500TR",  "US", "TR"),
    ("NASDAQ Composite", "^IXIC",   "US", "price"),
    ("Russell 2000",   "^RUT",      "US", "price"),
    ("FTSE 100",       "^FTSE",     "UK", "price"),
    ("FTSE 250",       "^FTMC",     "UK", "price"),
    ("DAX",            "^GDAXI",    "EZ", "TR"),
    ("Euro Stoxx 50",  "SX5T.Z",    "EZ", "TR"),
    ("CAC 40",         "^FCHI",     "EZ", "price"),
    ("Nikkei 225",     "^N225",     "JP", "price"),
    ("Taiwan",         "^TWII",     "TW", "price"),
    ("KOSPI",          "^KS11",     "KR", "price"),
    ("Hang Seng",      "^HSI",      "HK", "price"),
    ("Sensex",         "^BSESN",    "IN", "price"),
    ("Shanghai",       "000001.SS", "CN", "price"),
]


def build_row(name, ticker, region, basis):
    series = fetch_adjclose(ticker, start_year=START)
    if not series:
        return None
    d0, p0 = price_near(series, dt.date(START, 1, 1))
    d1, p1 = series[-1]
    y0 = d0.year + d0.timetuple().tm_yday / 365
    y1 = d1.year + d1.timetuple().tm_yday / 365
    r = returns(p0, y0, p1, y1, region=region)
    return {
        "name": name, "ticker": ticker, "region": region,
        "currency": CURRENCY[region], "basis": basis,
        "start": d0.isoformat(), "end": d1.isoformat(), "years": r["years"],
        "money_growth_pct": r["money_growth_pct"],
        "nominal": r["nominal"], "m2": r["m2"],
        "cpi": r.get("cpi"),
    }


def main():
    rows = []
    for name, ticker, region, basis in INDEXES:
        row = build_row(name, ticker, region, basis)
        if row:
            rows.append(row)
            print(f"  {name:18} {region}  nominal {row['nominal']['total_pct']:>7,.0f}%"
                  f"  real {row['m2']['total_pct']:>7,.0f}%")
        else:
            print(f"  {name:18} no data")
        time.sleep(1)

    out = {"generated": dt.date.today().isoformat(), "start_year": START, "rows": rows}
    with open(DATA / "index_report.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote index_report.json ({len(rows)} indexes)")


if __name__ == "__main__":
    main()
