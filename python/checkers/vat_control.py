from checkers import CheckResult
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "14. VAT Control"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    vat = sheets.get("vat_control")
    bs  = sheets.get("balance_sheet")

    if vat is None:
        results.append(CheckResult("VAT Control vs Balance Sheet", CATEGORY, "skip",
                                   "VAT Control sheet not found."))
        return results

    vat_total = last_numeric(first_present(find_row(vat, "total"), find_row(vat, "net vat"),
                                           find_row(vat, "vat liability"), find_row(vat, "balance")))
    bs_vat    = last_numeric(
        first_present(find_row(bs, "vat"), find_row(bs, "tax payable"), find_row(bs, "vat payable")) if bs is not None else None
    )

    if vat_total is None:
        results.append(CheckResult("VAT Control vs Balance Sheet", CATEGORY, "skip",
                                   "Could not identify total/balance from VAT Control sheet."))
    elif bs_vat is None:
        results.append(CheckResult("VAT Control vs Balance Sheet", CATEGORY, "warning",
                                   f"VAT Control total: {vat_total:,.2f}. "
                                   "VAT payable/receivable not found on Balance Sheet.",
                                   {"vat_total": round(vat_total,2)}))
    elif abs(vat_total - bs_vat) <= TOLERANCE:
        results.append(CheckResult("VAT Control vs Balance Sheet", CATEGORY, "pass",
                                   f"VAT Control matches Balance Sheet: {vat_total:,.2f}"))
    else:
        results.append(CheckResult("VAT Control vs Balance Sheet", CATEGORY, "fail",
                                   f"VAT mismatch: Control={vat_total:,.2f}, BS={bs_vat:,.2f}",
                                   {"vat_control": round(vat_total,2), "balance_sheet": round(bs_vat,2)}))

    return results
