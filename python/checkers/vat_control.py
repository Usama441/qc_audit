from checkers import result, selected
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "14. VAT Control"
RULE_KEY = "vat_control.vat_control_vs_balance_sheet"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    if not selected(enabled_rule_keys, RULE_KEY):
        return []

    vat_control = sheets.get("vat_control")
    balance_sheet = sheets.get("balance_sheet")

    if vat_control is None:
        return [result(RULE_KEY, "VAT Control vs Balance Sheet", CATEGORY, "skip", "VAT Control sheet not found.")]

    vat_total = last_numeric(first_present(find_row(vat_control, "total"), find_row(vat_control, "net vat"),
                                           find_row(vat_control, "vat liability"), find_row(vat_control, "balance")))
    balance_sheet_vat = last_numeric(
        first_present(find_row(balance_sheet, "vat"), find_row(balance_sheet, "tax payable"), find_row(balance_sheet, "vat payable"))
        if balance_sheet is not None else None
    )

    if vat_total is None:
        return [result(RULE_KEY, "VAT Control vs Balance Sheet", CATEGORY, "skip",
                       "Could not identify total/balance from VAT Control sheet.")]
    if balance_sheet_vat is None:
        return [result(RULE_KEY, "VAT Control vs Balance Sheet", CATEGORY, "warning",
                       f"VAT Control total: {vat_total:,.2f}. VAT payable/receivable not found on Balance Sheet.",
                       {"vat_total": round(vat_total, 2)})]
    if abs(vat_total - balance_sheet_vat) <= TOLERANCE:
        return [result(RULE_KEY, "VAT Control vs Balance Sheet", CATEGORY, "pass",
                       f"VAT Control matches Balance Sheet: {vat_total:,.2f}")]
    return [result(RULE_KEY, "VAT Control vs Balance Sheet", CATEGORY, "fail",
                   f"VAT mismatch: Control={vat_total:,.2f}, BS={balance_sheet_vat:,.2f}",
                   {"vat_control": round(vat_total, 2), "balance_sheet": round(balance_sheet_vat, 2)})]
