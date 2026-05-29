"""Render index_report.json into a dark monospace HTML page -> results/index.html
(served at /results). Run: uv run report_html.py
"""

import json
from html import escape

from paths import DATA, OUTPUT

OUT = OUTPUT / "results"


def ret(d):
    return f"{d['total_pct']:+,.0f}% ({d['cagr_pct']:.1f}%)"


def main():
    data = json.load(open(DATA / "index_report.json"))
    rows = sorted(data["rows"], key=lambda r: r["m2"]["total_pct"], reverse=True)

    trs = []
    for r in rows:
        real = r["m2"]
        cls = "pos" if real["total_pct"] >= 0 else "neg"
        trs.append(
            f'<tr><td class="idx">{escape(r["name"])} '
            f'<span class="rg">({escape(r["region"])})</span> '
            f'<span class="bs">{escape(r["basis"])}</span></td>'
            f'<td class="m muted">{r["money_growth_pct"]:+,.0f}%</td>'
            f'<td class="m">{ret(r["nominal"])}</td>'
            f'<td class="m bold {cls}">{ret(real)}</td></tr>')

    html = TEMPLATE.replace("{{GENERATED}}", data["generated"]).replace(
        "{{START}}", str(data["start_year"])).replace("{{ROWS}}", "\n".join(trs))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(html)
    print(f"Wrote {OUT}/index.html ({len(rows)} indexes)")


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Real Index Returns — after money creation</title>
<style>
 :root{--bg:#0d1117;--panel:#161b22;--line:#3c434e;--txt:#e6edf3;--muted:#8b949e;
       --pos:#56d364;--neg:#f87171;--accent:#f0883e;}
 *{box-sizing:border-box;}
 body{margin:0;background:var(--bg);color:var(--txt);
   font:15px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
 .wrap{max-width:1100px;margin:0 auto;padding:40px 28px 60px;}
 h1{font-size:26px;margin:0 0 6px;letter-spacing:.5px;}
 .sub{color:var(--muted);font-size:14px;margin-bottom:28px;}
 table{width:100%;border-collapse:collapse;}
 th,td{border:1px solid var(--line);padding:12px 16px;text-align:left;}
 thead th{color:var(--muted);font-weight:400;background:var(--panel);}
 td.m{font-variant-numeric:tabular-nums;}
 .muted{color:var(--muted);} .pos{color:var(--pos);} .neg{color:var(--neg);}
 .bold{font-weight:700;}
 .rg{color:var(--muted);} .bs{color:#4b5563;font-size:11px;}
 tbody tr:hover{background:var(--panel);}
 h2{color:var(--accent);font-size:16px;margin:34px 0 8px;}
 p.story{max-width:760px;color:var(--txt);}
 p.note{max-width:860px;color:var(--muted);font-size:12px;line-height:1.7;}
</style></head><body><div class="wrap">
 <h1>Real Index Returns</h1>
 <div class="sub">Nominal vs. after money creation &nbsp;|&nbsp; {{START}}&ndash;2026
   &nbsp;|&nbsp; each index deflated by its own money supply
   &nbsp;|&nbsp; generated {{GENERATED}}</div>
 <table>
  <thead><tr><th>Index</th><th>Money growth</th><th>Nominal</th>
    <th>After money creation</th></tr></thead>
  <tbody>
  {{ROWS}}
  </tbody>
 </table>
 <h2>The story</h2>
 <p class="story">Once you strip out money-supply growth, the emerging-market
  winners are the biggest losers: the Sensex and Shanghai's entire rise was money
  printing. Japan, Taiwan and the NASDAQ are the genuine real compounders, and
  dividends (TR vs price) decide it in Europe.</p>
 <p class="note">TR = total return (dividends reinvested); price = price index,
  which understates the real result by the dividend yield (~2&ndash;4%/yr).
  Money supply: US M2 plus FRED's OECD broad-money series (UK / Euro area / Japan
  / Korea); China, India, Taiwan and Hong Kong use curated official anchors as
  FRED's comparable series end in 2018. Figures are approximate; rankings are
  robust.</p>
</div></body></html>"""


if __name__ == "__main__":
    main()
