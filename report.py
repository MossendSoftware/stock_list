"""Render ft_financials.json into a browsable, searchable HTML page.

Run: uv run report.py  ->  financials.html
"""

import json
from html import escape

data = json.load(open("ft_financials.json"))
results = data["results"]

CARD = """<article class="card" data-bucket="{bucket}" data-search="{search}">
  <header>
    <div class="title"><h2>{name}</h2><span class="tags">{tags}</span></div>
    <div class="price">{price}</div>
  </header>
  <div class="grid">
    <div class="block"><h3>Balance sheet</h3><table>{bs}</table></div>
    <div class="block"><h3>Metrics</h3><table>{metrics}</table></div>
  </div>
  <footer><a href="{ft_url}" target="_blank" rel="noopener">View on FT &rarr;</a></footer>
</article>"""

BS_LABELS = {
    "total_assets": "Total assets",
    "total_current_assets": "Current assets",
    "total_liabilities": "Total liabilities",
    "total_current_liabilities": "Current liabilities",
    "shares_outstanding": "Shares outstanding",
}
METRIC_LABELS = {
    "net_assets": "Net assets",
    "book_value_per_share": "Book value / share",
    "price_to_book": "Price / book (P/B)",
    "current_ratio": "Current ratio",
    "debt_to_equity": "Debt / equity",
    "ncav_per_share": "NCAV / share",
}


def num(v):
    if v is None:
        return "&mdash;"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def rows(d, labels):
    out = []
    for k, lbl in labels.items():
        if k in d and d[k] is not None:
            out.append(f"<tr><td>{lbl}</td><td class='n'>{num(d[k])}</td></tr>")
    return "".join(out) or "<tr><td colspan=2 class='muted'>no data</td></tr>"


def main():
    cards = []
    for r in sorted(results, key=lambda x: x.get("metrics", {}).get("price_to_book")
                    if x.get("metrics", {}).get("price_to_book") is not None else 1e9):
        tags = " ".join(
            f"<i>{escape(str(t))}</i>" for t in
            [r["bucket"].replace("_", " "), r["country"], r["sector"], r["ft_symbol"]] if t)
        search = escape(f"{r['name']} {r['ly_ticker']} {r['ft_symbol']} "
                        f"{r['country']} {r['sector']}".lower())
        cards.append(CARD.format(
            bucket=escape(r["bucket"]),
            search=search,
            name=escape(r["name"]),
            tags=tags,
            price=f"{escape(r['currency'])} {num(r['price'])}",
            bs=rows(r["balance_sheet"], BS_LABELS),
            metrics=rows(r["metrics"], METRIC_LABELS),
            ft_url=escape(r["ft_url"]),
        ))

    html = TEMPLATE.replace("{{COUNT}}", str(len(results))).replace(
        "{{CARDS}}", "\n".join(cards))
    open("financials.html", "w").write(html)
    print(f"Wrote financials.html ({len(results)} companies)")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Micro-cap financials &mdash; FT</title>
<style>
  :root { --bg:#0d1117; --card:#161b22; --line:#30363d; --txt:#e6edf3;
          --muted:#8b949e; --accent:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--txt); }
  header.top { position:sticky; top:0; background:var(--bg); padding:18px 24px;
               border-bottom:1px solid var(--line); z-index:10; }
  h1 { margin:0 0 10px; font-size:20px; }
  .controls { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  input, select { background:var(--card); color:var(--txt); border:1px solid var(--line);
                  border-radius:8px; padding:8px 12px; font-size:14px; }
  input { flex:1; min-width:200px; }
  .count { color:var(--muted); font-size:13px; }
  main { display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr));
         gap:14px; padding:18px 24px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:16px; }
  .card header { display:flex; justify-content:space-between; gap:8px; align-items:flex-start; }
  .card h2 { margin:0; font-size:16px; }
  .tags { display:flex; flex-wrap:wrap; gap:5px; margin-top:6px; }
  .tags i { font-style:normal; font-size:11px; background:#21262d; color:var(--muted);
            padding:2px 7px; border-radius:20px; }
  .price { font-weight:600; white-space:nowrap; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px; }
  .block h3 { margin:0 0 6px; font-size:12px; text-transform:uppercase;
              letter-spacing:.04em; color:var(--muted); }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  td { padding:3px 0; border-bottom:1px solid #21262d; }
  td.n { text-align:right; font-variant-numeric:tabular-nums; }
  .muted { color:var(--muted); }
  footer { margin-top:12px; }
  footer a { color:var(--accent); text-decoration:none; font-size:13px; }
  .hidden { display:none; }
</style></head>
<body>
<header class="top">
  <h1>Micro-cap financials <span class="count">({{COUNT}} companies, via FT)</span></h1>
  <div class="controls">
    <input id="q" placeholder="Search name, ticker, country, sector&hellip;">
    <select id="bucket">
      <option value="">All buckets</option>
      <option value="under_10M">Under $10M</option>
      <option value="10M_to_25M">$10M&ndash;$25M</option>
    </select>
    <span class="count" id="shown"></span>
  </div>
</header>
<main id="list">
{{CARDS}}
</main>
<script>
  const q=document.getElementById('q'), bucket=document.getElementById('bucket'),
        cards=[...document.querySelectorAll('.card')], shown=document.getElementById('shown');
  function apply(){
    const term=q.value.trim().toLowerCase(), b=bucket.value; let n=0;
    for(const c of cards){
      const ok=(!term||c.dataset.search.includes(term))&&(!b||c.dataset.bucket===b);
      c.classList.toggle('hidden',!ok); if(ok)n++;
    }
    shown.textContent=n+' shown';
  }
  q.addEventListener('input',apply); bucket.addEventListener('change',apply); apply();
</script>
</body></html>"""


if __name__ == "__main__":
    main()
