"""Real (money-supply-adjusted) total return for a stock, via Yahoo + relative().

Yahoo's chart API gives a split- AND dividend-adjusted close (total return),
which is the correct input. We take the adjusted close near a start and end date,
then run it through relative.returns() to strip out money-supply growth.

Usage:
  uv run realreturn.py COST            # max history -> today
  uv run realreturn.py TXMD 2019 2026
"""

import datetime as dt
import sys

import yfinance as yf

from relative import returns


def fetch_adjclose(yahoo_ticker, start_year=1990):
    """-> sorted list of (date, adj_close), dividend+split adjusted."""
    df = yf.Ticker(yahoo_ticker).history(
        start=f"{start_year}-01-01", interval="1d", auto_adjust=True)
    out = []
    for ts, row in df["Close"].items():
        v = float(row)
        if v == v and v > 0:  # skip NaN / zero
            out.append((ts.date(), v))
    return out


def price_near(series, target):
    """Adjusted close on the trading day nearest `target` (a date)."""
    return min(series, key=lambda da: abs((da[0] - target).days))


def real_return(equity, start_date, start_price, end_date, end_price, region=None):
    """Real (money-supply-deflated) total return of an equity between two priced dates.

    Given an equity and its price at two dates, strip out the region's broad-money
    growth to get the *actual* return, not the nominal one. `region` defaults to the
    equity's monetary region (INDEX_REGION), falling back to US.

    Dates may be years (2019), ISO strings ("2019-06-30"), or datetime.date.
    Returns relative.returns()'s dict: nominal / cpi / m2 each with multiple,
    total_pct, cagr_pct. The headline real rate is the "m2" entry.
    """
    region = region or INDEX_REGION.get(str(equity).upper(), "US")
    return returns(start_price, start_date, end_price, end_date, region=region)


def analyze(yahoo_ticker, start=None, end=None, region=None):
    series = fetch_adjclose(yahoo_ticker, start_year=(start or 1990))
    if not series:
        print(f"{yahoo_ticker}: no price data")
        return
    first, last = series[0][0], series[-1][0]
    start_d = dt.date(start, 1, 1) if start else first
    end_d = dt.date(end, 12, 31) if end else last
    d0, p0 = price_near(series, start_d)
    d1, p1 = price_near(series, end_d)

    r = real_return(yahoo_ticker, d0, p0, d1, p1, region=region)
    region = r["region"]
    print(f"\n{yahoo_ticker}  (adj close, total return)  "
          f"[{region}, money +{r['money_growth_pct']:,.0f}%]")
    print(f"  {d0}  {p0:>10,.2f}   ->   {d1}  {p1:>10,.2f}   over {r['years']:.1f}y")
    print(f"  {'':34}{'total':>12}{'CAGR':>9}{'multiple':>11}")
    for name, k in [("Nominal", "nominal"),
                    ("Real, CPI-adjusted", "cpi"),
                    ("Real, after money creation", "m2")]:
        if k not in r:
            continue
        d = r[k]
        print(f"  {name:34}{d['total_pct']:>11,.0f}%{d['cagr_pct']:>8.1f}%"
              f"{d['multiple']:>10.2f}x")


# Yahoo index symbol -> monetary region used to deflate it.
INDEX_REGION = {
    "^GSPC": "US", "^IXIC": "US", "^DJI": "US", "^RUT": "US",
    "^FTSE": "UK", "^FTMC": "UK",
    "^GDAXI": "EZ", "^FCHI": "EZ", "^STOXX50E": "EZ", "^IBEX": "EZ", "^AEX": "EZ",
    "^N225": "JP", "^HSI": "HK", "000001.SS": "CN", "^KS11": "KR",
    "^BSESN": "IN", "^TWII": "TW",
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: uv run realreturn.py TICKER [start_year] [end_year] [REGION]")
    tk = sys.argv[1].upper()
    s = int(sys.argv[2]) if len(sys.argv) > 2 else None
    e = int(sys.argv[3]) if len(sys.argv) > 3 else None
    region = sys.argv[4].upper() if len(sys.argv) > 4 else INDEX_REGION.get(tk, "US")
    analyze(tk, s, e, region=region)
