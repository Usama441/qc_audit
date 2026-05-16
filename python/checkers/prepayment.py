from checkers import CheckResult
from checkers.loader import find_row, last_numeric

CATEGORY = "7. Prepayment"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    pp = sheets.get("prepayment")
    tb = sheets.get("trial_balance")

    if pp is None:
        results.append(CheckResult("Prepayment vs Trial Balance", CATEGORY, "skip",
                                   "Prepayment sheet not found."))
        return results

    total_row = find_row(pp, "total")
    if total_row is None and not pp.empty:
        total_row = pp.iloc[-1]
    pp_total  = last_numeric(total_row)

    tb_row  = find_row(tb, "prepayment") if tb is not None else None
    tb_val  = last_numeric(tb_row)

    if pp_total is None:
        results.append(CheckResult("Prepayment vs Trial Balance", CATEGORY, "skip",
                                   "Could not identify total from Prepayment schedule."))
    elif tb_val is None:
        results.append(CheckResult("Prepayment vs Trial Balance", CATEGORY, "warning",
                                   f"Prepayment schedule total: {pp_total:,.2f}. "
                                   "No prepayment account found in Trial Balance to compare.",
                                   {"schedule_total": round(pp_total,2)}))
    elif abs(pp_total - tb_val) <= TOLERANCE:
        results.append(CheckResult("Prepayment vs Trial Balance", CATEGORY, "pass",
                                   f"Prepayment matches: Schedule={pp_total:,.2f}, TB={tb_val:,.2f}"))
    else:
        results.append(CheckResult("Prepayment vs Trial Balance", CATEGORY, "fail",
                                   f"Prepayment mismatch: Schedule={pp_total:,.2f}, TB={tb_val:,.2f}",
                                   {"schedule": round(pp_total,2), "tb": round(tb_val,2)}))

    return results
