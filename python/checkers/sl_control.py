import pandas as pd
from checkers import CheckResult
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "9. SL Control (Receivables)"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    sl = sheets.get("sl_control")
    bs = sheets.get("balance_sheet")

    if sl is None:
        results.append(CheckResult("SL Control checks", CATEGORY, "skip",
                                   "SL Control (AR) sheet not found."))
        return results

    numeric_cols = [c for c in sl.columns if pd.to_numeric(sl[c], errors="coerce").notna().any()]

    # 9a — No negative figures in aged receivable
    negatives = {}
    for col in numeric_cols:
        series = pd.to_numeric(sl[col], errors="coerce")
        neg = series[series < -TOLERANCE]
        if not neg.empty:
            negatives[str(col)] = {"count": len(neg), "min": round(float(neg.min()), 2)}

    if negatives:
        results.append(CheckResult("No Negative AR Balances", CATEGORY, "fail",
                                   f"Negative figures found in {len(negatives)} column(s) of aged receivable.",
                                   {"columns": negatives}))
    else:
        results.append(CheckResult("No Negative AR Balances", CATEGORY, "pass",
                                   "No negative figures in aged receivable report."))

    # 9b — Total receivable == Balance Sheet AR
    total_row = first_present(find_row(sl, "total"), find_row(sl, "aged receivable"))
    sl_total  = last_numeric(total_row)

    bs_ar = None
    if bs is not None:
        ar_row = first_present(find_row(bs, "accounts receivable"), find_row(bs, "trade receivable"),
                               find_row(bs, "debtor"))
        bs_ar = last_numeric(ar_row)

    if sl_total is None:
        results.append(CheckResult("Total AR vs Balance Sheet", CATEGORY, "skip",
                                   "Could not identify total from SL Control report."))
    elif bs_ar is None:
        results.append(CheckResult("Total AR vs Balance Sheet", CATEGORY, "warning",
                                   f"SL Control total: {sl_total:,.2f}. "
                                   "Accounts Receivable not found on Balance Sheet.",
                                   {"sl_total": round(sl_total,2)}))
    elif abs(sl_total - bs_ar) <= TOLERANCE:
        results.append(CheckResult("Total AR vs Balance Sheet", CATEGORY, "pass",
                                   f"Total receivable matches BS: {sl_total:,.2f}"))
    else:
        results.append(CheckResult("Total AR vs Balance Sheet", CATEGORY, "fail",
                                   f"AR mismatch: SL Control={sl_total:,.2f}, BS={bs_ar:,.2f}",
                                   {"sl_control": round(sl_total,2), "balance_sheet": round(bs_ar,2)}))

    return results
