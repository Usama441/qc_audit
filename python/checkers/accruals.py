from checkers import CheckResult
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "12. Accruals"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    ac = sheets.get("accruals")
    bs = sheets.get("balance_sheet")

    if ac is None:
        results.append(CheckResult("Accruals checks", CATEGORY, "skip",
                                   "Accruals sheet not found."))
        return results

    # Audit fees accrual row
    audit_row = first_present(find_row(ac, "audit"), find_row(ac, "audit fee"))
    ac_audit  = last_numeric(audit_row)

    # Balance sheet accrued liabilities / audit fees
    bs_row    = None
    bs_audit  = None
    if bs is not None:
        bs_row   = first_present(find_row(bs, "accrued"), find_row(bs, "accrual"), find_row(bs, "audit fee"))
        bs_audit = last_numeric(bs_row)

    if ac_audit is None:
        results.append(CheckResult("Audit Fees Accrual vs Balance Sheet", CATEGORY, "skip",
                                   "No audit fees line found in Accruals schedule."))
    elif bs_audit is None:
        results.append(CheckResult("Audit Fees Accrual vs Balance Sheet", CATEGORY, "warning",
                                   f"Audit fees accrual: {ac_audit:,.2f}. "
                                   "Could not find matching line on Balance Sheet.",
                                   {"accrual": round(ac_audit,2)}))
    elif abs(ac_audit - bs_audit) <= TOLERANCE:
        results.append(CheckResult("Audit Fees Accrual vs Balance Sheet", CATEGORY, "pass",
                                   f"Audit fees accrual matches Balance Sheet: {ac_audit:,.2f}"))
    else:
        results.append(CheckResult("Audit Fees Accrual vs Balance Sheet", CATEGORY, "fail",
                                   f"Audit fees accrual mismatch: Schedule={ac_audit:,.2f}, BS={bs_audit:,.2f}",
                                   {"schedule": round(ac_audit,2), "balance_sheet": round(bs_audit,2)}))

    return results
