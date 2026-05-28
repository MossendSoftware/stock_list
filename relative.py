"""relative() / returns() — value money across time against its monetary context.

A nominal price is meaningless without the size of the money ocean it floats in.
These helpers restate a value, or a return, stripping out either consumer inflation
(CPI) or — the headline lens — growth in the broad money supply.

Region-aware: each market is deflated by its OWN money supply (US M2, UK M4,
Eurozone M3, Japan M2, China M2, ...). Because returns are currency-independent
ratios, no FX conversion is needed — only the correct local money-supply growth.

All series are APPROXIMATE annual anchors (broad money, local currency; CPI indices),
linearly interpolated. They're for relative ratios, not absolute figures. For
precision, swap in live central-bank / FRED data (see note at bottom).
"""

from datetime import date as _date

# ── Broad money supply, local currency (units arbitrary — only ratios matter) ──
# US M2 ($T), UK M4 (£T), Eurozone M3 (€T), Japan M2 (¥T), China M2 (¥T),
# Korea M2 (₩T), India M3 (₹T), Taiwan M2 (NT$T), Hong Kong M3 (HK$T).
MONEY = {
    "US": {2000: 4.6, 2004: 6.1, 2008: 7.5, 2012: 9.9, 2016: 12.4, 2019: 14.6,
           2020: 18.1, 2021: 20.6, 2022: 21.5, 2023: 20.8, 2024: 21.0,
           2025: 21.8, 2026: 22.2},
    "UK": {2004: 1.20, 2008: 1.80, 2012: 2.10, 2016: 2.35, 2020: 2.65,
           2022: 3.00, 2024: 3.05, 2026: 3.15},
    "EZ": {2004: 6.5, 2008: 9.0, 2012: 9.8, 2016: 11.0, 2020: 13.5,
           2022: 15.8, 2024: 16.2, 2026: 16.9},
    "JP": {2004: 695, 2008: 740, 2012: 830, 2016: 930, 2020: 1080,
           2022: 1200, 2024: 1245, 2026: 1275},
    "CN": {2004: 25, 2008: 47, 2012: 97, 2016: 155, 2020: 219,
           2022: 266, 2024: 310, 2026: 335},
    "KR": {2004: 930, 2008: 1400, 2012: 1800, 2016: 2340, 2020: 3200,
           2022: 3700, 2024: 4000, 2026: 4150},
    "IN": {2004: 20, 2008: 40, 2012: 73, 2016: 120, 2020: 175,
           2022: 215, 2024: 255, 2026: 280},
    "TW": {2004: 24, 2008: 29, 2012: 34, 2016: 41, 2020: 50,
           2022: 55, 2024: 58, 2026: 61},
    "HK": {2004: 4.2, 2008: 6.5, 2012: 9.0, 2016: 11.5, 2020: 14.5,
           2022: 16.0, 2024: 17.0, 2026: 17.8},
}

# ── CPI indices per region (arbitrary base; ratios only) ──
CPI = {
    "US": {2000: 172.2, 2004: 188.9, 2008: 215.3, 2012: 229.6, 2016: 240.0,
           2019: 255.7, 2020: 258.8, 2022: 292.7, 2024: 313.7, 2026: 328.0},
    "UK": {2004: 80, 2008: 87, 2012: 97, 2016: 101, 2020: 108, 2022: 118,
           2024: 133, 2026: 139},
    "EZ": {2004: 84, 2008: 93, 2012: 99, 2016: 100, 2020: 105, 2022: 117,
           2024: 126, 2026: 130},
    "JP": {2004: 97, 2008: 99, 2012: 97, 2016: 99, 2020: 100, 2022: 103,
           2024: 111, 2026: 115},
    "CN": {2004: 75, 2008: 88, 2012: 97, 2016: 105, 2020: 118, 2022: 122,
           2024: 126, 2026: 129},
}

CURRENCY = {"US": "USD", "UK": "GBP", "EZ": "EUR", "JP": "JPY", "CN": "CNY",
            "KR": "KRW", "IN": "INR", "TW": "TWD", "HK": "HKD"}

