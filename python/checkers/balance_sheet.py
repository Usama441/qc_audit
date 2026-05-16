import pandas as pd
from checkers import CheckResult
from checkers.loader import find_row, safe_float

CATEGORY = "3. Balance Sheet"
TOLERANCE = 0.01


def run(sheets: dict, free_zone: str) -> list:
    results = []
    bs = sheets.get("balance_sheet")

    if bs is None:
        results.append(CheckResult("Balance Sheet checks", CATEGORY, "skip",
                                   "Balance Sheet sheet not found."))
        return results

    # 3a — Assets = Equity + Liabilities
    total_assets      = _find_total(bs, "total assets", "assets")
    total_liabilities = _find_total(bs, "total liabilities", "liabilities")
    total_equity      = _find_total(bs, "total equity", "equity")

    if total_assets is None or total_liabilities is None or total_equity is None:
        results.append(CheckResult("Assets = Equity + Liabilities", CATEGORY, "skip",
                                   "Could not locate totals for Assets, Liabilities, or Equity on Balance Sheet."))
    else:
        rhs = total_liabilities + total_equity
        if abs(total_assets - rhs) <= TOLERANCE:
            results.append(CheckResult("Assets = Equity + Liabilities", CATEGORY, "pass",
                                       f"Balance sheet balances: Assets={round(total_assets,2)}, "
                                       f"Liabilities+Equity={round(rhs,2)}"))
        else:
            results.append(CheckResult("Assets = Equity + Liabilities", CATEGORY, "fail",
                                       f"Balance sheet does not balance. "
                                       f"Assets={round(total_assets,2)}, "
                                       f"Liabilities+Equity={round(rhs,2)}, "
                                       f"Difference={round(total_assets - rhs, 2)}",
                                       {"assets": round(total_assets,2),
                                        "liabilities": round(total_liabilities,2),
                                        "equity": round(total_equity,2),
                                        "difference": round(total_assets - rhs, 2)}))

    # 3b — Account code check (1xxxxxxx assets, 2xxxxxxx liabilities)
    code_col = next((c for c in bs.columns
                     if "code" in str(c).lower() or "account" in str(c).lower()), None)
    type_col = next((c for c in bs.columns
                     if "type" in str(c).lower() or "category" in str(c).lower()), None)

    if code_col is None:
        results.append(CheckResult("Account Code Links", CATEGORY, "skip",
                                   "No account code column found on Balance Sheet."))
    else:
        wrong = []
        for _, row in bs.iterrows():
            code = str(row[code_col]).strip()
            if not code or code in ("nan", "None"):
                continue
            label = str(row.get(type_col, "")).lower() if type_col else ""

            if "asset" in label and not code.startswith("1"):
                wrong.append({"code": code, "issue": "Asset account not starting with 1"})
            elif "liabilit" in label and not code.startswith("2"):
                wrong.append({"code": code, "issue": "Liability account not starting with 2"})

        if wrong:
            results.append(CheckResult("Account Code Links", CATEGORY, "fail",
                                       f"{len(wrong)} account(s) have incorrect code prefix for their type.",
                                       {"issues": wrong[:20]}))
        else:
            results.append(CheckResult("Account Code Links", CATEGORY, "pass",
                                       "All account codes match expected prefixes (1=Assets, 2=Liabilities)."))

    return results


def _find_total(df: pd.DataFrame, *keywords) -> float | None:
    row = find_row(df, *keywords)
    if row is None:
        return None
    for v in reversed(list(row.values)):
        try:
            f = float(v)
            if f != 0:
                return f
        except (TypeError, ValueError):
            continue
    return None
