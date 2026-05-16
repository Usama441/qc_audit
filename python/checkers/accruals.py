from checkers import result, selected
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "12. Accruals"
RULE_KEY = "accruals.audit_fees_accrual_vs_balance_sheet"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    if not selected(enabled_rule_keys, RULE_KEY):
        return []

    accruals = sheets.get("accruals")
    balance_sheet = sheets.get("balance_sheet")

    if accruals is None:
        return [result(RULE_KEY, "Audit Fees Accrual vs Balance Sheet", CATEGORY, "skip", "Accruals sheet not found.")]

    audit_row = first_present(find_row(accruals, "audit"), find_row(accruals, "audit fee"))
    accrual_audit = last_numeric(audit_row)

    balance_sheet_audit = None
    if balance_sheet is not None:
        balance_sheet_row = first_present(find_row(balance_sheet, "accrued"), find_row(balance_sheet, "accrual"), find_row(balance_sheet, "audit fee"))
        balance_sheet_audit = last_numeric(balance_sheet_row)

    if accrual_audit is None:
        return [result(RULE_KEY, "Audit Fees Accrual vs Balance Sheet", CATEGORY, "skip",
                       "No audit fees line found in Accruals schedule.")]
    if balance_sheet_audit is None:
        return [result(RULE_KEY, "Audit Fees Accrual vs Balance Sheet", CATEGORY, "warning",
                       f"Audit fees accrual: {accrual_audit:,.2f}. Could not find matching line on Balance Sheet.",
                       {"accrual": round(accrual_audit, 2)})]
    if abs(accrual_audit - balance_sheet_audit) <= TOLERANCE:
        return [result(RULE_KEY, "Audit Fees Accrual vs Balance Sheet", CATEGORY, "pass",
                       f"Audit fees accrual matches Balance Sheet: {accrual_audit:,.2f}")]
    return [result(RULE_KEY, "Audit Fees Accrual vs Balance Sheet", CATEGORY, "fail",
                   f"Audit fees accrual mismatch: Schedule={accrual_audit:,.2f}, BS={balance_sheet_audit:,.2f}",
                   {"schedule": round(accrual_audit, 2), "balance_sheet": round(balance_sheet_audit, 2)})]