# Override the anchors above with live FRED data when fetch_money.py has run.
import json as _json  # noqa: E402
import os as _os  # noqa: E402

MONEY_SOURCE = {r: "anchor" for r in MONEY}
_path = _os.path.join(_os.path.dirname(__file__), "money_supply.json")
if _os.path.exists(_path):
    _data = _json.load(open(_path))
    for _r, _tbl in _data["money"].items():
        MONEY[_r] = {int(_y): float(_v) for _y, _v in _tbl.items()}
    MONEY_SOURCE.update(_data.get("_sources", {}))


def _to_year(d):
    if isinstance(d, (int, float)):
        return float(d)
    if isinstance(d, _date):
        return d.year + (d.timetuple().tm_yday - 1) / 365.0
    s = str(d).strip()
    if "-" in s:
        d = _date.fromisoformat(s)
        return d.year + (d.timetuple().tm_yday - 1) / 365.0
    return float(s)


def _index(table, year):
    years = sorted(table)
    if year <= years[0]:
        return table[years[0]]
    if year >= years[-1]:
        return table[years[-1]]
    lo = max(y for y in years if y <= year)
    hi = min(y for y in years if y >= year)
    if lo == hi:
        return table[lo]
    frac = (year - lo) / (hi - lo)
    return table[lo] + frac * (table[hi] - table[lo])


def _multiple(table, y_from, y_to):
    return _index(table, y_to) / _index(table, y_from)


def relative(value, date, to_date=None, basis="m2", region="US"):
    """Restate `value` (as of `date`) into `to_date`'s terms for a region."""
    table = MONEY[region] if basis.lower() == "m2" else CPI[region]
    y_from = _to_year(date)
    y_to = _to_year(to_date) if to_date is not None else _to_year(_date.today())
    return value * _multiple(table, y_from, y_to)


def returns(start_value, start_date, end_value, end_date=None, region="US"):
    """Nominal vs real (CPI- and money-supply-adjusted) return for a region.

    The money line is "return after money creation": the gain net of that
    region's broad-money expansion. Returns total-return % and annualised CAGR.
    """
    y0 = _to_year(start_date)
    y1 = _to_year(end_date) if end_date is not None else _to_year(_date.today())
    years = max(y1 - y0, 1e-9)

    def pack(mult):
        cagr = mult ** (1 / years) - 1 if mult > 0 else float("nan")
        return {"multiple": mult, "total_pct": (mult - 1) * 100,
                "cagr_pct": cagr * 100}

    nominal = end_value / start_value
    out = {"years": years, "region": region, "nominal": pack(nominal)}
    if region in CPI:
        out["cpi"] = pack(nominal / _multiple(CPI[region], y0, y1))
    out["m2"] = pack(nominal / _multiple(MONEY[region], y0, y1))
    out["money_growth_pct"] = (_multiple(MONEY[region], y0, y1) - 1) * 100
    return out


def report(start_value, start_date, end_value, end_date=None, region="US"):
    r = returns(start_value, start_date, end_value, end_date, region)
    y1 = end_date if end_date is not None else int(_to_year(_date.today()))
    print(f"{start_value:,.2f} ({start_date})  ->  {end_value:,.2f} ({y1})"
          f"   over {r['years']:.0f}y   [{region} / {CURRENCY[region]}, "
          f"money +{r['money_growth_pct']:,.0f}%]")
    rows = [("Nominal", "nominal"), ("Real, CPI-adjusted", "cpi"),
            ("Real, after money creation", "m2")]
    print(f"  {'':34}{'total':>12}{'CAGR':>10}{'multiple':>11}")
    for name, k in rows:
        if k not in r:
            continue
        d = r[k]
        print(f"  {name:34}{d['total_pct']:>11,.0f}%{d['cagr_pct']:>9.1f}%"
              f"{d['multiple']:>10.2f}x")


if __name__ == "__main__":
    report(52, 2004, 1000, 2026, region="US")

# Live data: US via FRED (fredgraph.csv?id=M2SL / CPIAUCSL). UK M4: Bank of England
# series LPMVWYH. Eurozone M3: ECB BSI. Japan M2: BoJ. China M2: PBoC. All free.
