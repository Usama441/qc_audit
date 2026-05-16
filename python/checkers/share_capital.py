from checkers import CheckResult
from checkers.loader import find_row, last_numeric

CATEGORY = "13. Share Capital"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    sc = sheets.get("share_capital")
    bs = sheets.get("balance_sheet")

    if sc is None:
        results.append(CheckResult("Share Capital vs Balance Sheet", CATEGORY, "skip",
                                   "Share Capital sheet not found."))
        return results

    total_row = find_row(sc, "total")
    if total_row is None and not sc.empty:
        total_row = sc.iloc[-1]
    sc_total = last_numeric(total_row)
    bs_sc    = last_numeric(find_row(bs, "share capital") if bs is not None else None)

    if sc_total is None:
        results.append(CheckResult("Share Capital vs Balance Sheet", CATEGORY, "skip",
                                   "Could not identify total from Share Capital schedule."))
    elif bs_sc is None:
        results.append(CheckResult("Share Capital vs Balance Sheet", CATEGORY, "warning",
                                   f"Share Capital schedule total: {sc_total:,.2f}. "
                                   "Share Capital not found on Balance Sheet.",
                                   {"schedule_total": round(sc_total,2)}))
    elif abs(sc_total - bs_sc) <= TOLERANCE:
        results.append(CheckResult("Share Capital vs Balance Sheet", CATEGORY, "pass",
                                   f"Share capital matches Balance Sheet: {sc_total:,.2f}"))
    else:
        results.append(CheckResult("Share Capital vs Balance Sheet", CATEGORY, "fail",
                                   f"Share capital mismatch: Schedule={sc_total:,.2f}, BS={bs_sc:,.2f}",
                                   {"schedule": round(sc_total,2), "balance_sheet": round(bs_sc,2)}))

    return results
