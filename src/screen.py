"""Fundamentals-only screening signals computed from the captured FT statements.

One entry point: compute_signals(rec) -> dict of metrics + boolean flags.
Periods are newest-first (index 0 = latest fiscal year).
"""


def _row(statement, label):
    if not statement:
        return None
    for r in statement["rows"]:
        if not r["section"] and r["label"].lower() == label.lower():
            return r["values"]
    return None


def _latest(vals):
    if not vals:
        return None
    for v in vals:  # newest-first
        if v is not None:
            return v
    return None


def _oldest(vals):
    if not vals:
        return None
    for v in reversed(vals):
        if v is not None:
            return v
    return None


def _clean(vals):
    return [v for v in (vals or []) if v is not None]


def compute_signals(rec):
    inc = rec["statements"].get("income")
    bal = rec["statements"].get("balance")
    cf = rec["statements"].get("cashflow")
    price = rec.get("price")
    gbx = rec.get("currency") in ("GBX", "GBp")
    scale = 100 if gbx else 1  # pence vs major-unit for per-share figures

    equity = _row(bal, "Total equity")
    total_debt = _row(bal, "Total debt")
    tca = _row(bal, "Total current assets")
    tcl = _row(bal, "Total current liabilities")
    tl = _row(bal, "Total liabilities")
    shares = _row(bal, "Total common shares outstanding")
    revenue = _row(inc, "Total revenue")
    net_income = _row(inc, "Net income")
    op_cf = _row(cf, "Total cash from operations")

    eq = _latest(equity)
    sh = _latest(shares)
    s = {}

    # ── valuation vs assets ────────────────────────────────────────────────
    if eq is not None and sh:
        bvps = (eq / sh) * scale
        s["book_value_per_share"] = bvps
        if price and bvps > 0:
            s["price_to_book"] = price / bvps
    tca_l, tl_l = _latest(tca), _latest(tl)
    if tca_l is not None and tl_l is not None and sh:
        s["ncav_per_share"] = ((tca_l - tl_l) / sh) * scale

    # ── balance-sheet strength ─────────────────────────────────────────────
    td, eql = _latest(total_debt), eq
    if td is not None and eql:
        s["debt_to_equity"] = td / eql if eql != 0 else None
    if tca is not None and tcl is not None:
        cl = _latest(tcl)
        s["current_ratio"] = _latest(tca) / cl if cl else None
    if td is not None:
        s["total_debt"] = td

    # ── trends over the captured window ────────────────────────────────────
    rev = _clean(revenue)
    if len(rev) >= 2:
        new, old = _latest(revenue), _oldest(revenue)
        s["revenue_latest"] = new
        if new is not None and old not in (None, 0):
            s["revenue_change_pct"] = (new - old) / abs(old) * 100
    ni = _clean(net_income)
    if ni:
        s["loss_years"] = sum(1 for v in ni if v < 0)
        s["net_income_latest"] = _latest(net_income)
    if equity:
        s["equity_eroding"] = (_latest(equity) is not None
                               and _oldest(equity) is not None
                               and _latest(equity) < _oldest(equity))
    if op_cf is not None:
        s["op_cash_flow_latest"] = _latest(op_cf)

    # ── flags ──────────────────────────────────────────────────────────────
    pb = s.get("price_to_book")
    de = s.get("debt_to_equity")
    cr = s.get("current_ratio")
    ncav = s.get("ncav_per_share")

    s["flag_below_book"] = pb is not None and 0 < pb < 1
    s["flag_net_net"] = (ncav is not None and ncav > 0 and price is not None
                         and ncav > price)
    s["flag_low_debt"] = (de is not None and de < 0.5
                          and (cr is None or cr > 1.5))

    distress = 0
    rev_chg = s.get("revenue_change_pct")
    ocf = s.get("op_cash_flow_latest")
    if rev_chg is not None and rev_chg < -25:
        distress += 1
    if s.get("loss_years", 0) >= 3:
        distress += 1
    if s.get("equity_eroding"):
        distress += 1
    if ocf is not None and ocf < 0:
        distress += 1
    s["distress_score"] = distress
    s["flag_distressed"] = distress >= 2

    return s
