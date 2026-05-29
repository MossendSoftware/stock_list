"""Split a stocks CSV into market-cap bucket CSVs (USD).

Usage: uv run buckets.py [source.csv] [out_dir]
Defaults to the software/IT-filtered list -> buckets_simple/.
"""
import csv
import os
import sys

M = 1_000_000
BUCKETS = [
    ("under_10M", 0, 10 * M),
    ("10M_to_25M", 10 * M, 25 * M),
    ("25M_to_50M", 25 * M, 50 * M),
    ("50M_to_100M", 50 * M, 100 * M),
]
from paths import DATA

SRC = sys.argv[1] if len(sys.argv) > 1 else str(DATA / "stocks_simple.csv")
OUT = sys.argv[2] if len(sys.argv) > 2 else str(DATA / "buckets_simple")

rows = list(csv.DictReader(open(SRC)))
fields = list(rows[0].keys())
os.makedirs(OUT, exist_ok=True)

for name, lo, hi in BUCKETS:
    sel = [r for r in rows if r["market_cap_usd"]
           and lo <= float(r["market_cap_usd"]) < hi]
    path = os.path.join(OUT, f"{name}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(sel)
    print(f"{path:28} {len(sel):>4} stocks")
