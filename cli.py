"""Terminal views over the same data the HTML reports use.

Reads index_report.json, country_report.json and tickr/data/*.json and prints
formatted tables. No network access — run the scrape/build make targets first.

Usage:
  uv run cli.py indices
  uv run cli.py countries [CODE]
  uv run cli.py screener [--filter below-book|net-net|low-debt|distressed]
                         [--sort cap|pb|de|cr|loss] [--limit N]
  uv run cli.py ticker SYMBOL
"""

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from screen import compute_signals

ROOT = Path(__file__).parent
INDEX_JSON = ROOT / "index_report.json"
COUNTRY_JSON = ROOT / "country_report.json"
TICKR_DATA = ROOT / "tickr" / "data"

console = Console()


def _load(path):
    if not path.exists():
        console.print(f"[red]Missing {path.name}.[/red] Run the matching make target first.")
        sys.exit(1)
    return json.loads(path.read_text())


def _num(v, fmt="{:.2f}"):
    return fmt.format(v) if isinstance(v, (int, float)) else "—"


# ── indices ────────────────────────────────────────────────────────────────
def cmd_indices(_args):
    d = _load(INDEX_JSON)
    t = Table(title=f"Index real returns  (since {d['start_year']}, generated {d['generated']})")
    t.add_column("Index")
    t.add_column("Region")
    t.add_column("Basis")
    t.add_column("Money +%", justify="right")
    t.add_column("Nominal ×", justify="right")
    t.add_column("Nominal CAGR", justify="right")
    t.add_column("Real (money) ×", justify="right", style="bold")
    t.add_column("Real (CPI) ×", justify="right")
    for r in d["rows"]:
        nominal = r.get("nominal") or {}
        m2 = r.get("m2") or {}
        cpi = r.get("cpi") or {}
        t.add_row(
            r["name"], r["region"], r["basis"],
            _num(r.get("money_growth_pct"), "{:.0f}%"),
            _num(nominal.get("multiple"), "{:.2f}×"),
            _num(nominal.get("cagr_pct"), "{:.1f}%"),
            _num(m2.get("multiple"), "{:.2f}×"),
            _num(cpi.get("multiple"), "{:.2f}×"),
        )
    console.print(t)


# ── countries ──────────────────────────────────────────────────────────────
def _latest_year(series):
    if not series:
        return None, None
    y = max(series, key=int)
    return y, series[y]


def cmd_countries(args):
    d = _load(COUNTRY_JSON)
    if args.code:
        return _country_detail(d, args.code.upper())
    t = Table(title=f"Country macro — latest year  (series from {d['start_year']})")
    t.add_column("Country")
    t.add_column("Year", justify="right")
    t.add_column("Mkt cap $", justify="right")
    t.add_column("GDP $", justify="right")
    t.add_column("Cap/GDP", justify="right", style="bold")
    t.add_column("Debt/GDP", justify="right")
    t.add_column("10y rate", justify="right")
    for c in d["countries"]:
        yr, cap = _latest_year(c.get("market_cap_usd"))
        _, gdp = _latest_year(c.get("gdp_usd"))
        capgdp = (cap / gdp * 100) if cap and gdp else None
        _, debt = _latest_year(c.get("debt_pct_gdp"))
        _, rfr = _latest_year(c.get("rfr_pct"))
        t.add_row(
            f"{c['name']} ({c['code']})", yr or "—",
            _num(cap / 1e12, "${:.1f}T") if cap else "—",
            _num(gdp / 1e12, "${:.1f}T") if gdp else "—",
            _num(capgdp, "{:.0f}%"),
            _num(debt, "{:.0f}%"),
            _num(rfr, "{:.2f}%"),
        )
    console.print(t)


def _country_detail(d, code):
    c = next((x for x in d["countries"] if x["code"] == code), None)
    if not c:
        codes = ", ".join(x["code"] for x in d["countries"])
        console.print(f"[red]No country '{code}'.[/red] Available: {codes}")
        sys.exit(1)
    t = Table(title=f"{c['name']} ({c['code']}) — year by year")
    t.add_column("Year", justify="right")
    t.add_column("Mkt cap $", justify="right")
    t.add_column("GDP $", justify="right")
    t.add_column("Cap/GDP", justify="right", style="bold")
    t.add_column("Debt/GDP", justify="right")
    t.add_column("10y rate", justify="right")
    cap, gdp, debt, rfr = (c.get(k, {}) for k in
                           ("market_cap_usd", "gdp_usd", "debt_pct_gdp", "rfr_pct"))
    for y in sorted(cap, key=int):
        capgdp = (cap[y] / gdp[y] * 100) if cap.get(y) and gdp.get(y) else None
        t.add_row(
            y,
            _num(cap[y] / 1e12, "${:.2f}T") if cap.get(y) else "—",
            _num(gdp.get(y, 0) / 1e12, "${:.2f}T") if gdp.get(y) else "—",
            _num(capgdp, "{:.0f}%"),
            _num(debt.get(y), "{:.0f}%"),
            _num(rfr.get(y), "{:.2f}%"),
        )
    console.print(t)


