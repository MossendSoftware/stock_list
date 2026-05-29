# stock-list

A research toolkit that scrapes global market data, builds static HTML dashboards,
and exposes the same data as terminal tables and charts.

Three views:

- **Index real returns** — global index returns deflated by broad-money growth (and CPI).
- **Micro-cap screener** — FT fundamentals for sub-$25M stocks, with value/distress flags.
- **Country macro** — market cap vs. money supply vs. GDP vs. risk-free rates.

The recurring theme is *real* returns: nominal gains stripped of the money-supply
growth behind them.

## Layout

```
src/      all Python (run via `uv run src/<script>.py`, or use make targets)
data/     committed inputs + scraped data — CSVs, JSON reports, tickr/data/*.json
output/   generated HTML/PDF/charts — gitignored, rebuilt with `make build`
```

Paths are anchored to the repo root in `src/paths.py`, so scripts work from any CWD.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13.

```bash
make install        # uv sync
```

Most commands read the committed `data/` and need no secrets. The **scrape** targets
need a `.env` in the repo root (git-ignored):

```
FRED_API_KEY=...    # money + country macro (fred.stlouisfed.org/docs/api)
```

> **FT screener dependency:** `screener-scrape` reuses a `scraper` module and an
> `FT_COOKIE` from a separate `~/stock_trainer` repo (added to `sys.path` at runtime).
> Without that repo present, the other stages still work — the screener just can't
> be re-scraped (its captured data in `data/tickr/data/` is already committed).

## Run

```bash
make help           # list every target
make serve          # dashboards at http://127.0.0.1:8000 (PORT=8000)
make build          # regenerate output/ from data/ (no network)
```

Routes: `/index-returns`, `/screener`, `/screener/<ticker>`, `/countries`,
`/countries/<code>`, `/countries/compare`, `/countries/debt`.

## Terminal views

Print the same data as tables/charts — handy for piping or quick lookups.

```bash
make indices                              # index real returns
make countries                            # country macro overview
make countries CODE=US                    # one country, year by year
make screener-table                       # full screener
make screener-table FILTER=net-net SORT=cap LIMIT=20
make ticker SYM=VYNE                      # one ticker's signals
make real-return SYM=COST FROM=2015 TO=2026   # real return of an equity (fetches prices)
```

`FILTER` ∈ `below-book net-net low-debt distressed`; `SORT` ∈ `cap pb de cr loss`.
Or call directly, e.g. `uv run src/cli.py screener --filter net-net --sort cap --limit 20`.

### ASCII charts

```bash
make plot-country CODE=US                 # market cap vs money supply, indexed
make plot-country CODE=US METRIC=cap-gdp  # market cap vs GDP, in $ trillion
make plot-indices                         # index return multiples (bar)
make plot-indices METRIC=nominal          # METRIC=m2 (default) | cpi | nominal
```

### Real return, programmatically

`real_return()` in `src/realreturn.py` is the reusable core: give it an equity and
its price at two dates, and it returns the return net of money-supply growth.

```python
from realreturn import real_return
r = real_return("COST", "2015-01-02", 113.82, "2026-05-28", 995.20)
r["m2"]["total_pct"]   # real return after money creation; r["nominal"] is the gross figure
```

## Refresh the data

Each stage is a make target; run individually or chain with `make refresh`
(re-scrapes everything, then rebuilds — slow, needs the FRED key + FT setup).

| Target            | Output (under `data/`)          | Network |
|-------------------|---------------------------------|---------|
| `scrape`          | `stocks.csv`                    | yes     |
| `buckets`         | `buckets/`, `buckets_simple/`   | no      |
| `money`           | `money_supply.json`             | FRED    |
| `index-data`      | `index_report.json`             | yes     |
| `country-data`    | `country_report.json`           | FRED    |
| `screener-scrape` | `tickr/data/*.json` (resumable) | FT      |
| `build`           | → `output/` HTML/PDF/charts     | no      |
