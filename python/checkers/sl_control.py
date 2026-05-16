import pandas as pd
from checkers import result, selected
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "9. SL Control"
TOLERANCE = 0.01

RULE_NEGATIVE = "sl_control.no_negative_ar_balances"
RULE_TOTAL = "sl_control.total_ar_vs_balance_sheet"


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    results = []
    sl_control = sheets.get("sl_control")
    balance_sheet = sheets.get("balance_sheet")

    if sl_control is None:
        return _missing_sl_control_results(enabled_rule_keys)

    numeric_cols = [column for column in sl_control.columns if pd.to_numeric(sl_control[column], errors="coerce").notna().any()]

    if selected(enabled_rule_keys, RULE_NEGATIVE):
        negatives = {}
        for column in numeric_cols:
            series = pd.to_numeric(sl_control[column], errors="coerce")
            negative_rows = series[series < -TOLERANCE]
            if not negative_rows.empty:
                negatives[str(column)] = {"count": len(negative_rows), "min": round(float(negative_rows.min()), 2)}

        if negatives:
            results.append(result(RULE_NEGATIVE, "No Negative AR Balances", CATEGORY, "fail",
                                  f"Negative figures found in {len(negatives)} column(s) of aged receivable.",
                                  {"columns": negatives}))
        else:
            results.append(result(RULE_NEGATIVE, "No Negative AR Balances", CATEGORY, "pass",
                                  "No negative figures in aged receivable report."))

    if selected(enabled_rule_keys, RULE_TOTAL):
        total_row = first_present(find_row(sl_control, "total"), find_row(sl_control, "aged receivable"))
        sl_total = last_numeric(total_row)

        balance_sheet_ar = None
        if balance_sheet is not None:
            ar_row = first_present(find_row(balance_sheet, "accounts receivable"), find_row(balance_sheet, "trade receivable"), find_row(balance_sheet, "debtor"))
            balance_sheet_ar = last_numeric(ar_row)

        if sl_total is None:
            results.append(result(RULE_TOTAL, "Total AR vs Balance Sheet", CATEGORY, "skip",
                                  "Could not identify total from SL Control report."))
        elif balance_sheet_ar is None:
            results.append(result(RULE_TOTAL, "Total AR vs Balance Sheet", CATEGORY, "warning",
                                  f"SL Control total: {sl_total:,.2f}. Accounts Receivable not found on Balance Sheet.",
                                  {"sl_total": round(sl_total, 2)}))
        elif abs(sl_total - balance_sheet_ar) <= TOLERANCE:
            results.append(result(RULE_TOTAL, "Total AR vs Balance Sheet", CATEGORY, "pass",
                                  f"Total receivable matches BS: {sl_total:,.2f}"))
        else:
            results.append(result(RULE_TOTAL, "Total AR vs Balance Sheet", CATEGORY, "fail",
                                  f"AR mismatch: SL Control={sl_total:,.2f}, BS={balance_sheet_ar:,.2f}",
                                  {"sl_control": round(sl_total, 2), "balance_sheet": round(balance_sheet_ar, 2)}))

    return results


def _missing_sl_control_results(enabled_rule_keys) -> list:
    results = []
    if selected(enabled_rule_keys, RULE_NEGATIVE):
        results.append(result(RULE_NEGATIVE, "No Negative AR Balances", CATEGORY, "skip", "SL Control sheet not found."))
    if selected(enabled_rule_keys, RULE_TOTAL):
        results.append(result(RULE_TOTAL, "Total AR vs Balance Sheet", CATEGORY, "skip", "SL Control sheet not found."))
    return results
