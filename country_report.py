"""Render country_report.json into dark dual-axis charts, an overview page
(/country/report) and one page per country (/country/report/<slug>).

Per country: market cap and money supply indexed to 100 (left axis), risk-free
rate % (right axis), plus a year-by-year data table. Run: uv run country_report.py
"""

import json
from html import escape
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path("country")
IMG = OUT / "img"
PAGES = OUT / "report"  # per-country pages live here

BG = "#0d1117"
PANEL = "#161b22"
TXT = "#e6edf3"
MUTED = "#8b949e"
CAP = "#f0883e"
MONEY = "#56d364"
GDP = "#bc8cff"
RFR = "#79c0ff"
GRID = "#262d36"


def slugify(name):
    return name.lower().replace(" ", "-")


def to_series(d):
    return [(int(y), float(v)) for y, v in sorted(d.items(), key=lambda kv: int(kv[0]))]


def index_to_100(series, base_year):
    base = dict(series).get(base_year)
    if base is None or base == 0:
        return series
    return [(y, v / base * 100) for y, v in series]


def fmt_usd(v):
    if v is None:
        return "&mdash;"
    if v >= 1e12:
        return f"${v/1e12:.2f}tn"
    if v >= 1e9:
        return f"${v/1e9:,.0f}bn"
    return f"${v/1e6:,.0f}m"


def chart(country, big=False):
    cap = to_series(country["market_cap_usd"])
    money = to_series(country["money"])
    gdp = to_series(country.get("gdp_usd", {}))
    rfr = to_series(country["rfr_pct"])
    if not cap or not money:
        return None
    base = max(cap[0][0], money[0][0])
    cap_i = index_to_100(cap, base)
    money_i = index_to_100(money, base)
    gdp_i = index_to_100(gdp, base) if gdp else []

    fig, ax = plt.subplots(figsize=(10.5, 5.4) if big else (7.4, 4.0), dpi=120)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.plot([y for y, _ in cap_i], [v for _, v in cap_i], color=CAP, lw=2.2,
            marker="o", ms=3, label="Total market cap")
    ax.plot([y for y, _ in money_i], [v for _, v in money_i], color=MONEY, lw=2.2,
            marker="o", ms=3, label="Money supply")
    if gdp_i:
        ax.plot([y for y, _ in gdp_i], [v for _, v in gdp_i], color=GDP, lw=1.8,
                marker="o", ms=3, label="GDP")
    ax.set_ylabel(f"Indexed to 100 ({base})", color=MUTED, fontsize=9)
    ax.tick_params(colors=MUTED, labelsize=8)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.grid(True, color=GRID, lw=0.6, alpha=0.6)

    handles, labels = ax.get_legend_handles_labels()
    if rfr:
        ax2 = ax.twinx()
        ax2.plot([y for y, _ in rfr], [v for _, v in rfr], color=RFR, lw=1.8,
                 ls="--", label="Risk-free rate (10y govt, %)")
        ax2.set_ylabel("Risk-free rate (10y govt, %)", color=RFR, fontsize=9)
        ax2.tick_params(colors=RFR, labelsize=8)
        for s in ax2.spines.values():
            s.set_color(GRID)
        h2, l2 = ax2.get_legend_handles_labels()
        handles += h2
        labels += l2

    ax.legend(handles, labels, loc="upper left", fontsize=8,
              facecolor=PANEL, edgecolor=GRID, labelcolor=TXT)
    ax.set_title(country["name"], color=TXT, fontsize=13, loc="left", pad=8)
    fig.tight_layout()
    IMG.mkdir(parents=True, exist_ok=True)
    name = f"{country['code']}{'_lg' if big else ''}.png"
    fig.savefig(IMG / name, facecolor=BG)
    plt.close(fig)

    return {"img": name, "base": base,
            "cap_mult": cap[-1][1] / dict(cap).get(base, cap[0][1]),
            "money_mult": money[-1][1] / dict(money).get(base, money[0][1]),
            "rfr_now": rfr[-1][1] if rfr else None}


PALETTE = ["#f0883e", "#56d364", "#79c0ff", "#bc8cff", "#f87171",
           "#e3b341", "#56d4dd", "#db61a2"]


