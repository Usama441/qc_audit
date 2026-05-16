import pandas as pd
from checkers import CheckResult
from checkers.loader import first_present, find_last_row, last_numeric, numeric_col, find_row, rightmost_numeric, safe_float

CATEGORY = "2. Trial Balance"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    tb = sheets.get("trial_balance")
    bs = sheets.get("balance_sheet")
    eq = sheets.get("equity_statement")

    if tb is None:
        results.append(CheckResult("Trial Balance checks", CATEGORY, "skip",
                                   "Trial Balance sheet not found."))
        return results

    debit  = numeric_col(tb, "debit")
    credit = numeric_col(tb, "credit")
    bal    = numeric_col(tb, "balance", "amount", "net")

    # 2a — Sum of balances = 0
    if debit is not None and credit is not None:
        net = debit.fillna(0).sum() - credit.fillna(0).sum()
        if abs(net) <= TOLERANCE:
            results.append(CheckResult("Sum of Balances = 0", CATEGORY, "pass",
                                       f"Debit − Credit = {round(net, 2)} ✓"))
        else:
            results.append(CheckResult("Sum of Balances = 0", CATEGORY, "fail",
                                       f"Trial balance does not balance. Difference: {round(net, 2)}",
                                       {"difference": round(net, 2)}))
    elif bal is not None:
        net = bal.fillna(0).sum()
        if abs(net) <= TOLERANCE:
            results.append(CheckResult("Sum of Balances = 0", CATEGORY, "pass",
                                       f"Net balance column sums to {round(net, 2)} ✓"))
        else:
            results.append(CheckResult("Sum of Balances = 0", CATEGORY, "fail",
                                       f"Net balance column does not sum to zero. Sum = {round(net, 2)}",
                                       {"sum": round(net, 2)}))
    else:
        results.append(CheckResult("Sum of Balances = 0", CATEGORY, "skip",
                                   "Could not identify debit/credit or balance column in Trial Balance."))

    # 2b — Dividends not issued without share capital
    div_row = find_row(tb, "dividend")
    sc_row  = first_present(find_row(tb, "share capital"), find_row(tb, "capital invested"))

    if div_row is not None:
        div_val = safe_float(rightmost_numeric(div_row), 0)
        sc_val  = safe_float(rightmost_numeric(sc_row), 0) if sc_row is not None else 0

        if sc_val == 0:
            results.append(CheckResult("Dividends Without Share Capital", CATEGORY, "fail",
                                       "Dividends found in TB but Share Capital is zero or missing.",
                                       {"dividend": div_val, "share_capital": sc_val}))
        else:
            results.append(CheckResult("Dividends Without Share Capital", CATEGORY, "pass",
                                       "Dividends present and Share Capital exists."))
    else:
        results.append(CheckResult("Dividends Without Share Capital", CATEGORY, "pass",
                                   "No dividend entries found — check not applicable."))

    # 2c — Statutory reserve in free zones
    if free_zone in ("freezone_10", "freezone_5"):
        res_row = first_present(find_row(tb, "statutory reserve"), find_row(tb, "legal reserve"))
        if res_row is None:
            results.append(CheckResult("Statutory Reserve (Free Zone)", CATEGORY, "fail",
                                       "Entity is in a free zone but no Statutory/Legal Reserve found in Trial Balance."))
        else:
            results.append(CheckResult("Statutory Reserve (Free Zone)", CATEGORY, "pass",
                                       "Statutory/Legal Reserve account found in Trial Balance."))
    else:
        results.append(CheckResult("Statutory Reserve (Free Zone)", CATEGORY, "pass",
                                   "Mainland entity — statutory reserve check not applicable."))

    # 2d — Total equity on Balance Sheet == Total equity on Equity Statement
    if bs is None or eq is None:
        results.append(CheckResult("Equity Cross-Check (BS vs SoCE)", CATEGORY, "skip",
                                   "Balance Sheet or Equity Statement sheet missing — cannot cross-check equity."))
    else:
        bs_eq_row  = first_present(find_row(bs, "total equity"), find_row(bs, "equity"))
        soce_total = find_last_row(eq, "balance as at")
        if soce_total is None and not eq.empty:
            soce_total = eq.iloc[-1]

        bs_eq_val   = last_numeric(bs_eq_row)
        soce_eq_val = rightmost_numeric(soce_total)

        if bs_eq_val is None or soce_eq_val is None:
            results.append(CheckResult("Equity Cross-Check (BS vs SoCE)", CATEGORY, "skip",
                                       "Could not extract equity totals from Balance Sheet or Equity Statement."))
        elif abs(bs_eq_val - soce_eq_val) <= TOLERANCE:
            results.append(CheckResult("Equity Cross-Check (BS vs SoCE)", CATEGORY, "pass",
                                       f"Total Equity matches: BS={round(bs_eq_val,2)}, SoCE={round(soce_eq_val,2)}"))
        else:
            results.append(CheckResult("Equity Cross-Check (BS vs SoCE)", CATEGORY, "fail",
                                       f"Total Equity mismatch: BS={round(bs_eq_val,2)}, SoCE={round(soce_eq_val,2)}",
                                       {"bs_equity": round(bs_eq_val, 2), "soce_equity": round(soce_eq_val, 2)}))

    return results


def _is_nonzero_num(val) -> bool:
    try:
        return float(val) != 0
    except (TypeError, ValueError):
        return False
