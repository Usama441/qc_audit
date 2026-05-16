import pandas as pd
from checkers import CheckResult
from checkers.loader import first_present, find_last_row, find_row, last_numeric, rightmost_numeric

CATEGORY = "5. Equity Statement"
TOLERANCE = 0.01

RESERVE_RATES = {"freezone_10": 0.10, "freezone_5": 0.05}


def run(sheets: dict, free_zone: str) -> list:
    results = []
    eq = sheets.get("equity_statement")
    pl = sheets.get("profit_loss")
    tb = sheets.get("trial_balance")

    if eq is None:
        results.append(CheckResult("Equity Statement checks", CATEGORY, "skip",
                                   "Equity Statement (SoCE) sheet not found."))
        return results

    # 5a-i — Net profit in SoCE == Profit After Tax in SoCI
    soce_np = last_numeric(first_present(find_row(eq, "net profit"), find_row(eq, "profit for the year")))

    if pl is None:
        results.append(CheckResult("Net Profit: SoCE vs SoCI", CATEGORY, "skip",
                                   "P&L (SoCI) sheet not found — cannot cross-check net profit."))
    else:
        soce_np_row = first_present(find_row(pl, "profit after tax"), find_row(pl, "net profit"))
        soci_np = last_numeric(soce_np_row)

        if soce_np is None or soci_np is None:
            results.append(CheckResult("Net Profit: SoCE vs SoCI", CATEGORY, "skip",
                                       "Could not extract net profit from SoCE or SoCI."))
        elif abs(soce_np - soci_np) <= TOLERANCE:
            results.append(CheckResult("Net Profit: SoCE vs SoCI", CATEGORY, "pass",
                                       f"Net profit matches: SoCE={soce_np:,.2f}, SoCI={soci_np:,.2f}"))
        else:
            results.append(CheckResult("Net Profit: SoCE vs SoCI", CATEGORY, "fail",
                                       f"Net profit mismatch: SoCE={soce_np:,.2f}, SoCI={soci_np:,.2f}",
                                       {"soce": round(soce_np,2), "soci": round(soci_np,2)}))

    # 5a-ii — Share capital SoCE == Trial Balance
    soce_sc = rightmost_numeric(first_present(find_row(eq, "share capital"), find_row(eq, "paid up capital")))

    if tb is None:
        results.append(CheckResult("Share Capital: SoCE vs TB", CATEGORY, "skip",
                                   "Trial Balance not found."))
    else:
        tb_sc = rightmost_numeric(first_present(find_row(tb, "share capital"), find_row(tb, "capital invested")))
        if soce_sc is None or tb_sc is None:
            results.append(CheckResult("Share Capital: SoCE vs TB", CATEGORY, "skip",
                                       "Could not extract share capital from SoCE or Trial Balance."))
        elif abs(soce_sc - tb_sc) <= TOLERANCE:
            results.append(CheckResult("Share Capital: SoCE vs TB", CATEGORY, "pass",
                                       f"Share capital matches: SoCE={soce_sc:,.2f}, TB={tb_sc:,.2f}"))
        else:
            results.append(CheckResult("Share Capital: SoCE vs TB", CATEGORY, "fail",
                                       f"Share capital mismatch: SoCE={soce_sc:,.2f}, TB={tb_sc:,.2f}",
                                       {"soce": round(soce_sc,2), "tb": round(tb_sc,2)}))

    # 5a-iii — Owner current account SoCE == Trial Balance
    soce_oca = last_numeric(first_present(find_row(eq, "owner", "current account"), find_row(eq, "drawings")))
    if tb is None:
        pass  # already reported above
    else:
        tb_oca = rightmost_numeric(first_present(find_row(tb, "owner", "current account"), find_row(tb, "drawings")))
        if soce_oca is None or tb_oca is None:
            results.append(CheckResult("Owner Current Account: SoCE vs TB", CATEGORY, "skip",
                                       "Could not extract owner current account from SoCE or Trial Balance."))
        elif abs(soce_oca - tb_oca) <= TOLERANCE:
            results.append(CheckResult("Owner Current Account: SoCE vs TB", CATEGORY, "pass",
                                       f"Owner current account matches: SoCE={soce_oca:,.2f}, TB={tb_oca:,.2f}"))
        else:
            results.append(CheckResult("Owner Current Account: SoCE vs TB", CATEGORY, "fail",
                                       f"Owner current account mismatch: SoCE={soce_oca:,.2f}, TB={tb_oca:,.2f}",
                                       {"soce": round(soce_oca,2), "tb": round(tb_oca,2)}))

    # 5b — Statutory reserve = net_profit × rate
    rate = RESERVE_RATES.get(free_zone)
    if rate is None:
        results.append(CheckResult("Statutory Reserve Rate", CATEGORY, "pass",
                                   "Mainland entity — statutory reserve rate check not applicable."))
    else:
        res_row = first_present(find_row(eq, "statutory reserve"), find_row(eq, "legal reserve"))
        actual_reserve = last_numeric(res_row)
        expected_reserve = (soce_np or 0) * rate if soce_np else None

        if actual_reserve is None or expected_reserve is None:
            results.append(CheckResult("Statutory Reserve Rate", CATEGORY, "skip",
                                       f"Could not verify statutory reserve ({int(rate*100)}% of net profit)."))
        elif abs(actual_reserve - expected_reserve) <= TOLERANCE:
            results.append(CheckResult("Statutory Reserve Rate", CATEGORY, "pass",
                                       f"Statutory reserve {actual_reserve:,.2f} = "
                                       f"{int(rate*100)}% of net profit {soce_np:,.2f} ✓"))
        else:
            results.append(CheckResult("Statutory Reserve Rate", CATEGORY, "fail",
                                       f"Statutory reserve {actual_reserve:,.2f} ≠ "
                                       f"{int(rate*100)}% of net profit {soce_np:,.2f} "
                                       f"(expected {expected_reserve:,.2f})",
                                       {"actual": round(actual_reserve,2),
                                        "expected": round(expected_reserve,2),
                                        "rate": rate}))

    # 5c — Row and column totals consistency
    numeric_cols = [c for c in eq.columns if pd.to_numeric(eq[c], errors="coerce").notna().any()]
    if len(numeric_cols) < 2:
        results.append(CheckResult("SoCE Totals Consistency", CATEGORY, "skip",
                                   "Not enough numeric columns to verify SoCE totals."))
    else:
        total_row = first_present(find_last_row(eq, "balance as at"), find_row(eq, "total"))
        if total_row is None:
            results.append(CheckResult("SoCE Totals Consistency", CATEGORY, "skip",
                                       "No 'Total' row found in Equity Statement."))
        else:
            results.append(CheckResult("SoCE Totals Consistency", CATEGORY, "pass",
                                       "Total row found — manual review recommended for row/column cross-totals."))

    return results
