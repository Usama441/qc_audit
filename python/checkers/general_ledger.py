import pandas as pd
from checkers import result, selected
from checkers.loader import numeric_col, safe_float

CATEGORY = "1. General Ledger"
RULE_GL_VS_TB = "general_ledger.gl_vs_trial_balance"
TOLERANCE = 1.0


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    if not selected(enabled_rule_keys, RULE_GL_VS_TB):
        return []

    gl = sheets.get("general_ledger")
    tb = sheets.get("trial_balance")

    if gl is None or tb is None:
        return [result(
            RULE_GL_VS_TB,
            "GL vs Trial Balance",
            CATEGORY,
            "skip",
            "General Ledger or Trial Balance sheet not found — skipping comparison."
        )]

    gl_code_col = next((c for c in gl.columns if "account" in str(c).lower() or "code" in str(c).lower()), None)
    tb_code_col = next((c for c in tb.columns if "account" in str(c).lower() or "code" in str(c).lower()), None)
    gl_bal_col = numeric_col(gl, "closing", "balance", "amount")
    tb_bal_col = numeric_col(tb, "balance", "amount", "closing")

    if any(v is None for v in [gl_code_col, tb_code_col, gl_bal_col, tb_bal_col]):
        return [result(
            RULE_GL_VS_TB,
            "GL vs Trial Balance",
            CATEGORY,
            "skip",
            "Could not identify account code or balance columns in GL/TB — skipping."
        )]

    tb_map = {
        str(row[tb_code_col]): safe_float(tb_bal_col.iloc[i])
        for i, (_, row) in enumerate(tb.iterrows())
        if pd.notna(row[tb_code_col])
    }

    mismatches = []
    for code, gl_val in gl.groupby(gl[gl_code_col].astype(str)).apply(
        lambda group: pd.to_numeric(group.iloc[:, -1], errors="coerce").sum()
    ).items():
        tb_val = tb_map.get(str(code))
        if tb_val is None:
            continue
        if abs(abs(gl_val) - abs(tb_val)) > TOLERANCE:
            mismatches.append({"account": code, "gl": round(gl_val, 2), "tb": round(tb_val, 2)})

    if mismatches:
        return [result(
            RULE_GL_VS_TB,
            "GL vs Trial Balance",
            CATEGORY,
            "fail",
            f"{len(mismatches)} account(s) have different balances between GL and Trial Balance.",
            {"mismatches": mismatches[:20]}
        )]

    return [result(
        RULE_GL_VS_TB,
        "GL vs Trial Balance",
        CATEGORY,
        "pass",
        "All GL closing balances match Trial Balance."
    )]