def multi_chart(series_list, fname, title, ylabel, log=False):
    """series_list: [(name, [(year,val),...]), ...] -> dark multi-line PNG."""
    fig, ax = plt.subplots(figsize=(10.5, 5.6), dpi=120)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for i, (name, pts) in enumerate(series_list):
        if not pts:
            continue
        ax.plot([y for y, _ in pts], [v for _, v in pts],
                color=PALETTE[i % len(PALETTE)], lw=2.0, marker="o", ms=2.5,
                label=name)
    if log:
        ax.set_yscale("log")
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    ax.tick_params(colors=MUTED, labelsize=8)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.grid(True, color=GRID, lw=0.6, alpha=0.6, which="both")
    ax.legend(loc="upper left", fontsize=8, facecolor=PANEL, edgecolor=GRID,
              labelcolor=TXT, ncol=2)
    ax.set_title(title, color=TXT, fontsize=13, loc="left", pad=8)
    fig.tight_layout()
    IMG.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG / fname, facecolor=BG)
    plt.close(fig)


def build_compare(data):
    countries = data["countries"]
    money, cap, capgdp = [], [], []
    for c in countries:
        m = to_series(c["money"])
        k = to_series(c["market_cap_usd"])
        g = dict(to_series(c.get("gdp_usd", {})))
        if m:
            money.append((c["name"], index_to_100(m, m[0][0])))
        if k:
            cap.append((c["name"], index_to_100(k, k[0][0])))
        # Cap/GDP %, excluding Hong Kong (hub distortion)
        if g and c["code"] != "HK":
            ratio = [(y, v / g[y] * 100) for y, v in k if y in g]
            if ratio:
                capgdp.append((c["name"], ratio))

    multi_chart(money, "compare_money.png", "Money supply by country",
                "Indexed to 100 (log)", log=True)
    multi_chart(cap, "compare_marketcap.png", "Total market cap by country",
                "Indexed to 100 (log)", log=True)
    multi_chart(capgdp, "compare_capgdp.png",
                "Market cap / GDP (Buffett indicator) — HK excluded",
                "Market cap as % of GDP")


DEBT = "#f87171"


def debt_chart(country):
    """Money supply vs government debt, both indexed to 100; debt/GDP on right."""
    money = to_series(country["money"])
    debt = to_series(country.get("govt_debt_lcu", {}))
    dgdp = to_series(country.get("debt_pct_gdp", {}))
    if not money or not debt:
        return None
    base = max(money[0][0], debt[0][0])
    money_i = index_to_100(money, base)
    debt_i = index_to_100(debt, base)

    fig, ax = plt.subplots(figsize=(7.4, 4.0), dpi=120)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.plot([y for y, _ in money_i], [v for _, v in money_i], color=MONEY, lw=2.2,
            marker="o", ms=3, label="Money supply")
    ax.plot([y for y, _ in debt_i], [v for _, v in debt_i], color=DEBT, lw=2.2,
            marker="o", ms=3, label="Govt debt")
    ax.set_ylabel(f"Indexed to 100 ({base})", color=MUTED, fontsize=9)
    ax.tick_params(colors=MUTED, labelsize=8)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.grid(True, color=GRID, lw=0.6, alpha=0.6)
    handles, labels = ax.get_legend_handles_labels()
    if dgdp:
        ax2 = ax.twinx()
        ax2.plot([y for y, _ in dgdp], [v for _, v in dgdp], color=CAP, lw=1.6,
                 ls="--", label="Debt / GDP (%)")
        ax2.set_ylabel("Debt / GDP (%)", color=CAP, fontsize=9)
        ax2.tick_params(colors=CAP, labelsize=8)
        for s in ax2.spines.values():
            s.set_color(GRID)
        h2, l2 = ax2.get_legend_handles_labels()
        handles += h2
        labels += l2
    ax.legend(handles, labels, loc="upper left", fontsize=8, facecolor=PANEL,
              edgecolor=GRID, labelcolor=TXT)
    ax.set_title(country["name"], color=TXT, fontsize=12, loc="left", pad=8)
    fig.tight_layout()
    IMG.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG / f"debt_{country['code']}.png", facecolor=BG)
    plt.close(fig)
    return {"money_mult": money[-1][1] / dict(money).get(base, money[0][1]),
            "debt_mult": debt[-1][1] / dict(debt).get(base, debt[0][1]),
            "dgdp_now": dgdp[-1][1] if dgdp else None, "base": base}


