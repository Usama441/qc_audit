import pandas as pd
from checkers import result, selected
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "8. Sales"
TOLERANCE = 0.01

RULE_SEQUENCE = "sales.invoice_sequence"
RULE_TOTAL = "sales.total_sales_vs_soci_revenue"


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    results = []
    sales = sheets.get("sales")
    profit_loss = sheets.get("profit_loss")

    if sales is None:
        return _missing_sales_results(enabled_rule_keys)

    if selected(enabled_rule_keys, RULE_SEQUENCE):
        invoice_col = next(
            (
                c for c in sales.columns
                if "invoice" in str(c).lower() or "number" in str(c).lower() or "no" in str(c).lower()
            ),
            None
        )

        if invoice_col is None:
            results.append(result(RULE_SEQUENCE, "Invoice Sequence", CATEGORY, "skip",
                                  "No invoice number column found in Sales sheet."))
        else:
            numbers = pd.to_numeric(sales[invoice_col], errors="coerce").dropna().astype(int).sort_values()
            if len(numbers) < 2:
                results.append(result(RULE_SEQUENCE, "Invoice Sequence", CATEGORY, "skip",
                                      "Fewer than 2 numeric invoice numbers found."))
            else:
                expected = range(int(numbers.iloc[0]), int(numbers.iloc[-1]) + 1)
                gaps = sorted(set(expected) - set(numbers))
                if gaps:
                    results.append(result(RULE_SEQUENCE, "Invoice Sequence", CATEGORY, "fail",
                                          f"{len(gaps)} gap(s) in invoice sequence. First gap at {gaps[0]}.",
                                          {"gaps": gaps[:20]}))
                else:
                    results.append(result(RULE_SEQUENCE, "Invoice Sequence", CATEGORY, "pass",
                                          f"Invoices {numbers.iloc[0]}–{numbers.iloc[-1]} are in sequence with no gaps."))

    if selected(enabled_rule_keys, RULE_TOTAL):
        amount_col = next(
            (
                c for c in sales.columns
                if "amount" in str(c).lower() or "total" in str(c).lower() or "value" in str(c).lower()
            ),
            None
        )
        sales_total = pd.to_numeric(sales[amount_col], errors="coerce").sum() if amount_col is not None else None
        soci_revenue_row = first_present(find_row(profit_loss, "total revenue"), find_row(profit_loss, "revenue")) if profit_loss is not None else None
        soci_revenue = last_numeric(soci_revenue_row)

        if sales_total is None:
            results.append(result(RULE_TOTAL, "Total Sales vs SoCI Revenue", CATEGORY, "skip",
                                  "Could not identify sales amount column."))
        elif soci_revenue is None:
            results.append(result(RULE_TOTAL, "Total Sales vs SoCI Revenue", CATEGORY, "warning",
                                  f"Sales schedule total: {sales_total:,.2f}. Could not locate revenue in P&L for comparison.",
                                  {"sales_total": round(sales_total, 2)}))
        elif abs(sales_total - soci_revenue) <= TOLERANCE:
            results.append(result(RULE_TOTAL, "Total Sales vs SoCI Revenue", CATEGORY, "pass",
                                  f"Total sales matches SoCI revenue: {sales_total:,.2f}"))
        else:
            results.append(result(RULE_TOTAL, "Total Sales vs SoCI Revenue", CATEGORY, "fail",
                                  f"Sales total {sales_total:,.2f} ≠ SoCI revenue {soci_revenue:,.2f}",
                                  {"sales": round(sales_total, 2), "soci_revenue": round(soci_revenue, 2)}))

    return results


def _missing_sales_results(enabled_rule_keys) -> list:
    results = []
    if selected(enabled_rule_keys, RULE_SEQUENCE):
        results.append(result(RULE_SEQUENCE, "Invoice Sequence", CATEGORY, "skip", "Sales sheet not found."))
    if selected(enabled_rule_keys, RULE_TOTAL):
        results.append(result(RULE_TOTAL, "Total Sales vs SoCI Revenue", CATEGORY, "skip", "Sales sheet not found."))
    return results
