from checkers import result, selected
from checkers.loader import first_present, find_last_row, find_row, numeric_col, rightmost_numeric, safe_float

CATEGORY = "2. Trial Balance"
TOLERANCE = 0.01

RULE_SUM_ZERO = "trial_balance.sum_of_balances_zero"
RULE_DIVIDENDS = "trial_balance.dividends_without_share_capital"
RULE_RESERVE = "trial_balance.statutory_reserve_free_zone"
RULE_EQUITY = "trial_balance.equity_cross_check_bs_vs_soce"


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    results = []
    tb = sheets.get("trial_balance")
    bs = sheets.get("balance_sheet")
    eq = sheets.get("equity_statement")

    if tb is None:
        return _missing_trial_balance_results(enabled_rule_keys)

    debit = numeric_col(tb, "debit")
    credit = numeric_col(tb, "credit")
    balance = numeric_col(tb, "balance", "amount", "net")

    if selected(enabled_rule_keys, RULE_SUM_ZERO):
        if debit is not None and credit is not None:
            net = debit.fillna(0).sum() - credit.fillna(0).sum()
            if abs(net) <= TOLERANCE:
                results.append(result(RULE_SUM_ZERO, "Sum of Balances = 0", CATEGORY, "pass",
                                      f"Debit − Credit = {round(net, 2)} ✓"))
            else:
                results.append(result(RULE_SUM_ZERO, "Sum of Balances = 0", CATEGORY, "fail",
                                      f"Trial balance does not balance. Difference: {round(net, 2)}",
                                      {"difference": round(net, 2)}))
        elif balance is not None:
            net = balance.fillna(0).sum()
            if abs(net) <= TOLERANCE:
                results.append(result(RULE_SUM_ZERO, "Sum of Balances = 0", CATEGORY, "pass",
                                      f"Net balance column sums to {round(net, 2)} ✓"))
            else:
                results.append(result(RULE_SUM_ZERO, "Sum of Balances = 0", CATEGORY, "fail",
                                      f"Net balance column does not sum to zero. Sum = {round(net, 2)}",
                                      {"sum": round(net, 2)}))
        else:
            results.append(result(RULE_SUM_ZERO, "Sum of Balances = 0", CATEGORY, "skip",
                                  "Could not identify debit/credit or balance column in Trial Balance."))

    if selected(enabled_rule_keys, RULE_DIVIDENDS):
        dividend_row = find_row(tb, "dividend")
        share_capital_row = first_present(find_row(tb, "share capital"), find_row(tb, "capital invested"))

        if dividend_row is not None:
            dividend_value = safe_float(rightmost_numeric(dividend_row), 0)
            share_capital_value = safe_float(rightmost_numeric(share_capital_row), 0) if share_capital_row is not None else 0

            if share_capital_value == 0:
                results.append(result(RULE_DIVIDENDS, "Dividends Without Share Capital", CATEGORY, "fail",
                                      "Dividends found in TB but Share Capital is zero or missing.",
                                      {"dividend": dividend_value, "share_capital": share_capital_value}))
            else:
                results.append(result(RULE_DIVIDENDS, "Dividends Without Share Capital", CATEGORY, "pass",
                                      "Dividends present and Share Capital exists."))
        else:
            results.append(result(RULE_DIVIDENDS, "Dividends Without Share Capital", CATEGORY, "pass",
                                  "No dividend entries found — check not applicable."))

    if selected(enabled_rule_keys, RULE_RESERVE):
        if free_zone in ("freezone_10", "freezone_5"):
            reserve_row = first_present(find_row(tb, "statutory reserve"), find_row(tb, "legal reserve"))
            if reserve_row is None:
                results.append(result(RULE_RESERVE, "Statutory Reserve (Free Zone)", CATEGORY, "fail",
                                      "Entity is in a free zone but no Statutory/Legal Reserve found in Trial Balance."))
            else:
                results.append(result(RULE_RESERVE, "Statutory Reserve (Free Zone)", CATEGORY, "pass",
                                      "Statutory/Legal Reserve account found in Trial Balance."))
        else:
            results.append(result(RULE_RESERVE, "Statutory Reserve (Free Zone)", CATEGORY, "pass",
                                  "Mainland entity — statutory reserve check not applicable."))

    if selected(enabled_rule_keys, RULE_EQUITY):
        if bs is None or eq is None:
            results.append(result(RULE_EQUITY, "Equity Cross-Check (BS vs SoCE)", CATEGORY, "skip",
                                  "Balance Sheet or Equity Statement sheet missing — cannot cross-check equity."))
        else:
            bs_equity_row = first_present(find_row(bs, "total equity"), find_row(bs, "equity"))
            soce_total_row = find_last_row(eq, "balance as at")
            if soce_total_row is None and not eq.empty:
                soce_total_row = eq.iloc[-1]

            bs_equity_value = rightmost_numeric(bs_equity_row)
            soce_equity_value = rightmost_numeric(soce_total_row)

            if bs_equity_value is None or soce_equity_value is None:
                results.append(result(RULE_EQUITY, "Equity Cross-Check (BS vs SoCE)", CATEGORY, "skip",
                                      "Could not extract equity totals from Balance Sheet or Equity Statement."))
            elif abs(bs_equity_value - soce_equity_value) <= TOLERANCE:
                results.append(result(RULE_EQUITY, "Equity Cross-Check (BS vs SoCE)", CATEGORY, "pass",
                                      f"Total Equity matches: BS={round(bs_equity_value, 2)}, SoCE={round(soce_equity_value, 2)}"))
            else:
                results.append(result(RULE_EQUITY, "Equity Cross-Check (BS vs SoCE)", CATEGORY, "fail",
                                      f"Total Equity mismatch: BS={round(bs_equity_value, 2)}, SoCE={round(soce_equity_value, 2)}",
                                      {"bs_equity": round(bs_equity_value, 2), "soce_equity": round(soce_equity_value, 2)}))

    return results


def _missing_trial_balance_results(enabled_rule_keys) -> list:
    rules = []
    if selected(enabled_rule_keys, RULE_SUM_ZERO):
        rules.append(result(RULE_SUM_ZERO, "Sum of Balances = 0", CATEGORY, "skip", "Trial Balance sheet not found."))
    if selected(enabled_rule_keys, RULE_DIVIDENDS):
        rules.append(result(RULE_DIVIDENDS, "Dividends Without Share Capital", CATEGORY, "skip", "Trial Balance sheet not found."))
    if selected(enabled_rule_keys, RULE_RESERVE):
        rules.append(result(RULE_RESERVE, "Statutory Reserve (Free Zone)", CATEGORY, "skip", "Trial Balance sheet not found."))
    if selected(enabled_rule_keys, RULE_EQUITY):
        rules.append(result(RULE_EQUITY, "Equity Cross-Check (BS vs SoCE)", CATEGORY, "skip", "Trial Balance sheet not found."))
    return rules
