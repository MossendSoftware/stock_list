# stock-list

A research toolkit that scrapes global market data, builds static HTML dashboards,
and exposes the same data as terminal tables.

Three views:

- **Index real returns** — global index returns deflated by broad-money growth (and CPI).
- **Micro-cap screener** — FT fundamentals for sub-$25M stocks, with value/distress flags.
- **Country macro** — market cap vs. money supply vs. GDP vs. risk-free rates.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13.

```bash
make install        # uv sync
```

Scrape targets need a `.env` in the repo root (git-ignored):

```
FRED_API_KEY=...    # money + country macro (fred.stlouisfed.org/docs/api)
FT_COOKIE=...        # FT financials for the screener (browser session cookie)
```

`indices`, `countries`, `screener-table`, `ticker`, and `build` need no secrets —
they read the committed JSON/CSV.

## Run

```bash
make help           # list every target
make serve          # dashboards at http://127.0.0.1:8000 (PORT=8000)
make build          # regenerate all HTML/PDF from existing JSON (no network)
```

Routes: `/index-returns`, `/screener`, `/screener/<ticker>`, `/countries`,
`/countries/<code>`, `/countries/compare`, `/countries/debt`.

## Terminal views

`cli.py` prints the same data as tables — handy for piping or quick lookups.

```bash
make indices                              # index real returns
make countries                            # country macro overview
make countries CODE=US                    # one country, year by year
make screener-table                       # full screener
make screener-table FILTER=net-net SORT=cap LIMIT=20
make ticker SYM=VYNE                      # one ticker's signals
```

`FILTER` is one of `below-book net-net low-debt distressed`; `SORT` is one of
`cap pb de cr loss`. Or call directly:
`uv run cli.py screener --filter net-net --sort cap --limit 20`.

### ASCII charts

```bash
make plot-country CODE=US                 # market cap vs money supply, indexed
make plot-indices                         # index return multiples (bar)
make plot-indices METRIC=nominal          # METRIC=m2 (default) | cpi | nominal
```

## Refresh the data

Each stage is a make target; run individually or chain with `make refresh`
(re-scrapes everything, then rebuilds — slow, needs both secrets).

| Target            | Output                          | Network |
|-------------------|---------------------------------|---------|
| `scrape`          | `stocks.csv`                    | yes     |
| `buckets`         | `buckets/`, `buckets_simple/`   | no      |
| `money`           | `money_supply.json`             | FRED    |
| `index-data`      | `index_report.json`             | yes     |
| `country-data`    | `country_report.json`           | FRED    |
| `screener-scrape` | `tickr/data/*.json` (resumable) | FT      |
| `build`           | all HTML/PDF/charts             | no      |
