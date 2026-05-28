"""Render index_report.json into a styled dark PDF via fpdf2.

Run: uv run report_pdf.py  ->  index_report.pdf
"""

import json

from fpdf import FPDF

BG = (13, 17, 23)
PANEL = (22, 27, 34)
TXT = (230, 237, 243)
MUTED = (139, 148, 158)
BORDER = (60, 67, 78)
POS = (86, 211, 100)
NEG = (248, 113, 113)
ACCENT = (240, 136, 62)

# column widths (landscape A4 usable ~ 277mm)
COLS = [("Index", 72, "L"), ("Money growth", 52, "L"),
        ("Nominal", 70, "L"), ("After money creation", 82, "L")]
ROW_H = 11


def ret_str(d):
    return f"{d['total_pct']:+,.0f}% ({d['cagr_pct']:.1f}%)"


class Report(FPDF):
    def header(self):
        pass

    def fill_bg(self):
        self.set_fill_color(*BG)
        self.rect(0, 0, self.w, self.h, "F")

    def cell_box(self, w, text, align="L", bold=False, color=TXT, fill=None):
        x, y = self.get_x(), self.get_y()
        if fill:
            self.set_fill_color(*fill)
            self.rect(x, y, w, ROW_H, "F")
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.rect(x, y, w, ROW_H)
        self.set_font("Courier", "B" if bold else "", 10)
        self.set_text_color(*color)
        pad = 3
        self.set_xy(x + pad, y)
        self.cell(w - 2 * pad, ROW_H, text, align=align)
        self.set_xy(x + w, y)


def main():
    data = json.load(open("index_report.json"))
    rows = sorted(data["rows"], key=lambda r: r["m2"]["total_pct"], reverse=True)

    pdf = Report(orientation="L", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.fill_bg()
    pdf.set_left_margin(10)

    # title
    pdf.set_xy(10, 12)
    pdf.set_font("Courier", "B", 18)
    pdf.set_text_color(*TXT)
    pdf.cell(0, 9, "Real Index Returns")
    pdf.set_xy(10, 22)
    pdf.set_font("Courier", "", 11)
    pdf.set_text_color(*MUTED)
    yr = data["start_year"]
    pdf.cell(0, 6, f"Nominal vs. after money creation  |  {yr}-2026  |  "
                   f"each index deflated by its own money supply")

    # header row
    y = 34
    pdf.set_xy(10, y)
    for name, w, _ in COLS:
        pdf.cell_box(w, name, "L", bold=True, color=MUTED, fill=PANEL)
    y += ROW_H

    for r in rows:
        pdf.set_xy(10, y)
        tag = f" ({r['region']})"
        pdf.cell_box(COLS[0][1], r["name"] + tag, "L", color=TXT)
        pdf.cell_box(COLS[1][1], f"{r['money_growth_pct']:+,.0f}%", "L", color=MUTED)
        pdf.cell_box(COLS[2][1], ret_str(r["nominal"]), "L", color=TXT)
        real = r["m2"]
        pdf.cell_box(COLS[3][1], ret_str(real), "L", bold=True,
                     color=POS if real["total_pct"] >= 0 else NEG)
        y += ROW_H

    # story + footnotes
    y += 6
    pdf.set_xy(10, y)
    pdf.set_font("Courier", "B", 11)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 6, "The story")
    pdf.set_xy(10, y + 7)
    pdf.set_font("Courier", "", 9)
    pdf.set_text_color(*TXT)
    story = ("Once you strip out money-supply growth, the emerging-market winners "
             "are the biggest losers: Sensex and Shanghai's entire rise was money "
             "printing. Japan, Taiwan and the NASDAQ are the genuine real compounders.")
    pdf.multi_cell(255, 5, story)
    pdf.set_xy(10, pdf.get_y() + 3)
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(*MUTED)
    note = ("TR = total return (dividends reinvested); price = price index "
            "(understates by dividend yield).  Money supply: US M2 + FRED OECD "
            "broad money (UK/EZ/JP/KR); CN/IN/TW/HK curated official anchors.")
    pdf.multi_cell(255, 4.5, note)

    pdf.output("index_report.pdf")
    print("Wrote index_report.pdf")


if __name__ == "__main__":
    main()