# ── screener ───────────────────────────────────────────────────────────────
FILTERS = {
    "below-book": "flag_below_book",
    "net-net": "flag_net_net",
    "low-debt": "flag_low_debt",
    "distressed": "flag_distressed",
}
SORTS = {
    "cap": ("ly_market_cap_usd", True),
    "pb": ("price_to_book", False),
    "de": ("debt_to_equity", False),
    "cr": ("current_ratio", True),
    "loss": ("loss_years", True),
}


def _load_tickrs():
    if not TICKR_DATA.exists():
        console.print(f"[red]Missing {TICKR_DATA}.[/red] Run `make screener-scrape` first.")
        sys.exit(1)
    out = []
    for f in sorted(TICKR_DATA.glob("*.json")):
        d = json.loads(f.read_text())
        if d.get("missed"):
            continue
        out.append((d, compute_signals(d)))
    return out


def cmd_screener(args):
    recs = _load_tickrs()
    if args.filter:
        flag = FILTERS[args.filter]
        recs = [(r, s) for r, s in recs if s.get(flag)]

    if args.sort:
        key, reverse = SORTS[args.sort]
        in_sig = key in ("price_to_book", "debt_to_equity", "current_ratio", "loss_years")

        def sortkey(item):
            rec, sig = item
            v = (sig if in_sig else rec).get(key)
            return v if isinstance(v, (int, float)) else (float("-inf") if reverse else float("inf"))
        recs.sort(key=sortkey, reverse=reverse)
    else:
        recs.sort(key=lambda x: x[0]["name"].lower())

    if args.limit:
        recs = recs[: args.limit]

    title = "Micro-cap screener"
    if args.filter:
        title += f"  ·  {args.filter}"
    t = Table(title=f"{title}  ({len(recs)} shown)")
    t.add_column("Company")
    t.add_column("FT sym")
    t.add_column("Bucket")
    t.add_column("Mkt cap", justify="right")
    t.add_column("P/B", justify="right")
    t.add_column("D/E", justify="right")
    t.add_column("Curr.", justify="right")
    t.add_column("Loss yr", justify="right")
    t.add_column("Flags")
    for rec, sig in recs:
        cap = rec.get("ly_market_cap_usd")
        flags = ",".join(k.replace("flag_", "").replace("_", "-")
                         for k in FILTERS.values() if sig.get(k))
        t.add_row(
            rec["name"], rec.get("ft_symbol", "—"),
            rec.get("bucket", "—").replace("_", " "),
            _num(cap / 1e6, "${:,.1f}M") if cap else "—",
            _num(sig.get("price_to_book")),
            _num(sig.get("debt_to_equity")),
            _num(sig.get("current_ratio")),
            _num(sig.get("loss_years"), "{:.0f}"),
            flags or "—",
        )
    console.print(t)


# ── ticker ─────────────────────────────────────────────────────────────────
def cmd_ticker(args):
    recs = _load_tickrs()
    q = args.symbol.upper()
    match = next(((r, s) for r, s in recs
                  if q in (r.get("ft_symbol", "").upper(), r.get("ly_ticker", "").upper())), None)
    if not match:
        console.print(f"[red]No ticker '{args.symbol}'.[/red] Try `uv run cli.py screener`.")
        sys.exit(1)
    rec, sig = match

    cap = rec.get("ly_market_cap_usd")
    header = Table(title=f"{rec['name']} ({rec.get('ft_symbol', '—')})", show_header=False)
    header.add_column("k", style="dim")
    header.add_column("v")
    header.add_row("Lightyear", rec.get("ly_ticker", "—"))
    header.add_row("Country / sector", f"{rec.get('country', '—')} · {rec.get('sector', '—')}")
    header.add_row("Price", f"{rec.get('currency', '')} {_num(rec.get('price'))}")
    header.add_row("Market cap", _num(cap / 1e6, "${:,.1f}M") if cap else "—")
    console.print(header)

    metrics = Table(title="Signals")
    metrics.add_column("Metric")
    metrics.add_column("Value", justify="right")
    for key, lbl, fmt in [
        ("price_to_book", "Price / book", "{:.2f}"),
        ("book_value_per_share", "Book value / share", "{:.2f}"),
        ("ncav_per_share", "NCAV / share", "{:.2f}"),
        ("debt_to_equity", "Debt / equity", "{:.2f}"),
        ("current_ratio", "Current ratio", "{:.2f}"),
        ("revenue_change_pct", "Revenue Δ (window)", "{:+.0f}%"),
        ("loss_years", "Loss years (of 5)", "{:.0f}"),
        ("distress_score", "Distress score (0-4)", "{:.0f}"),
    ]:
        metrics.add_row(lbl, _num(sig.get(key), fmt))
    flags = [k.replace("flag_", "").replace("_", "-") for k in FILTERS.values() if sig.get(k)]
    metrics.add_row("Flags", ", ".join(flags) or "—")
    console.print(metrics)


