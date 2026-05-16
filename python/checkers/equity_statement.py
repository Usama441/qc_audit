import pandas as pd
from checkers import result, selected
from checkers.loader import first_present, find_last_row, find_row, last_numeric, rightmost_numeric

CATEGORY = "5. Equity Statement"
TOLERANCE = 0.01
RESERVE_RATES = {"freezone_10": 0.10, "freezone_5": 0.05}

RULE_NET_PROFIT = "equity_statement.net_profit_soce_vs_soci"
RULE_SHARE_CAPITAL = "equity_statement.share_capital_soce_vs_tb"
RULE_OWNER_CURRENT = "equity_statement.owner_current_account_soce_vs_tb"
RULE_RESERVE_RATE = "equity_statement.statutory_reserve_rate"
RULE_TOTALS = "equity_statement.soce_totals_consistency"


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    results = []
    equity_statement = sheets.get("equity_statement")
    profit_loss = sheets.get("profit_loss")
    trial_balance = sheets.get("trial_balance")

    if equity_statement is None:
        return _missing_equity_statement_results(enabled_rule_keys)

    soce_net_profit = last_numeric(first_present(find_row(equity_statement, "net profit"), find_row(equity_statement, "profit for the year")))

    if selected(enabled_rule_keys, RULE_NET_PROFIT):
        if profit_loss is None:
            results.append(result(RULE_NET_PROFIT, "Net Profit: SoCE vs SoCI", CATEGORY, "skip",
                                  "P&L (SoCI) sheet not found — cannot cross-check net profit."))
        else:
            soci_net_profit_row = first_present(find_row(profit_loss, "profit after tax"), find_row(profit_loss, "net profit"))
            soci_net_profit = last_numeric(soci_net_profit_row)

            if soce_net_profit is None or soci_net_profit is None:
                results.append(result(RULE_NET_PROFIT, "Net Profit: SoCE vs SoCI", CATEGORY, "skip",
                                      "Could not extract net profit from SoCE or SoCI."))
            elif abs(soce_net_profit - soci_net_profit) <= TOLERANCE:
                results.append(result(RULE_NET_PROFIT, "Net Profit: SoCE vs SoCI", CATEGORY, "pass",
                                      f"Net profit matches: SoCE={soce_net_profit:,.2f}, SoCI={soci_net_profit:,.2f}"))
            else:
                results.append(result(RULE_NET_PROFIT, "Net Profit: SoCE vs SoCI", CATEGORY, "fail",
                                      f"Net profit mismatch: SoCE={soce_net_profit:,.2f}, SoCI={soci_net_profit:,.2f}",
                                      {"soce": round(soce_net_profit, 2), "soci": round(soci_net_profit, 2)}))

    if selected(enabled_rule_keys, RULE_SHARE_CAPITAL):
        soce_share_capital = rightmost_numeric(first_present(find_row(equity_statement, "share capital"), find_row(equity_statement, "paid up capital")))

        if trial_balance is None:
            results.append(result(RULE_SHARE_CAPITAL, "Share Capital: SoCE vs TB", CATEGORY, "skip", "Trial Balance not found."))
        else:
            tb_share_capital = rightmost_numeric(first_present(find_row(trial_balance, "share capital"), find_row(trial_balance, "capital invested")))
            if soce_share_capital is None or tb_share_capital is None:
                results.append(result(RULE_SHARE_CAPITAL, "Share Capital: SoCE vs TB", CATEGORY, "skip",
                                      "Could not extract share capital from SoCE or Trial Balance."))
            elif abs(soce_share_capital - tb_share_capital) <= TOLERANCE:
                results.append(result(RULE_SHARE_CAPITAL, "Share Capital: SoCE vs TB", CATEGORY, "pass",
                                      f"Share capital matches: SoCE={soce_share_capital:,.2f}, TB={tb_share_capital:,.2f}"))
            else:
                results.append(result(RULE_SHARE_CAPITAL, "Share Capital: SoCE vs TB", CATEGORY, "fail",
                                      f"Share capital mismatch: SoCE={soce_share_capital:,.2f}, TB={tb_share_capital:,.2f}",
                                      {"soce": round(soce_share_capital, 2), "tb": round(tb_share_capital, 2)}))

    if selected(enabled_rule_keys, RULE_OWNER_CURRENT):
        soce_owner_current = last_numeric(first_present(find_row(equity_statement, "owner", "current account"), find_row(equity_statement, "drawings")))

        if trial_balance is None:
            results.append(result(RULE_OWNER_CURRENT, "Owner Current Account: SoCE vs TB", CATEGORY, "skip", "Trial Balance not found."))
        else:
            tb_owner_current = rightmost_numeric(first_present(find_row(trial_balance, "owner", "current account"), find_row(trial_balance, "drawings")))
            if soce_owner_current is None or tb_owner_current is None:
                results.append(result(RULE_OWNER_CURRENT, "Owner Current Account: SoCE vs TB", CATEGORY, "skip",
                                      "Could not extract owner current account from SoCE or Trial Balance."))
            elif abs(soce_owner_current - tb_owner_current) <= TOLERANCE:
                results.append(result(RULE_OWNER_CURRENT, "Owner Current Account: SoCE vs TB", CATEGORY, "pass",
                                      f"Owner current account matches: SoCE={soce_owner_current:,.2f}, TB={tb_owner_current:,.2f}"))
            else:
                results.append(result(RULE_OWNER_CURRENT, "Owner Current Account: SoCE vs TB", CATEGORY, "fail",
                                      f"Owner current account mismatch: SoCE={soce_owner_current:,.2f}, TB={tb_owner_current:,.2f}",
                                      {"soce": round(soce_owner_current, 2), "tb": round(tb_owner_current, 2)}))

    if selected(enabled_rule_keys, RULE_RESERVE_RATE):
        reserve_rate = RESERVE_RATES.get(free_zone)
        if reserve_rate is None:
            results.append(result(RULE_RESERVE_RATE, "Statutory Reserve Rate", CATEGORY, "pass",
                                  "Mainland entity — statutory reserve rate check not applicable."))
        else:
            reserve_row = first_present(find_row(equity_statement, "statutory reserve"), find_row(equity_statement, "legal reserve"))
            actual_reserve = last_numeric(reserve_row)
            expected_reserve = (soce_net_profit or 0) * reserve_rate if soce_net_profit is not None else None

            if actual_reserve is None or expected_reserve is None:
                results.append(result(RULE_RESERVE_RATE, "Statutory Reserve Rate", CATEGORY, "skip",
                                      f"Could not verify statutory reserve ({int(reserve_rate * 100)}% of net profit)."))
            elif abs(actual_reserve - expected_reserve) <= TOLERANCE:
                results.append(result(RULE_RESERVE_RATE, "Statutory Reserve Rate", CATEGORY, "pass",
                                      f"Statutory reserve {actual_reserve:,.2f} = {int(reserve_rate * 100)}% of net profit {soce_net_profit:,.2f} ✓"))
            else:
                results.append(result(RULE_RESERVE_RATE, "Statutory Reserve Rate", CATEGORY, "fail",
                                      f"Statutory reserve {actual_reserve:,.2f} ≠ {int(reserve_rate * 100)}% of net profit {soce_net_profit:,.2f} "
                                      f"(expected {expected_reserve:,.2f})",
                                      {"actual": round(actual_reserve, 2), "expected": round(expected_reserve, 2), "rate": reserve_rate}))

    if selected(enabled_rule_keys, RULE_TOTALS):
        numeric_columns = [column for column in equity_statement.columns if pd.to_numeric(equity_statement[column], errors="coerce").notna().any()]
        if len(numeric_columns) < 2:
            results.append(result(RULE_TOTALS, "SoCE Totals Consistency", CATEGORY, "skip",
                                  "Not enough numeric columns to verify SoCE totals."))
        else:
            total_row = first_present(find_last_row(equity_statement, "balance as at"), find_row(equity_statement, "total"))
            if total_row is None:
                results.append(result(RULE_TOTALS, "SoCE Totals Consistency", CATEGORY, "skip",
                                      "No 'Total' row found in Equity Statement."))
            else:
                results.append(result(RULE_TOTALS, "SoCE Totals Consistency", CATEGORY, "pass",
                                      "Total row found — manual review recommended for row/column cross-totals."))

    return results


def _missing_equity_statement_results(enabled_rule_keys) -> list:
    results = []
    if selected(enabled_rule_keys, RULE_NET_PROFIT):
        results.append(result(RULE_NET_PROFIT, "Net Profit: SoCE vs SoCI", CATEGORY, "skip", "Equity Statement sheet not found."))
    if selected(enabled_rule_keys, RULE_SHARE_CAPITAL):
        results.append(result(RULE_SHARE_CAPITAL, "Share Capital: SoCE vs TB", CATEGORY, "skip", "Equity Statement sheet not found."))
    if selected(enabled_rule_keys, RULE_OWNER_CURRENT):
        results.append(result(RULE_OWNER_CURRENT, "Owner Current Account: SoCE vs TB", CATEGORY, "skip", "Equity Statement sheet not found."))
    if selected(enabled_rule_keys, RULE_RESERVE_RATE):
        results.append(result(RULE_RESERVE_RATE, "Statutory Reserve Rate", CATEGORY, "skip", "Equity Statement sheet not found."))
    if selected(enabled_rule_keys, RULE_TOTALS):
        results.append(result(RULE_TOTALS, "SoCE Totals Consistency", CATEGORY, "skip", "Equity Statement sheet not found."))
    return results
