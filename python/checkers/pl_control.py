from checkers import CheckResult
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "10. PL Control (Payables)"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    pl_ctrl = sheets.get("pl_control")
    bs      = sheets.get("balance_sheet")

    if pl_ctrl is None:
        results.append(CheckResult("PL Control checks", CATEGORY, "skip",
                                   "PL Control (AP) sheet not found."))
        return results

    pl_total = last_numeric(first_present(find_row(pl_ctrl, "total"), find_row(pl_ctrl, "aged payable")))

    bs_ap = None
    if bs is not None:
        ap_row = first_present(find_row(bs, "accounts payable"), find_row(bs, "trade payable"),
                               find_row(bs, "creditor"))
        bs_ap = last_numeric(ap_row)

    if pl_total is None:
        results.append(CheckResult("Total AP vs Balance Sheet", CATEGORY, "skip",
                                   "Could not identify total from PL Control report."))
    elif bs_ap is None:
        results.append(CheckResult("Total AP vs Balance Sheet", CATEGORY, "warning",
                                   f"PL Control total: {pl_total:,.2f}. "
                                   "Accounts Payable not found on Balance Sheet.",
                                   {"pl_total": round(pl_total,2)}))
    elif abs(pl_total - bs_ap) <= TOLERANCE:
        results.append(CheckResult("Total AP vs Balance Sheet", CATEGORY, "pass",
                                   f"Total payable matches BS: {pl_total:,.2f}"))
    else:
        results.append(CheckResult("Total AP vs Balance Sheet", CATEGORY, "fail",
                                   f"AP mismatch: PL Control={pl_total:,.2f}, BS={bs_ap:,.2f}",
                                   {"pl_control": round(pl_total,2), "balance_sheet": round(bs_ap,2)}))

    return results
