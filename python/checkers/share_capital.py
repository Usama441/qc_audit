from checkers import result, selected
from checkers.loader import find_row, last_numeric

CATEGORY = "13. Share Capital"
RULE_KEY = "share_capital.share_capital_vs_balance_sheet"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    if not selected(enabled_rule_keys, RULE_KEY):
        return []

    share_capital = sheets.get("share_capital")
    balance_sheet = sheets.get("balance_sheet")

    if share_capital is None:
        return [result(RULE_KEY, "Share Capital vs Balance Sheet", CATEGORY, "skip", "Share Capital sheet not found.")]

    total_row = find_row(share_capital, "total")
    if total_row is None and not share_capital.empty:
        total_row = share_capital.iloc[-1]
    share_capital_total = last_numeric(total_row)
    balance_sheet_value = last_numeric(find_row(balance_sheet, "share capital") if balance_sheet is not None else None)

    if share_capital_total is None:
        return [result(RULE_KEY, "Share Capital vs Balance Sheet", CATEGORY, "skip",
                       "Could not identify total from Share Capital schedule.")]
    if balance_sheet_value is None:
        return [result(RULE_KEY, "Share Capital vs Balance Sheet", CATEGORY, "warning",
                       f"Share Capital schedule total: {share_capital_total:,.2f}. Share Capital not found on Balance Sheet.",
                       {"schedule_total": round(share_capital_total, 2)})]
    if abs(share_capital_total - balance_sheet_value) <= TOLERANCE:
        return [result(RULE_KEY, "Share Capital vs Balance Sheet", CATEGORY, "pass",
                       f"Share capital matches Balance Sheet: {share_capital_total:,.2f}")]
    return [result(RULE_KEY, "Share Capital vs Balance Sheet", CATEGORY, "fail",
                   f"Share capital mismatch: Schedule={share_capital_total:,.2f}, BS={balance_sheet_value:,.2f}",
                   {"schedule": round(share_capital_total, 2), "balance_sheet": round(balance_sheet_value, 2)})]
