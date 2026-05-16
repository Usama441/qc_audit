from checkers import result, selected
from checkers.loader import find_row, last_numeric

CATEGORY = "7. Prepayment"
RULE_KEY = "prepayment.prepayment_vs_trial_balance"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    if not selected(enabled_rule_keys, RULE_KEY):
        return []

    prepayment = sheets.get("prepayment")
    trial_balance = sheets.get("trial_balance")

    if prepayment is None:
        return [result(RULE_KEY, "Prepayment vs Trial Balance", CATEGORY, "skip", "Prepayment sheet not found.")]

    total_row = find_row(prepayment, "total")
    if total_row is None and not prepayment.empty:
        total_row = prepayment.iloc[-1]
    prepayment_total = last_numeric(total_row)

    trial_balance_row = find_row(trial_balance, "prepayment") if trial_balance is not None else None
    trial_balance_value = last_numeric(trial_balance_row)

    if prepayment_total is None:
        return [result(RULE_KEY, "Prepayment vs Trial Balance", CATEGORY, "skip",
                       "Could not identify total from Prepayment schedule.")]
    if trial_balance_value is None:
        return [result(RULE_KEY, "Prepayment vs Trial Balance", CATEGORY, "warning",
                       f"Prepayment schedule total: {prepayment_total:,.2f}. No prepayment account found in Trial Balance to compare.",
                       {"schedule_total": round(prepayment_total, 2)})]
    if abs(prepayment_total - trial_balance_value) <= TOLERANCE:
        return [result(RULE_KEY, "Prepayment vs Trial Balance", CATEGORY, "pass",
                       f"Prepayment matches: Schedule={prepayment_total:,.2f}, TB={trial_balance_value:,.2f}")]
    return [result(RULE_KEY, "Prepayment vs Trial Balance", CATEGORY, "fail",
                   f"Prepayment mismatch: Schedule={prepayment_total:,.2f}, TB={trial_balance_value:,.2f}",
                   {"schedule": round(prepayment_total, 2), "tb": round(trial_balance_value, 2)})]
