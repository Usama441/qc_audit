import pandas as pd
from checkers import result, selected
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "11. Bank Control"
TOLERANCE = 1.0

RULE_TOTAL = "bank_control.bank_total_vs_balance_sheet"
RULE_INCLUSION = "bank_control.all_non_zero_bank_accounts_included"


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    results = []
    bank_control = sheets.get("bank_control")
    balance_sheet = sheets.get("balance_sheet")

    if bank_control is None:
        return _missing_bank_control_results(enabled_rule_keys)

    balance_col = next((c for c in bank_control.columns if "balance" in str(c).lower() or "amount" in str(c).lower()), None)

    if selected(enabled_rule_keys, RULE_TOTAL):
        bank_total_row = first_present(find_row(bank_control, "total"), find_row(bank_control, "balance of"), find_row(bank_control, "transactions without statement"))
        bank_total = last_numeric(bank_total_row)

        balance_sheet_cash = None
        if balance_sheet is not None:
            cash_row = first_present(find_row(balance_sheet, "cash", "bank"), find_row(balance_sheet, "cash and cash equivalents"), find_row(balance_sheet, "bank"))
            balance_sheet_cash = last_numeric(cash_row)

        if bank_total is None:
            results.append(result(RULE_TOTAL, "Bank Total vs Balance Sheet", CATEGORY, "skip",
                                  "Could not identify total from Bank Control."))
        elif balance_sheet_cash is None:
            results.append(result(RULE_TOTAL, "Bank Total vs Balance Sheet", CATEGORY, "warning",
                                  f"Bank Control total: {bank_total:,.2f}. Cash & bank not found on Balance Sheet.",
                                  {"bank_total": round(bank_total, 2)}))
        elif abs(bank_total - balance_sheet_cash) <= TOLERANCE:
            results.append(result(RULE_TOTAL, "Bank Total vs Balance Sheet", CATEGORY, "pass",
                                  f"Bank balance matches BS cash & bank: {bank_total:,.2f}"))
        else:
            results.append(result(RULE_TOTAL, "Bank Total vs Balance Sheet", CATEGORY, "fail",
                                  f"Bank balance mismatch: Bank Control={bank_total:,.2f}, BS={balance_sheet_cash:,.2f}",
                                  {"bank_control": round(bank_total, 2), "balance_sheet": round(balance_sheet_cash, 2)}))

    if selected(enabled_rule_keys, RULE_INCLUSION):
        if balance_col is None:
            results.append(result(RULE_INCLUSION, "All Non-Zero Bank Accounts Included", CATEGORY, "skip",
                                  "Could not identify balance column in Bank Control."))
        else:
            series = pd.to_numeric(bank_control[balance_col], errors="coerce")
            zero_rows = series[(series == 0) | series.isna()]
            nonzero_rows = series[series.abs() > TOLERANCE]
            results.append(result(RULE_INCLUSION, "All Non-Zero Bank Accounts Included", CATEGORY, "pass",
                                  f"{len(nonzero_rows)} non-zero bank account(s) included; {len(zero_rows)} zero/blank row(s) present."))

    return results


def _missing_bank_control_results(enabled_rule_keys) -> list:
    results = []
    if selected(enabled_rule_keys, RULE_TOTAL):
        results.append(result(RULE_TOTAL, "Bank Total vs Balance Sheet", CATEGORY, "skip", "Bank Control sheet not found."))
    if selected(enabled_rule_keys, RULE_INCLUSION):
        results.append(result(RULE_INCLUSION, "All Non-Zero Bank Accounts Included", CATEGORY, "skip", "Bank Control sheet not found."))
    return results
