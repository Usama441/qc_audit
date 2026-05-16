import pandas as pd
from checkers import CheckResult
from checkers.loader import numeric_col, safe_float

CATEGORY = "1. General Ledger"
TOLERANCE = 1.0


def run(sheets: dict, free_zone: str) -> list:
    results = []

    gl = sheets.get("general_ledger")
    tb = sheets.get("trial_balance")

    if gl is None or tb is None:
        results.append(CheckResult(
            check_name="GL vs Trial Balance",
            category=CATEGORY,
            status="skip",
            message="General Ledger or Trial Balance sheet not found — skipping comparison.",
        ))
        return results

    # Find account code columns in both sheets
    gl_code_col = next((c for c in gl.columns if "account" in str(c).lower() or "code" in str(c).lower()), None)
    tb_code_col = next((c for c in tb.columns if "account" in str(c).lower() or "code" in str(c).lower()), None)
    gl_bal_col  = numeric_col(gl, "closing", "balance", "amount")
    tb_bal_col  = numeric_col(tb, "balance", "amount", "closing")

    if any(v is None for v in [gl_code_col, tb_code_col, gl_bal_col, tb_bal_col]):
        results.append(CheckResult(
            check_name="GL vs Trial Balance",
            category=CATEGORY,
            status="skip",
            message="Could not identify account code or balance columns in GL/TB — skipping.",
        ))
        return results

    gl_totals = gl.groupby(gl[gl_code_col].astype(str))[gl.columns[gl.columns.get_loc(gl_code_col) + 1:]].apply(
        lambda x: pd.to_numeric(x.iloc[:, -1], errors="coerce").sum()
    )

    tb_map = {
        str(row[tb_code_col]): safe_float(tb_bal_col.iloc[i])
        for i, (_, row) in enumerate(tb.iterrows())
        if pd.notna(row[tb_code_col])
    }

    mismatches = []
    for code, gl_val in gl.groupby(gl[gl_code_col].astype(str)).apply(
        lambda g: pd.to_numeric(g.iloc[:, -1], errors="coerce").sum()
    ).items():
        tb_val = tb_map.get(str(code))
        if tb_val is None:
            continue
        if abs(abs(gl_val) - abs(tb_val)) > TOLERANCE:
            mismatches.append({"account": code, "gl": round(gl_val, 2), "tb": round(tb_val, 2)})

    if mismatches:
        results.append(CheckResult(
            check_name="GL vs Trial Balance",
            category=CATEGORY,
            status="fail",
            message=f"{len(mismatches)} account(s) have different balances between GL and Trial Balance.",
            details={"mismatches": mismatches[:20]},
        ))
    else:
        results.append(CheckResult(
            check_name="GL vs Trial Balance",
            category=CATEGORY,
            status="pass",
            message="All GL closing balances match Trial Balance.",
        ))

    return results
