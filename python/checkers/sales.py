import pandas as pd
from checkers import CheckResult
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "8. Sales"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    sales = sheets.get("sales")
    pl    = sheets.get("profit_loss")

    if sales is None:
        results.append(CheckResult("Sales checks", CATEGORY, "skip",
                                   "Sales sheet not found."))
        return results

    # 8a — Invoice numbers are sequential
    inv_col = next((c for c in sales.columns
                    if "invoice" in str(c).lower() or "number" in str(c).lower()
                    or "no" in str(c).lower()), None)

    if inv_col is None:
        results.append(CheckResult("Invoice Sequence", CATEGORY, "skip",
                                   "No invoice number column found in Sales sheet."))
    else:
        nums = pd.to_numeric(sales[inv_col], errors="coerce").dropna().astype(int).sort_values()
        if len(nums) < 2:
            results.append(CheckResult("Invoice Sequence", CATEGORY, "skip",
                                       "Fewer than 2 numeric invoice numbers found."))
        else:
            expected = range(int(nums.iloc[0]), int(nums.iloc[-1]) + 1)
            gaps = sorted(set(expected) - set(nums))
            if gaps:
                results.append(CheckResult("Invoice Sequence", CATEGORY, "fail",
                                           f"{len(gaps)} gap(s) in invoice sequence. First gap at {gaps[0]}.",
                                           {"gaps": gaps[:20]}))
            else:
                results.append(CheckResult("Invoice Sequence", CATEGORY, "pass",
                                           f"Invoices {nums.iloc[0]}–{nums.iloc[-1]} are in sequence with no gaps."))

    # 8b — Total sales == SoCI revenue
    amt_col = next((c for c in sales.columns
                    if "amount" in str(c).lower() or "total" in str(c).lower()
                    or "value" in str(c).lower()), None)
    sales_total = pd.to_numeric(sales[amt_col], errors="coerce").sum() if amt_col is not None else None

    soci_rev_row = first_present(find_row(pl, "total revenue"), find_row(pl, "revenue")) if pl is not None else None
    soci_rev = last_numeric(soci_rev_row)

    if sales_total is None:
        results.append(CheckResult("Total Sales vs SoCI Revenue", CATEGORY, "skip",
                                   "Could not identify sales amount column."))
    elif soci_rev is None:
        results.append(CheckResult("Total Sales vs SoCI Revenue", CATEGORY, "warning",
                                   f"Sales schedule total: {sales_total:,.2f}. "
                                   "Could not locate revenue in P&L for comparison.",
                                   {"sales_total": round(sales_total,2)}))
    elif abs(sales_total - soci_rev) <= TOLERANCE:
        results.append(CheckResult("Total Sales vs SoCI Revenue", CATEGORY, "pass",
                                   f"Total sales matches SoCI revenue: {sales_total:,.2f}"))
    else:
        results.append(CheckResult("Total Sales vs SoCI Revenue", CATEGORY, "fail",
                                   f"Sales total {sales_total:,.2f} ≠ SoCI revenue {soci_rev:,.2f}",
                                   {"sales": round(sales_total,2), "soci_revenue": round(soci_rev,2)}))

    return results