def build_debt_screen(data):
    cards = []
    for c in data["countries"]:
        m = debt_chart(c)
        if not m:
            continue
        cap = (f'Since {m["base"]}: money {m["money_mult"]:.1f}x, '
               f'debt {m["debt_mult"]:.1f}x &middot; debt/GDP '
               f'{m["dgdp_now"]:.0f}%' if m["dgdp_now"] else '')
        cards.append(f'<figure><img src="/country/img/debt_{c["code"]}.png" '
                     f'alt="{escape(c["name"])}"><figcaption>{cap}</figcaption></figure>')
    (OUT / "debt.html").write_text(DEBTPAGE.replace("{{CARDS}}", "\n".join(cards)))


def data_table(country):
    cap = country["market_cap_usd"]
    est_from = country.get("market_cap_est_from")
    gdp = country.get("gdp_usd", {})
    money = {int(y): v for y, v in country["money"].items()}
    rfr = country["rfr_pct"]
    years = sorted({int(y) for y in cap} | set(money) | {int(y) for y in rfr})
    base = max(min((int(y) for y in cap), default=0),
               min(money, default=0))
    cap_base = cap.get(str(base))
    money_base = money.get(base)
    rows = []
    for y in years:
        c = cap.get(str(y))
        m = money.get(y)
        cap_txt = fmt_usd(c)
        if est_from and c is not None and y >= est_from:
            cap_txt += " <span class='est'>est</span>"
        capi = f"{c/cap_base*100:.0f}" if c and cap_base else "&mdash;"
        moni = f"{m/money_base*100:.0f}" if m and money_base else "&mdash;"
        g = gdp.get(str(y))
        capgdp = f"{c/g*100:.0f}%" if c and g else "&mdash;"
        r = rfr.get(str(y))
        rows.append(f"<tr><td>{y}</td><td class='m'>{cap_txt}</td>"
                    f"<td class='m'>{capi}</td><td class='m'>{moni}</td>"
                    f"<td class='m'>{capgdp}</td>"
                    f"<td class='m'>{f'{r:.2f}%' if r is not None else '&mdash;'}</td></tr>")
    return "".join(rows)


def main():
    data = json.load(open("country_report.json"))
    PAGES.mkdir(parents=True, exist_ok=True)
    cards = []
    for c in data["countries"]:
        meta = chart(c)
        if not meta:
            continue
        big = chart(c, big=True)
        slug = slugify(c["name"])
        rfr = (f'RFR {meta["rfr_now"]:.1f}%' if meta["rfr_now"] is not None else 'RFR n/a')
        caption = (f'Since {meta["base"]}: market cap {meta["cap_mult"]:.1f}x, '
                   f'money {meta["money_mult"]:.1f}x &middot; {rfr}')
        cards.append(f'<a class="card" href="/countries/{slug}">'
                     f'<img src="/country/img/{meta["img"]}" alt="{escape(c["name"])}">'
                     f'<div class="cap">{caption}</div></a>')
        # per-country page
        page = (COUNTRY.replace("{{NAME}}", escape(c["name"]))
                .replace("{{CAPTION}}", caption)
                .replace("{{IMG}}", f"/country/img/{big['img']}")
                .replace("{{ROWS}}", data_table(c)))
        (PAGES / f"{slug}.html").write_text(page)
        print(f"  {c['name']:16} cap {meta['cap_mult']:.1f}x  money {meta['money_mult']:.1f}x")

    (OUT / "report.html").write_text(OVERVIEW.replace("{{CARDS}}", "\n".join(cards)))

    build_compare(data)
    (OUT / "compare.html").write_text(COMPARE)
    build_debt_screen(data)
    print(f"\nWrote overview + compare + debt + {len(cards)} country pages to {OUT}/")


_STYLE = """
 :root{--bg:#0d1117;--panel:#161b22;--line:#262d36;--txt:#e6edf3;--muted:#8b949e;--accent:#f0883e;}
 *{box-sizing:border-box;}
 body{margin:0;background:var(--bg);color:var(--txt);
   font:15px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
 .wrap{max-width:1180px;margin:0 auto;padding:40px 28px 60px;}
 a{color:var(--accent);text-decoration:none;}
 h1{font-size:25px;margin:0 0 6px;}
 .sub{color:var(--muted);font-size:14px;margin-bottom:26px;max-width:840px;}
 .back{color:var(--muted);font-size:13px;}
"""

