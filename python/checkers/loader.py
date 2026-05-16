import logging
import os
import zipfile
from io import BytesIO
import pandas as pd
from openpyxl import load_workbook

from config import MAX_WORKBOOK_SIZE_BYTES

logger = logging.getLogger(__name__)

SHEET_ALIASES = {
    "general_ledger":   ["General Ledger", "GL", "general ledger"],
    "trial_balance":    ["Trial Balance", "TB", "trial balance"],
    "balance_sheet":    ["Balance Sheet", "BS", "balance sheet", "SoFP", "Statement of Financial Position"],
    "profit_loss":      ["Profit & Loss", "P&L", "Income Statement", "SoCI", "profit and loss", "Statement of Profit and Loss"],
    "equity_statement": ["SoCE", "Equity Statement", "Statement of Changes in Equity"],
    "cash_flow":        ["Cash Flow", "CFS", "Cash Flow Statement", "cash flow", "SoCF", "Statement of Cash flows"],
    "prepayment":       ["Prepayment", "Prepayments"],
    "sales":            ["Sales", "Sale"],
    "sl_control":       ["SL Control", "AR Control", "Accounts Receivable"],
    "pl_control":       ["PL Control", "AP Control", "Accounts Payable"],
    "bank_control":     ["Bank Control", "Bank"],
    "accruals":         ["Accruals", "Accrual"],
    "share_capital":    ["Share Capital"],
    "vat_control":      ["VAT Control", "VAT"],
}

HEADER_ROW_KEYWORDS = {
    "general_ledger": ["code", "account", "debit", "credit", "balance"],
    "trial_balance": ["code", "account", "debit", "credit", "balance"],
    "equity_statement": ["share capital", "retained earnings", "statutory reserves", "total"],
    "share_capital": ["owner name", "shares", "value per share", "total share value"],
    "sales": ["date", "number", "partner", "total"],
    "sl_control": ["date", "total", "1-30", "31-60"],
    "pl_control": ["date", "total", "1-30", "31-60"],
    "bank_control": ["date", "label", "amount"],
}


def load_sheets(file_path: str, original_filename: str | None = None) -> dict:
    """
    Load all sheets from an Excel workbook.
    Returns a dict keyed by our canonical names (e.g. "trial_balance").
    Sheets that are not found are absent from the dict.
    """
    _validate_workbook(file_path, original_filename=original_filename)
    with open(file_path, "rb") as workbook_file:
        workbook_bytes = workbook_file.read()
    workbook = load_workbook(BytesIO(workbook_bytes), data_only=True, read_only=True)
    available = {_normalize_text(s): s for s in workbook.sheetnames}

    sheets = {}
    for key, aliases in SHEET_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalize_text(alias)
            if normalized_alias in available:
                real_name = available[normalized_alias]
                sheets[key] = _worksheet_to_dataframe(workbook[real_name], key)
                logger.info("Loaded sheet '%s' → %s", real_name, key)
                break
        else:
            logger.warning("Sheet not found for key '%s' (tried: %s)", key, aliases)

    return sheets


def _validate_workbook(file_path: str, original_filename: str | None = None):
    filename_for_validation = original_filename or file_path
    extension = os.path.splitext(filename_for_validation)[1].lower()
    if extension and extension != ".xlsx":
        raise ValueError("Only .xlsx workbooks are supported")

    file_size = os.path.getsize(file_path)
    if file_size > MAX_WORKBOOK_SIZE_BYTES:
        raise ValueError(f"Workbook exceeds the {MAX_WORKBOOK_SIZE_BYTES // (1024 * 1024)} MB size limit")

    if not zipfile.is_zipfile(file_path):
        raise ValueError("Uploaded workbook is not a valid .xlsx file")


def _worksheet_to_dataframe(worksheet, sheet_key: str) -> pd.DataFrame:
    rows = list(worksheet.iter_rows(values_only=True))
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).dropna(axis=1, how="all").dropna(how="all").reset_index(drop=True)
    if df.empty:
        return df

    header_row_index = _detect_header_row(df, sheet_key)
    if header_row_index is None:
        df.columns = [f"column_{index}" for index in range(df.shape[1])]
        return df.reset_index(drop=True)

    headers = _dedupe_headers(df.iloc[header_row_index].tolist())
    data = df.iloc[header_row_index + 1 :].reset_index(drop=True)
    data.columns = headers
    return data.dropna(how="all").reset_index(drop=True)


def _detect_header_row(df: pd.DataFrame, sheet_key: str) -> int | None:
    keywords = HEADER_ROW_KEYWORDS.get(sheet_key)
    if not keywords:
        return None

    best_index = None
    best_score = 0
    search_limit = min(len(df), 15)

    for index in range(search_limit):
        row_values = [_normalize_text(value) for value in df.iloc[index].tolist() if value is not None]
        if not row_values:
            continue

        score = sum(1 for keyword in keywords if any(keyword in value for value in row_values))
        if score > best_score:
            best_score = score
            best_index = index

    return best_index if best_score >= 2 else None


def _dedupe_headers(headers: list) -> list[str]:
    seen = {}
    normalized_headers = []

    for index, header in enumerate(headers):
        base = str(header).strip() if header not in (None, "") else f"column_{index}"
        count = seen.get(base, 0) + 1
        seen[base] = count
        normalized_headers.append(base if count == 1 else f"{base}_{count}")

    return normalized_headers


def _normalize_text(value) -> str:
    return " ".join(str(value).strip().lower().split())


def numeric_col(df: pd.DataFrame, *hints: str) -> pd.Series | None:
    """
    Find the first numeric column whose name contains one of the hint strings
    (case-insensitive). Returns None if not found.
    """
    best_series = None
    best_score = (-1, -1, -1)

    for hint in hints:
        for index, col in enumerate(df.columns):
            if hint.lower() in str(col).lower():
                s = pd.to_numeric(df.iloc[:, index], errors="coerce")
                nonzero_count = int((s.fillna(0).abs() > 0).sum())
                nonnull_count = int(s.notna().sum())
                score = (nonzero_count, nonnull_count, index)
                if nonnull_count > 0 and score > best_score:
                    best_series = s
                    best_score = score

    return best_series


def find_row(df: pd.DataFrame, *keywords: str) -> pd.Series | None:
    """Return the first row where any cell contains all keywords (case-insensitive)."""
    kw_lower = [k.lower() for k in keywords]
    for _, row in df.iterrows():
        text = " ".join(str(v).lower() for v in row.values)
        if all(k in text for k in kw_lower):
            return row
    return None


def find_last_row(df: pd.DataFrame, *keywords: str) -> pd.Series | None:
    """Return the last row where any cell contains all keywords (case-insensitive)."""
    kw_lower = [k.lower() for k in keywords]
    for _, row in df.iloc[::-1].iterrows():
        text = " ".join(str(v).lower() for v in row.values)
        if all(k in text for k in kw_lower):
            return row
    return None


def safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def last_numeric(row) -> float | None:
    if row is None:
        return None

    best_number = None
    best_score = (-1, -1)
    zero_found = False

    for index, value in enumerate(list(row.values)):
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue

        if pd.isna(number):
            continue

        if number == 0:
            zero_found = True
            continue

        score = (abs(number), index)
        if score > best_score:
            best_number = number
            best_score = score

    if best_number is not None:
        return best_number
    if zero_found:
        return 0.0
    return None


def rightmost_numeric(row) -> float | None:
    if row is None:
        return None

    zero_found = False

    for value in reversed(list(row.values)):
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue

        if pd.isna(number):
            continue

        if number == 0:
            zero_found = True
            continue

        return number

    if zero_found:
        return 0.0
    return None