# ── plots (ASCII charts) ────────────────────────────────────────────────────
def _series_years(*series):
    common = set.intersection(*(set(s) for s in series if s)) if series else set()
    return sorted((int(y) for y in common))


def _indexed(series, years):
    base = series[str(years[0])]
    return [series[str(y)] / base * 100 for y in years]


def cmd_plot(args):
    import plotext as plt

    if args.kind == "country":
        d = _load(COUNTRY_JSON)
        code = args.code.upper()
        c = next((x for x in d["countries"] if x["code"] == code), None)
        if not c:
            codes = ", ".join(x["code"] for x in d["countries"])
            console.print(f"[red]No country '{code}'.[/red] Available: {codes}")
            sys.exit(1)
        cap, money = c.get("market_cap_usd"), c.get("money")
        years = _series_years(cap, money)
        if len(years) < 2:
            console.print("[red]Not enough overlapping data to plot.[/red]")
            sys.exit(1)
        plt.clear_figure()
        plt.plot(years, _indexed(cap, years), label="Market cap", marker="braille")
        plt.plot(years, _indexed(money, years), label="Money supply", marker="braille")
        plt.title(f"{c['name']} — market cap vs money supply (indexed to 100 at {years[0]})")
        plt.xlabel("year")
        plt.theme("dark")
        plt.show()
        return

    if args.kind == "indices":
        d = _load(INDEX_JSON)
        rows = [r for r in d["rows"] if (r.get(args.metric) or {}).get("multiple") is not None]
        rows.sort(key=lambda r: r[args.metric]["multiple"])
        labels = [r["name"] for r in rows]
        vals = [r[args.metric]["multiple"] for r in rows]
        metric_lbl = {"m2": "real (after money growth)",
                      "cpi": "real (CPI)", "nominal": "nominal"}[args.metric]
        plt.clear_figure()
        plt.bar(labels, vals, orientation="horizontal", width=0.4)
        plt.title(f"Index return multiple — {metric_lbl}  (since {d['start_year']})")
        plt.xlabel("× multiple")
        plt.theme("dark")
        plt.show()
        return


def main():
    p = argparse.ArgumentParser(description="Terminal views over the stock-list data.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("indices", help="Index real returns table")

    pc = sub.add_parser("countries", help="Country macro (optionally one CODE for year-by-year)")
    pc.add_argument("code", nargs="?", help="Country code, e.g. US, UK, JP")

    ps = sub.add_parser("screener", help="Micro-cap screener table")
    ps.add_argument("--filter", choices=FILTERS, help="Preset fundamentals filter")
    ps.add_argument("--sort", choices=SORTS, help="Sort column")
    ps.add_argument("--limit", type=int, help="Max rows")

    pt = sub.add_parser("ticker", help="One ticker's signals")
    pt.add_argument("symbol", help="FT or Lightyear symbol")

    pp = sub.add_parser("plot", help="ASCII charts")
    pp_sub = pp.add_subparsers(dest="kind", required=True)
    ppc = pp_sub.add_parser("country", help="Market cap vs money supply over time")
    ppc.add_argument("code", help="Country code, e.g. US, JP")
    ppi = pp_sub.add_parser("indices", help="Index return multiples (bar chart)")
    ppi.add_argument("--metric", choices=("m2", "cpi", "nominal"), default="m2",
                     help="Which multiple to chart (default: m2 = real after money growth)")

    args = p.parse_args()
    {"indices": cmd_indices, "countries": cmd_countries,
     "screener": cmd_screener, "ticker": cmd_ticker, "plot": cmd_plot}[args.cmd](args)


if __name__ == "__main__":
    main()