OVERVIEW = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Country macro — market cap vs money vs rates</title><style>""" + _STYLE + """
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:18px;}
 .card{display:block;background:var(--panel);border:1px solid var(--line);
   border-radius:12px;padding:10px;color:var(--txt);}
 .card:hover{border-color:var(--accent);}
 .card img{width:100%;display:block;border-radius:6px;}
 .cap{color:var(--muted);font-size:12px;padding:8px 4px 2px;}
 .note{color:var(--muted);font-size:12px;margin-top:26px;max-width:900px;line-height:1.7;}
 .explain{margin-top:34px;background:var(--panel);border:1px solid var(--line);
   border-radius:12px;padding:20px 24px;max-width:900px;}
 .explain h2{color:var(--accent);font-size:17px;margin:0 0 10px;}
 .explain p{font-size:14px;line-height:1.7;margin:0 0 12px;}
 .explain ul{font-size:14px;line-height:1.7;margin:0 0 12px;padding-left:20px;}
 .explain .warn{color:var(--accent);}
 .explain table{border-collapse:collapse;font-size:13px;margin:6px 0 14px;}
 .explain td,.explain th{border:1px solid var(--line);padding:5px 12px;text-align:left;}
 .explain th{color:var(--muted);font-weight:400;}
 .explain td.m{text-align:right;font-variant-numeric:tabular-nums;}
</style></head><body><div class="wrap">
 <h1>Market cap vs. money supply vs. rates</h1>
 <p style="margin:0 0 14px"><a href="/countries/compare">Compare all countries &rarr;</a>
   &nbsp;&middot;&nbsp; <a href="/countries/debt">Money supply vs. government debt &rarr;</a></p>
 <div class="sub">Total stock-market capitalisation, broad money and GDP, indexed to
   100 (left axis), vs the risk-free rate (10-year govt bond yield, right axis). Click
   a country for detail. Is the market growing in real terms, or tracking the money
   supply &mdash; and how does it compare to the real economy (GDP)?</div>
 <div class="grid">{{CARDS}}</div>

 <section class="explain">
  <h2>What is Cap/GDP? (the Buffett indicator)</h2>
  <p>A country's <b>total stock-market capitalisation &divide; that same country's
   GDP</b> &mdash; not global GDP. GDP is roughly one year of the economy's output;
   market cap is what investors collectively pay for its listed slice. So Cap/GDP is
   essentially a <b>price-to-sales ratio for the whole country</b>: how big the
   market is relative to the real economy underneath it.</p>
  <p>Rough reading:</p>
  <ul>
   <li><b>~50&ndash;75%</b> &mdash; market modest/cheap vs. the economy</li>
   <li><b>~100%</b> &mdash; market cap equals one year of GDP; historically "fair"</li>
   <li><b>150%+</b> &mdash; market large/expensive vs. the economy</li>
  </ul>
  <p>Rising over time means the market is inflating faster than the economy beneath
   it &mdash; genuine growth in the listed share of GDP, or just liquidity and
   exuberance. Where it sits now (latest, vs. 2004):</p>
  <table><thead><tr><th>Country</th><th>Latest</th><th>2004</th><th>Read</th></tr></thead>
   <tbody>
    <tr><td>United States</td><td class="m">216%</td><td class="m">134%</td><td>extreme &mdash; above the dot-com peak</td></tr>
    <tr><td>Japan</td><td class="m">157%</td><td class="m">73%</td><td>big re-rating, cheap &rarr; rich</td></tr>
    <tr><td>India</td><td class="m">131%</td><td class="m">59%</td><td>listed market more than doubled vs. economy</td></tr>
    <tr><td>United Kingdom</td><td class="m">91%</td><td class="m">116%</td><td>de-rated &mdash; market shrank vs. economy</td></tr>
    <tr><td>South Korea</td><td class="m">83%</td><td class="m">52%</td><td>still moderate</td></tr>
    <tr><td>China</td><td class="m">63%</td><td class="m">23%</td><td>moderate despite huge nominal growth</td></tr>
    <tr><td>Hong Kong</td><td class="m">1,118%</td><td class="m">509%</td><td>distortion &mdash; see below</td></tr>
   </tbody></table>
  <p class="warn">Caveat: Cap/GDP only works when the listed companies belong to the
   local economy. Hong Kong's 1,118% is meaningless &mdash; its exchange lists giant
   <i>mainland Chinese</i> firms against tiny HK GDP. The same distortion hits
   financial hubs (Switzerland, Netherlands, Luxembourg). Use it for large,
   self-contained domestic markets; ignore it for hubs. Euro-area data is also stale
   (ends 2018).</p>
 </section>

 <p class="note">Market cap &amp; GDP: World Bank (US$); Cap/GDP is the "Buffett
   indicator". Money:
   US M2 + FRED OECD broad money (UK/EZ/JP/KR); China/India/Hong Kong curated.
   Risk-free rate: FRED 10-year government bond yield (US/UK/EZ/JP/KR; no clean
   sovereign yield for China/India/HK). World Bank UK market cap ends 2022; 2023+
   estimated from the FTSE All-Share index (marked &ldquo;est&rdquo;).</p>
