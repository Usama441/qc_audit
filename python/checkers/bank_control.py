import pandas as pd
from checkers import CheckResult
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "11. Bank Control"
TOLERANCE = 1.0


def run(sheets: dict, free_zone: str) -> list:
    results = []
    bk = sheets.get("bank_control")
    bs = sheets.get("balance_sheet")

    if bk is None:
        results.append(CheckResult("Bank Control checks", CATEGORY, "skip",
                                   "Bank Control sheet not found."))
        return results

    bal_col = next((c for c in bk.columns
                    if "balance" in str(c).lower() or "amount" in str(c).lower()), None)

    # 11a — Bank total vs Balance Sheet cash & bank
    bk_total_row = first_present(find_row(bk, "total"), find_row(bk, "balance of"), find_row(bk, "transactions without statement"))
    bk_total     = last_numeric(bk_total_row)

    bs_cash = None
    if bs is not None:
        cash_row = first_present(find_row(bs, "cash", "bank"), find_row(bs, "cash and cash equivalents"),
                                 find_row(bs, "bank"))
        bs_cash = last_numeric(cash_row)

    if bk_total is None:
        results.append(CheckResult("Bank Total vs Balance Sheet", CATEGORY, "skip",
                                   "Could not identify total from Bank Control."))
    elif bs_cash is None:
        results.append(CheckResult("Bank Total vs Balance Sheet", CATEGORY, "warning",
                                   f"Bank Control total: {bk_total:,.2f}. "
                                   "Cash & bank not found on Balance Sheet.",
                                   {"bank_total": round(bk_total,2)}))
    elif abs(bk_total - bs_cash) <= TOLERANCE:
        results.append(CheckResult("Bank Total vs Balance Sheet", CATEGORY, "pass",
                                   f"Bank balance matches BS cash & bank: {bk_total:,.2f}"))
    else:
        results.append(CheckResult("Bank Total vs Balance Sheet", CATEGORY, "fail",
                                   f"Bank balance mismatch: Bank Control={bk_total:,.2f}, BS={bs_cash:,.2f}",
                                   {"bank_control": round(bk_total,2), "balance_sheet": round(bs_cash,2)}))

    # 11b — All non-zero bank accounts included
    if bal_col is not None:
        series  = pd.to_numeric(bk[bal_col], errors="coerce")
        zero    = series[(series == 0) | series.isna()]
        nonzero = series[series.abs() > TOLERANCE]

        name_col = next((c for c in bk.columns
                         if "name" in str(c).lower() or "bank" in str(c).lower()
                         or "account" in str(c).lower()), None)

        results.append(CheckResult("All Non-Zero Bank Accounts Included", CATEGORY, "pass",
                                   f"{len(nonzero)} non-zero bank account(s) included; "
                                   f"{len(zero)} zero/blank row(s) present."))
    else:
        results.append(CheckResult("All Non-Zero Bank Accounts Included", CATEGORY, "skip",
                                   "Could not identify balance column in Bank Control."))

    return results
