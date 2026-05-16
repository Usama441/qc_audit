from checkers import CheckResult
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "6. Cash Flow"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    cf = sheets.get("cash_flow")
    pl = sheets.get("profit_loss")
    bs = sheets.get("balance_sheet")

    if cf is None:
        results.append(CheckResult("Cash Flow checks", CATEGORY, "skip",
                                   "Cash Flow Statement sheet not found."))
        return results

    # 6a — Net profit from SoCI (profit before tax)
    cf_pbt  = last_numeric(first_present(find_row(cf, "profit before tax"), find_row(cf, "net profit")))
    soci_pbt = last_numeric(
        first_present(find_row(pl, "profit before tax"), find_row(pl, "net profit")) if pl is not None else None
    )

    if cf_pbt is None:
        results.append(CheckResult("Profit Before Tax (CF vs SoCI)", CATEGORY, "skip",
                                   "Could not find profit before tax in Cash Flow statement."))
    elif soci_pbt is None:
        results.append(CheckResult("Profit Before Tax (CF vs SoCI)", CATEGORY, "skip",
                                   "Could not find profit before tax in P&L (SoCI)."))
    elif abs(cf_pbt - soci_pbt) <= TOLERANCE:
        results.append(CheckResult("Profit Before Tax (CF vs SoCI)", CATEGORY, "pass",
                                   f"Profit before tax matches: CF={cf_pbt:,.2f}, SoCI={soci_pbt:,.2f}"))
    else:
        results.append(CheckResult("Profit Before Tax (CF vs SoCI)", CATEGORY, "fail",
                                   f"Profit before tax mismatch: CF={cf_pbt:,.2f}, SoCI={soci_pbt:,.2f}",
                                   {"cf": round(cf_pbt,2), "soci": round(soci_pbt,2)}))

    # 6b — Depreciation added back (should be positive in operating activities)
    dep_row = first_present(find_row(cf, "depreciation"), find_row(cf, "amortisation"), find_row(cf, "amortization"))
    dep_val = last_numeric(dep_row)
    if dep_val is None:
        results.append(CheckResult("Depreciation Added Back", CATEGORY, "skip",
                                   "No depreciation line found in Cash Flow."))
    elif dep_val > 0:
        results.append(CheckResult("Depreciation Added Back", CATEGORY, "pass",
                                   f"Depreciation {dep_val:,.2f} is added back (positive)."))
    else:
        results.append(CheckResult("Depreciation Added Back", CATEGORY, "fail",
                                   f"Depreciation {dep_val:,.2f} is negative — should be added back as positive.",
                                   {"depreciation": round(dep_val,2)}))

    # 6c — Bad debt added back
    bd_row = first_present(find_row(cf, "bad debt"), find_row(cf, "impairment"), find_row(cf, "provision"))
    bd_val = last_numeric(bd_row)
    if bd_val is None:
        results.append(CheckResult("Bad Debt Added Back", CATEGORY, "skip",
                                   "No bad debt / provision line found in Cash Flow."))
    elif bd_val > 0:
        results.append(CheckResult("Bad Debt Added Back", CATEGORY, "pass",
                                   f"Bad debt provision {bd_val:,.2f} is added back (positive)."))
    else:
        results.append(CheckResult("Bad Debt Added Back", CATEGORY, "warning",
                                   f"Bad debt / provision {bd_val:,.2f} is not positive — confirm it is added back.",
                                   {"value": round(bd_val,2)}))

    # 6d — Opening cash = prior year BS cash & bank
    open_row = first_present(find_row(cf, "beginning"), find_row(cf, "opening"), find_row(cf, "start of year"))
    cf_open  = last_numeric(open_row)
    # Prior year balance on BS is not in scope of a single-year file — flag for manual review
    if cf_open is None:
        results.append(CheckResult("Opening Cash vs Prior Year BS", CATEGORY, "skip",
                                   "Could not identify opening cash figure in Cash Flow statement."))
    else:
        results.append(CheckResult("Opening Cash vs Prior Year BS", CATEGORY, "warning",
                                   f"Opening cash per CF: {cf_open:,.2f}. "
                                   "Verify this matches prior year Balance Sheet cash & bank balance.",
                                   {"opening_cash": round(cf_open,2)}))

    # 6e — Closing cash = current year BS cash & bank
    close_row = first_present(find_row(cf, "end of"), find_row(cf, "closing"), find_row(cf, "end of period"))
    cf_close  = last_numeric(close_row)
    bs_cash   = last_numeric(find_row(bs, "cash", "bank") if bs is not None else None)

    if cf_close is None:
        results.append(CheckResult("Closing Cash vs Balance Sheet", CATEGORY, "skip",
                                   "Could not identify closing cash figure in Cash Flow statement."))
    elif bs_cash is None:
        results.append(CheckResult("Closing Cash vs Balance Sheet", CATEGORY, "skip",
                                   "Could not identify cash & bank on Balance Sheet."))
    elif abs(cf_close - bs_cash) <= TOLERANCE:
        results.append(CheckResult("Closing Cash vs Balance Sheet", CATEGORY, "pass",
                                   f"Closing cash matches: CF={cf_close:,.2f}, BS={bs_cash:,.2f}"))
    else:
        results.append(CheckResult("Closing Cash vs Balance Sheet", CATEGORY, "fail",
                                   f"Closing cash mismatch: CF={cf_close:,.2f}, BS={bs_cash:,.2f}",
                                   {"cf_close": round(cf_close,2), "bs_cash": round(bs_cash,2)}))

    return results
