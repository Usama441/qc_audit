from checkers import result, selected
from checkers.loader import first_present, find_row, last_numeric

CATEGORY = "6. Cash Flow"
TOLERANCE = 0.01

RULE_PROFIT = "cash_flow.profit_before_tax_cf_vs_soci"
RULE_DEPRECIATION = "cash_flow.depreciation_added_back"
RULE_BAD_DEBT = "cash_flow.bad_debt_added_back"
RULE_OPENING = "cash_flow.opening_cash_vs_prior_year_bs"
RULE_CLOSING = "cash_flow.closing_cash_vs_balance_sheet"


def run(sheets: dict, free_zone: str, enabled_rule_keys=None) -> list:
    results = []
    cash_flow = sheets.get("cash_flow")
    profit_loss = sheets.get("profit_loss")
    balance_sheet = sheets.get("balance_sheet")

    if cash_flow is None:
        return _missing_cash_flow_results(enabled_rule_keys)

    if selected(enabled_rule_keys, RULE_PROFIT):
        cash_flow_pbt = last_numeric(first_present(find_row(cash_flow, "profit before tax"), find_row(cash_flow, "net profit")))
        soci_pbt = last_numeric(first_present(find_row(profit_loss, "profit before tax"), find_row(profit_loss, "net profit")) if profit_loss is not None else None)

        if cash_flow_pbt is None:
            results.append(result(RULE_PROFIT, "Profit Before Tax (CF vs SoCI)", CATEGORY, "skip",
                                  "Could not find profit before tax in Cash Flow statement."))
        elif soci_pbt is None:
            results.append(result(RULE_PROFIT, "Profit Before Tax (CF vs SoCI)", CATEGORY, "skip",
                                  "Could not find profit before tax in P&L (SoCI)."))
        elif abs(cash_flow_pbt - soci_pbt) <= TOLERANCE:
            results.append(result(RULE_PROFIT, "Profit Before Tax (CF vs SoCI)", CATEGORY, "pass",
                                  f"Profit before tax matches: CF={cash_flow_pbt:,.2f}, SoCI={soci_pbt:,.2f}"))
        else:
            results.append(result(RULE_PROFIT, "Profit Before Tax (CF vs SoCI)", CATEGORY, "fail",
                                  f"Profit before tax mismatch: CF={cash_flow_pbt:,.2f}, SoCI={soci_pbt:,.2f}",
                                  {"cf": round(cash_flow_pbt, 2), "soci": round(soci_pbt, 2)}))

    if selected(enabled_rule_keys, RULE_DEPRECIATION):
        depreciation_row = first_present(find_row(cash_flow, "depreciation"), find_row(cash_flow, "amortisation"), find_row(cash_flow, "amortization"))
        depreciation_value = last_numeric(depreciation_row)

        if depreciation_value is None:
            results.append(result(RULE_DEPRECIATION, "Depreciation Added Back", CATEGORY, "skip",
                                  "No depreciation line found in Cash Flow."))
        elif depreciation_value > 0:
            results.append(result(RULE_DEPRECIATION, "Depreciation Added Back", CATEGORY, "pass",
                                  f"Depreciation {depreciation_value:,.2f} is added back (positive)."))
        else:
            results.append(result(RULE_DEPRECIATION, "Depreciation Added Back", CATEGORY, "fail",
                                  f"Depreciation {depreciation_value:,.2f} is negative — should be added back as positive.",
                                  {"depreciation": round(depreciation_value, 2)}))

    if selected(enabled_rule_keys, RULE_BAD_DEBT):
        bad_debt_row = first_present(find_row(cash_flow, "bad debt"), find_row(cash_flow, "impairment"), find_row(cash_flow, "provision"))
        bad_debt_value = last_numeric(bad_debt_row)

        if bad_debt_value is None:
            results.append(result(RULE_BAD_DEBT, "Bad Debt Added Back", CATEGORY, "skip",
                                  "No bad debt / provision line found in Cash Flow."))
        elif bad_debt_value > 0:
            results.append(result(RULE_BAD_DEBT, "Bad Debt Added Back", CATEGORY, "pass",
                                  f"Bad debt provision {bad_debt_value:,.2f} is added back (positive)."))
        else:
            results.append(result(RULE_BAD_DEBT, "Bad Debt Added Back", CATEGORY, "warning",
                                  f"Bad debt / provision {bad_debt_value:,.2f} is not positive — confirm it is added back.",
                                  {"value": round(bad_debt_value, 2)}))

    if selected(enabled_rule_keys, RULE_OPENING):
        opening_row = first_present(find_row(cash_flow, "beginning"), find_row(cash_flow, "opening"), find_row(cash_flow, "start of year"))
        opening_cash = last_numeric(opening_row)

        if opening_cash is None:
            results.append(result(RULE_OPENING, "Opening Cash vs Prior Year BS", CATEGORY, "skip",
                                  "Could not identify opening cash figure in Cash Flow statement."))
        else:
            results.append(result(RULE_OPENING, "Opening Cash vs Prior Year BS", CATEGORY, "warning",
                                  f"Opening cash per CF: {opening_cash:,.2f}. Verify this matches prior year Balance Sheet cash & bank balance.",
                                  {"opening_cash": round(opening_cash, 2)}))

    if selected(enabled_rule_keys, RULE_CLOSING):
        closing_row = first_present(find_row(cash_flow, "end of"), find_row(cash_flow, "closing"), find_row(cash_flow, "end of period"))
        closing_cash = last_numeric(closing_row)
        balance_sheet_cash = last_numeric(find_row(balance_sheet, "cash", "bank") if balance_sheet is not None else None)

        if closing_cash is None:
            results.append(result(RULE_CLOSING, "Closing Cash vs Balance Sheet", CATEGORY, "skip",
                                  "Could not identify closing cash figure in Cash Flow statement."))
        elif balance_sheet_cash is None:
            results.append(result(RULE_CLOSING, "Closing Cash vs Balance Sheet", CATEGORY, "skip",
                                  "Could not identify cash & bank on Balance Sheet."))
        elif abs(closing_cash - balance_sheet_cash) <= TOLERANCE:
            results.append(result(RULE_CLOSING, "Closing Cash vs Balance Sheet", CATEGORY, "pass",
                                  f"Closing cash matches: CF={closing_cash:,.2f}, BS={balance_sheet_cash:,.2f}"))
        else:
            results.append(result(RULE_CLOSING, "Closing Cash vs Balance Sheet", CATEGORY, "fail",
                                  f"Closing cash mismatch: CF={closing_cash:,.2f}, BS={balance_sheet_cash:,.2f}",
                                  {"cf_close": round(closing_cash, 2), "bs_cash": round(balance_sheet_cash, 2)}))

    return results


def _missing_cash_flow_results(enabled_rule_keys) -> list:
    results = []
    if selected(enabled_rule_keys, RULE_PROFIT):
        results.append(result(RULE_PROFIT, "Profit Before Tax (CF vs SoCI)", CATEGORY, "skip", "Cash Flow sheet not found."))
    if selected(enabled_rule_keys, RULE_DEPRECIATION):
        results.append(result(RULE_DEPRECIATION, "Depreciation Added Back", CATEGORY, "skip", "Cash Flow sheet not found."))
    if selected(enabled_rule_keys, RULE_BAD_DEBT):
        results.append(result(RULE_BAD_DEBT, "Bad Debt Added Back", CATEGORY, "skip", "Cash Flow sheet not found."))
    if selected(enabled_rule_keys, RULE_OPENING):
        results.append(result(RULE_OPENING, "Opening Cash vs Prior Year BS", CATEGORY, "skip", "Cash Flow sheet not found."))
    if selected(enabled_rule_keys, RULE_CLOSING):
        results.append(result(RULE_CLOSING, "Closing Cash vs Balance Sheet", CATEGORY, "skip", "Cash Flow sheet not found."))
    return results
