"""Render captured FT financials into one HTML page per ticker + a screener index.

Reads tickr/data/*.json -> tickr/<TICKER>.html and tickr/index.html.
Adds fundamentals-only screening signals (screen.py): flag badges on each page,
sortable columns + preset filters on the index. Run: uv run tickr_render.py
"""

import json
from html import escape
from pathlib import Path

from screen import compute_signals

DATA_DIR = Path("tickr/data")
OUT = Path("tickr")

STATEMENT_TITLES = {"income": "Income Statement",
                    "balance": "Balance Sheet",
                    "cashflow": "Cash Flow Statement"}

FLAG_LABELS = {
    "flag_below_book": ("Below book", "blue"),
    "flag_net_net": ("Net-net", "green"),
    "flag_low_debt": ("Low debt", "teal"),
    "flag_distressed": ("Distressed", "red"),
}


def fmt(raw, val):
    if raw in (None, "", "--"):
        return '<span class="muted">&mdash;</span>'
    neg = (isinstance(val, (int, float)) and val < 0) or raw.strip().startswith("(")
    return f'<span class="{"neg" if neg else ""}">{escape(raw)}</span>'


def statement_table(st):
    if not st or not st.get("rows"):
        return '<p class="muted">No data.</p>'
    heads = "".join(f"<th>{escape(p)}</th>" for p in st["periods"])
    body = []
    for r in st["rows"]:
        if r["section"]:
            body.append(f'<tr class="section"><td colspan="{len(st["periods"])+1}">'
                        f'{escape(r["label"])}</td></tr>')
            continue
        cells = "".join(f"<td>{fmt(rw, v)}</td>"
                        for rw, v in zip(r["raw"], r["values"]))
        body.append(f'<tr><th>{escape(r["label"])}</th>{cells}</tr>')
    return (f'<table class="fin"><thead><tr><th class="lbl"></th>{heads}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def badges(sig):
    out = []
    for k, (label, cls) in FLAG_LABELS.items():
        if sig.get(k):
            out.append(f'<span class="badge {cls}">{label}</span>')
    return "".join(out) or '<span class="muted">no flags</span>'


def metric_chips(sig):
    chips = []
    order = [("price_to_book", "P/B", "{:.2f}"),
             ("current_ratio", "Current ratio", "{:.2f}"),
             ("debt_to_equity", "Debt/equity", "{:.2f}"),
             ("ncav_per_share", "NCAV/share", "{:.2f}"),
             ("book_value_per_share", "Book/share", "{:.2f}"),
             ("revenue_change_pct", "Revenue Δ (window)", "{:+.0f}%"),
             ("loss_years", "Loss years (of 5)", "{:.0f}")]
    for k, lbl, f in order:
        if sig.get(k) is not None:
            chips.append(f'<div class="chip"><span>{lbl}</span><b>{f.format(sig[k])}</b></div>')
    return "".join(chips)


def ticker_page(rec, sig):
    cap = rec.get("ly_market_cap_usd")
    cap_s = f"${cap/1e6:,.1f}M" if cap else "&mdash;"
    tabs, panels = [], []
    for i, (key, title) in enumerate(STATEMENT_TITLES.items()):
        active = " active" if i == 0 else ""
        tabs.append(f'<button class="tab{active}" data-t="{key}">{title}</button>')
        panels.append(f'<div class="panel{active}" id="{key}">'
                      f'{statement_table(rec["statements"].get(key))}</div>')
    return PAGE.format(
        name=escape(rec["name"]),
        symbol=escape(rec["ft_symbol"]),
        ly=escape(rec["ly_ticker"]),
        price=f'{escape(rec["currency"])} {rec["price"]:,.2f}',
        meta=" &middot; ".join(escape(str(x)) for x in
                               [rec["country"], rec["sector"],
                                rec["bucket"].replace("_", " ")] if x),
        cap=cap_s,
        badges=badges(sig),
        chips=metric_chips(sig),
        tabs="".join(tabs),
        panels="".join(panels),
        ft_url=escape(rec["ft_url"]),
    )


def cell(v, f="{:.2f}"):
    return f.format(v) if isinstance(v, (int, float)) else "&mdash;"


def sort_val(v):
    return v if isinstance(v, (int, float)) else ""


def main():
    recs = []
    for f in sorted(DATA_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        if d.get("missed"):
            continue
        recs.append((d, compute_signals(d)))

    OUT.mkdir(exist_ok=True)
    for rec, sig in recs:
        slug = rec["ly_ticker"].replace("/", "_").replace(" ", "_")
        (OUT / f"{slug}.html").write_text(ticker_page(rec, sig))

    rows = []
    for rec, sig in sorted(recs, key=lambda x: x[0]["name"].lower()):
        slug = rec["ly_ticker"].replace("/", "_").replace(" ", "_")
        cap = rec.get("ly_market_cap_usd")
        search = escape(f'{rec["name"]} {rec["ly_ticker"]} {rec["ft_symbol"]} '
                        f'{rec["country"]} {rec["sector"]}'.lower())
        flags = " ".join(k for k in FLAG_LABELS if sig.get(k))
        chips = "".join(f'<span class="badge {FLAG_LABELS[k][1]} mini">'
                        f'{FLAG_LABELS[k][0]}</span>' for k in FLAG_LABELS if sig.get(k))
        rows.append(
            f'<a class="row" href="/screener/{slug}" data-search="{search}" '
            f'data-bucket="{escape(rec["bucket"])}" data-flags="{flags}" '
            f'data-cap="{sort_val(cap)}" data-pb="{sort_val(sig.get("price_to_book"))}" '
            f'data-de="{sort_val(sig.get("debt_to_equity"))}" '
            f'data-cr="{sort_val(sig.get("current_ratio"))}" '
            f'data-loss="{sort_val(sig.get("loss_years"))}" '
            f'data-distress="{sort_val(sig.get("distress_score"))}">'
            f'<span class="nm">{escape(rec["name"])}<br><small>{chips}</small></span>'
            f'<span class="sym">{escape(rec["ft_symbol"])}</span>'
            f'<span class="num">{cell(cap/1e6, "${:,.1f}M") if cap else "&mdash;"}</span>'
            f'<span class="num">{cell(sig.get("price_to_book"))}</span>'
            f'<span class="num">{cell(sig.get("debt_to_equity"))}</span>'
            f'<span class="num">{cell(sig.get("current_ratio"))}</span>'
            f'<span class="num">{cell(sig.get("loss_years"), "{:.0f}")}</span></a>')

    (OUT / "index.html").write_text(
        INDEX.replace("{{COUNT}}", str(len(recs))).replace("{{ROWS}}", "\n".join(rows)))
    print(f"Wrote {len(recs)} ticker pages + screener index.html to {OUT}/")


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} ({symbol}) — financials</title>
<style>
 :root{{--bg:#0d1117;--card:#161b22;--line:#262d36;--txt:#e6edf3;--muted:#8b949e;
        --accent:#f0883e;--neg:#f85149;}}
 *{{box-sizing:border-box;}}
 body{{margin:0;background:var(--bg);color:var(--txt);
   font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;}}
 a{{color:var(--accent);text-decoration:none;}}
 .wrap{{max-width:1100px;margin:0 auto;padding:24px;}}
 .back{{font-size:13px;color:var(--muted);}}
 header{{margin:8px 0 14px;}}
 h1{{margin:0;font-size:22px;}}
 .sub{{color:var(--muted);font-size:13px;margin-top:4px;}}
 .price{{font-size:20px;font-weight:600;margin-top:8px;}}
 .badges{{margin:12px 0;display:flex;gap:6px;flex-wrap:wrap;align-items:center;}}
 .badge{{font-size:12px;padding:3px 10px;border-radius:20px;font-weight:600;}}
 .badge.mini{{font-size:10px;padding:1px 7px;font-weight:500;}}
 .badge.blue{{background:#1f3a5f;color:#79c0ff;}}
 .badge.green{{background:#1b3a2b;color:#56d364;}}
 .badge.teal{{background:#10363a;color:#56d4dd;}}
 .badge.red{{background:#3d1d1d;color:#ff7b72;}}
 .chips{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0;}}
 .chip{{background:var(--card);border:1px solid var(--line);border-radius:8px;
   padding:6px 12px;font-size:12px;}}
 .chip span{{color:var(--muted);margin-right:6px;}}
 .tabs{{display:flex;gap:4px;border-bottom:1px solid var(--line);}}
 .tab{{background:none;border:none;color:var(--muted);padding:10px 14px;
   font-size:14px;cursor:pointer;border-bottom:2px solid transparent;}}
 .tab.active{{color:var(--accent);border-bottom-color:var(--accent);}}
 .panel{{display:none;overflow-x:auto;}}
 .panel.active{{display:block;}}
 table.fin{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;}}
 table.fin th.lbl{{width:42%;}}
 table.fin thead th{{text-align:right;padding:10px 8px;font-size:12px;color:var(--muted);
   border-bottom:1px solid var(--line);}}
 table.fin tbody th{{text-align:left;font-weight:400;padding:5px 8px;}}
 table.fin td{{text-align:right;padding:5px 8px;border-bottom:1px solid #1c2129;}}
 table.fin tr.section td{{text-align:left;font-weight:700;font-size:11px;
   letter-spacing:.05em;color:var(--muted);padding-top:16px;border:none;}}
 .neg{{color:var(--neg);}} .muted{{color:var(--muted);}}
 footer{{margin-top:24px;font-size:13px;}}
</style></head><body><div class="wrap">
 <a class="back" href="/screener">&larr; All tickers</a>
 <header><h1>{name} <span class="muted">{symbol}</span></h1>
   <div class="sub">{meta} &middot; Lightyear: {ly} &middot; Mkt cap {cap}</div>
   <div class="price">{price}</div></header>
 <div class="badges">{badges}</div>
 <div class="chips">{chips}</div>
 <div class="tabs">{tabs}</div>
 {panels}
 <footer><a href="{ft_url}" target="_blank" rel="noopener">Source: FT tearsheet &rarr;</a></footer>
</div>
<script>
 document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{
   const t=b.dataset.t;
   document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===b));
   document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.id===t));
 }});
</script></body></html>"""

INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Micro-cap screener — {{COUNT}} tickers</title>
<style>
 :root{--bg:#0d1117;--card:#161b22;--line:#262d36;--txt:#e6edf3;--muted:#8b949e;--accent:#f0883e;}
 *{box-sizing:border-box;}
 body{margin:0;background:var(--bg);color:var(--txt);
   font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;}
 .top{position:sticky;top:0;background:var(--bg);padding:16px 24px;
   border-bottom:1px solid var(--line);z-index:5;}
 h1{margin:0 0 10px;font-size:19px;}
 .controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;}
 input,select{background:var(--card);color:var(--txt);border:1px solid var(--line);
   border-radius:8px;padding:8px 12px;font-size:14px;}
 input{flex:1;min-width:200px;}
 .presets{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;}
 .preset{background:var(--card);border:1px solid var(--line);color:var(--txt);
   border-radius:20px;padding:6px 14px;font-size:13px;cursor:pointer;}
 .preset.on{background:var(--accent);color:#161b22;border-color:var(--accent);font-weight:600;}
 .count{color:var(--muted);font-size:13px;}
 main{max-width:1080px;margin:0 auto;padding:8px 24px 40px;}
 .head,.row{display:grid;grid-template-columns:1fr 100px 110px 70px 70px 80px 70px;
   gap:10px;padding:10px 12px;align-items:center;}
 .head{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em;
   border-bottom:1px solid var(--line);position:sticky;top:118px;background:var(--bg);}
 .head span{cursor:pointer;user-select:none;}
 .head .num,.row .num{text-align:right;font-variant-numeric:tabular-nums;}
 .row{border-bottom:1px solid #1c2129;text-decoration:none;color:var(--txt);}
 .row:hover{background:var(--card);}
 .row .sym{color:var(--muted);}
 .row small{display:inline-flex;gap:4px;margin-top:3px;}
 .badge{font-size:10px;padding:1px 7px;border-radius:20px;}
 .badge.blue{background:#1f3a5f;color:#79c0ff;} .badge.green{background:#1b3a2b;color:#56d364;}
 .badge.teal{background:#10363a;color:#56d4dd;} .badge.red{background:#3d1d1d;color:#ff7b72;}
 .hidden{display:none;}
</style></head><body>
<div class="top"><h1>Micro-cap screener <span class="count">({{COUNT}} tickers · FT fundamentals)</span></h1>
 <div class="controls">
   <input id="q" placeholder="Search name, ticker, country, sector…">
   <select id="bucket"><option value="">All buckets</option>
     <option value="under_10M">Under $10M</option>
     <option value="10M_to_25M">$10M–$25M</option></select>
   <span class="count" id="shown"></span></div>
 <div class="presets">
   <button class="preset on" data-f="">All</button>
   <button class="preset" data-f="flag_below_book">Below book (P/B&lt;1)</button>
   <button class="preset" data-f="flag_net_net">Net-net</button>
   <button class="preset" data-f="flag_low_debt">Low debt</button>
   <button class="preset" data-f="flag_distressed">Distressed</button>
 </div></div>
<main>
 <div class="head"><span data-s="search" data-t="t">Company</span>
   <span class="sym" data-s="sym" data-t="t">FT symbol</span>
   <span class="num" data-s="cap" data-t="n">Mkt cap</span>
   <span class="num" data-s="pb" data-t="n">P/B</span>
   <span class="num" data-s="de" data-t="n">D/E</span>
   <span class="num" data-s="cr" data-t="n">Curr.</span>
   <span class="num" data-s="loss" data-t="n">Loss yr</span></div>
 <div id="list">{{ROWS}}</div>
</main>
<script>
 const q=document.getElementById('q'),bk=document.getElementById('bucket'),
   list=document.getElementById('list'),sh=document.getElementById('shown'),
   rows=[...document.querySelectorAll('.row')];
 let flag='';
 function ap(){const t=q.value.trim().toLowerCase(),b=bk.value;let n=0;
   for(const r of rows){const ok=(!t||r.dataset.search.includes(t))&&(!b||r.dataset.bucket===b)
       &&(!flag||r.dataset.flags.includes(flag));
     r.classList.toggle('hidden',!ok);if(ok)n++;}
   sh.textContent=n+' shown';}
 q.oninput=ap;bk.onchange=ap;
 document.querySelectorAll('.preset').forEach(b=>b.onclick=()=>{
   flag=b.dataset.f;
   document.querySelectorAll('.preset').forEach(x=>x.classList.toggle('on',x===b));ap();});
 let sortKey=null,asc=true;
 document.querySelectorAll('.head span').forEach(h=>h.onclick=()=>{
   const k=h.dataset.s,num=h.dataset.t==='n';
   asc=sortKey===k?!asc:true;sortKey=k;
   const sorted=[...rows].sort((a,b)=>{
     let x=a.dataset[k]||'',y=b.dataset[k]||'';
     if(num){x=x===''?-Infinity:+x;y=y===''?-Infinity:+y;return asc?x-y:y-x;}
     return asc?x.localeCompare(y):y.localeCompare(x);});
   sorted.forEach(r=>list.appendChild(r));});
 ap();
</script></body></html>"""


if __name__ == "__main__":
    main()