</div></body></html>"""

COUNTRY = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{NAME}} — market cap vs money vs rate</title><style>""" + _STYLE + """
 img.chart{width:100%;max-width:1000px;border:1px solid var(--line);border-radius:10px;}
 .headline{color:var(--muted);font-size:14px;margin:6px 0 18px;}
 table{border-collapse:collapse;margin-top:8px;font-size:13px;}
 th,td{border:1px solid var(--line);padding:6px 14px;text-align:left;}
 thead th{color:var(--muted);font-weight:400;background:var(--panel);}
 td.m{text-align:right;font-variant-numeric:tabular-nums;}
 .est{color:var(--accent);font-size:10px;}
</style></head><body><div class="wrap">
 <a class="back" href="/countries">&larr; All countries</a>
 <h1>{{NAME}}</h1>
 <div class="headline">{{CAPTION}}</div>
 <img class="chart" src="{{IMG}}" alt="{{NAME}}">
 <table><thead><tr><th>Year</th><th>Market cap</th><th>Cap idx</th>
   <th>Money idx</th><th>Cap/GDP</th><th>Risk-free %</th></tr></thead>
   <tbody>{{ROWS}}</tbody></table>
</div></body></html>"""


DEBTPAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Money supply vs. government debt</title><style>""" + _STYLE + """
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:18px;}
 figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;}
 figure img{width:100%;display:block;border-radius:6px;}
 figcaption{color:var(--muted);font-size:12px;padding:8px 4px 2px;}
 .note{color:var(--muted);font-size:12px;margin-top:26px;max-width:900px;line-height:1.7;}
</style></head><body><div class="wrap">
 <a class="back" href="/countries">&larr; Per-country view</a>
 <h1>Money supply vs. government debt</h1>
 <div class="sub">Broad money and general-government gross debt, both indexed to 100
   (left axis), with debt-to-GDP on the right. When debt outruns money, the gap is
   funded by real lenders; when money keeps pace, the debt is being monetised.</div>
 <div class="grid">{{CARDS}}</div>
 <p class="note">Govt debt: IMF general government gross debt (% of GDP, FRED
   GGGDTA*) &times; local-currency GDP (World Bank). Available for US, UK, Japan,
   Korea, China, India; Euro-area and Hong Kong series unavailable/insufficient.</p>
</div></body></html>"""

COMPARE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Country comparison — money, market cap, Cap/GDP</title><style>""" + _STYLE + """
 figure{margin:0 0 24px;background:var(--panel);border:1px solid var(--line);
   border-radius:12px;padding:12px;}
 figure img{width:100%;display:block;border-radius:6px;}
 figcaption{color:var(--muted);font-size:13px;padding:10px 4px 2px;line-height:1.6;}
</style></head><body><div class="wrap">
 <a class="back" href="/countries">&larr; Per-country view</a>
 <h1>Comparing countries</h1>
 <div class="sub">The same three measures, each with every country on one chart.
   Money and market cap are indexed to 100 at each country's start year and drawn on
   a <b>log scale</b> &mdash; so equal slopes mean equal growth rates, and the huge
   emerging-market numbers don't crush the rest.</div>
 <figure><img src="/country/img/compare_money.png" alt="Money supply by country">
   <figcaption>Broad money, indexed (log). China and India tower over the developed
   world; Japan barely grew its money supply.</figcaption></figure>
 <figure><img src="/country/img/compare_marketcap.png" alt="Market cap by country">
   <figcaption>Total market cap, indexed (log). Steeper than money almost everywhere
   &mdash; markets outgrew the money that chased them, China/India most of all.</figcaption></figure>
 <figure><img src="/country/img/compare_capgdp.png" alt="Cap/GDP by country">
   <figcaption>Market cap as a % of GDP (the Buffett indicator). Hong Kong excluded
   (hub distortion). The US sits well above everyone; the UK has drifted down.</figcaption></figure>
 <p class="note">Sources as on the per-country pages. Cap/GDP excludes Hong Kong;
   Euro-area data ends 2018.</p>
</div></body></html>"""


if __name__ == "__main__":
    main()
