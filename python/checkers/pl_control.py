from checkers import result, selected
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "10. PL Control"
RULE_KEY = "pl_control.total_ap_vs_balance_sheet"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    if not selected(enabled_rule_keys, RULE_KEY):
        return []

    pl_control = sheets.get("pl_control")
    balance_sheet = sheets.get("balance_sheet")

    if pl_control is None:
        return [result(RULE_KEY, "Total AP vs Balance Sheet", CATEGORY, "skip", "PL Control sheet not found.")]

    pl_total = last_numeric(first_present(find_row(pl_control, "total"), find_row(pl_control, "aged payable")))

    balance_sheet_ap = None
    if balance_sheet is not None:
        ap_row = first_present(find_row(balance_sheet, "accounts payable"), find_row(balance_sheet, "trade payable"), find_row(balance_sheet, "creditor"))
        balance_sheet_ap = last_numeric(ap_row)

    if pl_total is None:
        return [result(RULE_KEY, "Total AP vs Balance Sheet", CATEGORY, "skip",
                       "Could not identify total from PL Control report.")]
    if balance_sheet_ap is None:
        return [result(RULE_KEY, "Total AP vs Balance Sheet", CATEGORY, "warning",
                       f"PL Control total: {pl_total:,.2f}. Accounts Payable not found on Balance Sheet.",
                       {"pl_total": round(pl_total, 2)})]
    if abs(pl_total - balance_sheet_ap) <= TOLERANCE:
        return [result(RULE_KEY, "Total AP vs Balance Sheet", CATEGORY, "pass",
                       f"Total payable matches BS: {pl_total:,.2f}")]
    return [result(RULE_KEY, "Total AP vs Balance Sheet", CATEGORY, "fail",
                   f"AP mismatch: PL Control={pl_total:,.2f}, BS={balance_sheet_ap:,.2f}",
                   {"pl_control": round(pl_total, 2), "balance_sheet": round(balance_sheet_ap, 2)})]
