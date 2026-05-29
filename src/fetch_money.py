"""Pull money-supply series from FRED -> money_supply.json (loaded by relative.py).

US uses M2 (M2SL level) — the thesis metric. UK/Euro area/Japan/Korea use the
OECD harmonised Broad Money series, supplied by FRED as month-over-month growth
rates, which we compound into an index level (only ratios matter downstream).

China/India/Taiwan/Hong Kong have no current FRED series (FRED's stop in 2018),
so those keep curated official anchors defined here.

Run: uv run fetch_money.py   (needs FRED_API_KEY in .env)
"""

import json
import os

import requests

from paths import DATA, ENV

for line in ENV.read_text().splitlines():
    if line.startswith("FRED_API_KEY="):
        os.environ["FRED_API_KEY"] = line.split("=", 1)[1].strip()
KEY = os.environ["FRED_API_KEY"]
API = "https://api.stlouisfed.org/fred/series/observations"

# region -> (series_id, kind). kind "level" = use values; "growth" = compound MoM %.
FRED_SERIES = {
    "US": ("M2SL", "level"),
    "UK": ("MABMM301GBM657S", "growth"),
    "EZ": ("MABMM301EZM657S", "growth"),
    "JP": ("MABMM301JPM657S", "growth"),
    "KR": ("MABMM301KRM657S", "growth"),
}

# FRED lacks current comparable series for these — curated official anchors
# (broad money, local currency $T-equivalent; approximate, for ratios only).
CURATED = {
    "CN": {2004: 25.3, 2008: 47.5, 2012: 97.4, 2016: 155.0, 2020: 218.7,
           2022: 266.4, 2024: 313.5, 2026: 332.0},   # PBoC M2 (¥T)
    "IN": {2004: 20.0, 2008: 40.0, 2012: 73.0, 2016: 120.0, 2020: 175.0,
           2022: 215.0, 2024: 257.0, 2026: 280.0},   # RBI M3 (₹T)
    "TW": {2004: 24.0, 2008: 29.0, 2012: 34.0, 2016: 41.0, 2020: 50.0,
           2022: 55.0, 2024: 58.0, 2026: 61.0},       # CBC M2 (NT$T)
    "HK": {2004: 4.2, 2008: 6.5, 2012: 9.0, 2016: 11.5, 2020: 14.5,
           2022: 16.0, 2024: 17.0, 2026: 17.8},       # HKMA M3 (HK$T)
}


def fetch_obs(series_id):
    r = requests.get(API, params={"series_id": series_id, "api_key": KEY,
                                  "file_type": "json", "observation_start": "1999-01-01"},
                     timeout=30)
    r.raise_for_status()
    return [(o["date"], o["value"]) for o in r.json()["observations"]]


def annual_levels(series_id, kind):
    """-> {year: index level}, taking the last observation of each year."""
    obs = fetch_obs(series_id)
    monthly = []  # (year, month, level)
    if kind == "level":
        for date, val in obs:
            if val not in (".", ""):
                y, m, _ = date.split("-")
                monthly.append((int(y), int(m), float(val)))
    else:  # growth: compound MoM % into an index starting at 100
        level = 100.0
        started = False
        for date, val in obs:
            if val in (".", ""):
                continue
            if started:
                level *= (1 + float(val) / 100)
            started = True
            y, m, _ = date.split("-")
            monthly.append((int(y), int(m), level))
    out = {}
    for y, m, lv in monthly:
        out[y] = lv  # last write per year = latest month seen (obs are ascending)
    return out


def main():
    money = {}
    for region, (sid, kind) in FRED_SERIES.items():
        levels = annual_levels(sid, kind)
        money[region] = {str(y): round(v, 4) for y, v in levels.items()}
        yrs = sorted(levels)
        print(f"{region}: {sid:18} {yrs[0]}..{yrs[-1]} "
              f"({len(yrs)}y, {kind})")
    for region, anchors in CURATED.items():
        money[region] = {str(y): v for y, v in anchors.items()}
        print(f"{region}: curated anchors {min(anchors)}..{max(anchors)}")

    meta = {"_sources": {r: s for r, (s, _) in FRED_SERIES.items()}}
    meta["_sources"].update({r: "curated" for r in CURATED})
    out = {"money": money, **meta}
    (DATA / "money_supply.json").write_text(json.dumps(out, indent=2))
    print("\nWrote money_supply.json")


if __name__ == "__main__":
    main()
