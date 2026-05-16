import pandas as pd
from checkers import CheckResult
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "4. Profit & Loss"
TOLERANCE = 0.01
SBR_THRESHOLD = 3_000_000
CT_THRESHOLD  = 375_000

NON_DEDUCTIBLE_KEYWORDS = ["entertainment", "fines", "penalties", "fine and penalty",
                            "penalty", "entertainment expense"]


def run(sheets: dict, free_zone: str) -> list:
    results = []
    pl = sheets.get("profit_loss")

    if pl is None:
        results.append(CheckResult("P&L checks", CATEGORY, "skip",
                                   "Profit & Loss sheet not found."))
        return results

    revenue_row = first_present(find_row(pl, "total revenue"), find_row(pl, "revenue"), find_row(pl, "sales"))
    profit_row  = first_present(find_row(pl, "profit after tax"), find_row(pl, "net profit"),
                                find_row(pl, "profit for the year"))

    revenue = last_numeric(revenue_row)
    profit  = last_numeric(profit_row)

    # 4a — Revenue < 3,000,000 (SBR warning)
    if revenue is None:
        results.append(CheckResult("Revenue < 3,000,000 (SBR)", CATEGORY, "skip",
                                   "Could not identify revenue figure."))
    elif revenue < SBR_THRESHOLD:
        results.append(CheckResult("Revenue < 3,000,000 (SBR)", CATEGORY, "warning",
                                   f"Revenue is {revenue:,.2f} — below SBR threshold of 3,000,000. "
                                   "Small Business Relief may apply.",
                                   {"revenue": round(revenue, 2)}))
    else:
        results.append(CheckResult("Revenue < 3,000,000 (SBR)", CATEGORY, "pass",
                                   f"Revenue {revenue:,.2f} is above the SBR threshold."))

    # 4b — Profit > 375,000 (corporate tax warning)
    if profit is None:
        results.append(CheckResult("Profit > 375,000 (Corporate Tax)", CATEGORY, "skip",
                                   "Could not identify net profit figure."))
    elif profit > CT_THRESHOLD:
        results.append(CheckResult("Profit > 375,000 (Corporate Tax)", CATEGORY, "warning",
                                   f"Net profit {profit:,.2f} exceeds AED 375,000 — "
                                   "corporate tax at 9% applies.",
                                   {"net_profit": round(profit, 2)}))
    else:
        results.append(CheckResult("Profit > 375,000 (Corporate Tax)", CATEGORY, "pass",
                                   f"Net profit {profit:,.2f} is within the zero-rate threshold."))

    # 4c — Account codes 4xxxxxxx (revenue) and 5xxxxxxx (expenses) only
    code_col = next((c for c in pl.columns
                     if "code" in str(c).lower() or "account" in str(c).lower()), None)

    if code_col is None:
        results.append(CheckResult("Account Code Links (4x/5x)", CATEGORY, "skip",
                                   "No account code column found on P&L."))
    else:
        wrong = []
        for _, row in pl.iterrows():
            code = str(row[code_col]).strip()
            if not code or code in ("nan", "None"):
                continue
            if not (code.startswith("4") or code.startswith("5")):
                wrong.append(code)

        if wrong:
            results.append(CheckResult("Account Code Links (4x/5x)", CATEGORY, "fail",
                                       f"{len(wrong)} account code(s) on P&L do not start with 4 or 5.",
                                       {"invalid_codes": wrong[:20]}))
        else:
            results.append(CheckResult("Account Code Links (4x/5x)", CATEGORY, "pass",
                                       "All P&L account codes correctly start with 4 (revenue) or 5 (expense)."))

    # 4d — Non-deductible expenses (entertainment, fines, penalties)
    label_col = next((c for c in pl.columns
                      if "name" in str(c).lower() or "description" in str(c).lower()
                      or "account" in str(c).lower()), pl.columns[0])

    found_non_deductible = []
    for _, row in pl.iterrows():
        label = str(row.get(label_col, "")).lower()
        for kw in NON_DEDUCTIBLE_KEYWORDS:
            if kw in label:
                found_non_deductible.append({"account": str(row.get(label_col)), "keyword": kw})
                break

    if found_non_deductible:
        results.append(CheckResult("Non-Deductible Expenses", CATEGORY, "warning",
                                   f"{len(found_non_deductible)} potential non-deductible expense(s) found "
                                   "(entertainment, fines, penalties). Review for corporate tax add-back.",
                                   {"items": found_non_deductible}))
    else:
        results.append(CheckResult("Non-Deductible Expenses", CATEGORY, "pass",
                                   "No entertainment, fines, or penalties detected on P&L."))

    return results
