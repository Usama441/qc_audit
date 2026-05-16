import json
import logging
import psycopg2
import time
from datetime import datetime, timezone

from celery_app import app
from config import DATABASE_URL
from db import update_job_status
from checkers.loader import load_sheets
from checkers import CheckResult

import checkers.general_ledger   as general_ledger
import checkers.trial_balance    as trial_balance
import checkers.balance_sheet    as balance_sheet
import checkers.profit_loss      as profit_loss
import checkers.equity_statement as equity_statement
import checkers.cash_flow        as cash_flow
import checkers.prepayment       as prepayment
import checkers.sales            as sales_checker
import checkers.sl_control       as sl_control
import checkers.pl_control       as pl_control
import checkers.bank_control     as bank_control
import checkers.accruals         as accruals
import checkers.share_capital    as share_capital
import checkers.vat_control      as vat_control

logger = logging.getLogger(__name__)

MAX_CHECK_ATTEMPTS = 2
MIN_CHECK_DURATION_SECONDS = 2.0

CHECKER_DEFINITIONS = [
    ("general_ledger", "General Ledger vs Trial Balance", general_ledger),
    ("trial_balance", "Trial Balance", trial_balance),
    ("balance_sheet", "Balance Sheet", balance_sheet),
    ("profit_loss", "Profit & Loss", profit_loss),
    ("equity_statement", "Equity Statement", equity_statement),
    ("cash_flow", "Cash Flow", cash_flow),
    ("prepayment", "Prepayment", prepayment),
    ("sales", "Sales", sales_checker),
    ("sl_control", "SL Control", sl_control),
    ("pl_control", "PL Control", pl_control),
    ("bank_control", "Bank Control", bank_control),
    ("accruals", "Accruals", accruals),
    ("share_capital", "Share Capital", share_capital),
    ("vat_control", "VAT Control", vat_control),
]

CHECKER_MAP = {
    step_key: {"label": step_label, "checker": checker}
    for step_key, step_label, checker in CHECKER_DEFINITIONS
}


@app.task(bind=True, name="audit_check")
def run_audit(self, job_id: str, payload: dict):
    upload_id = payload.get("upload_id")
    file_path = payload.get("file_path")
    original_filename = payload.get("original_filename")
    free_zone = payload.get("free_zone", "mainland")

    logger.info("Starting audit for upload_id=%s, free_zone=%s", upload_id, free_zone)
    update_job_status(job_id, "processing")
    _update_upload_status(upload_id, "processing")

    try:
        step_states = _initial_step_states()
        _write_audit_report(upload_id, [], _build_summary([], step_states, state="processing"))

        sheets = load_sheets(file_path, original_filename=original_filename)
        results = []

        for step_key, step_label, checker in CHECKER_DEFINITIONS:
            step_results = _execute_checker(
                upload_id=upload_id,
                step_states=step_states,
                existing_results=results,
                step_key=step_key,
                step_label=step_label,
                checker=checker,
                sheets=sheets,
                free_zone=free_zone
            )
            results = [result for result in results if result.get("checker_key") != step_key]
            results.extend(step_results)

        summary = _build_summary(results, step_states, state="completed")
        _write_audit_report(upload_id, results, summary)
        _update_upload_status(upload_id, "completed")
        update_job_status(job_id, "completed", result={"summary": summary})

        logger.info("Audit complete for upload_id=%s: %s", upload_id, summary)
        return summary

    except Exception as exc:
        logger.exception("Audit failed for upload_id=%s", upload_id)
        _write_failure_report(upload_id, str(exc))
        _update_upload_status(upload_id, "failed")
        update_job_status(job_id, "failed", error_message=str(exc))
        raise self.retry(exc=exc, countdown=10, max_retries=2)


@app.task(bind=True, name="retry_audit_check")
def retry_audit_check(self, job_id: str, payload: dict):
    upload_id = payload.get("upload_id")
    file_path = payload.get("file_path")
    original_filename = payload.get("original_filename")
    free_zone = payload.get("free_zone", "mainland")
    check_key = payload.get("check_key")

    checker_definition = CHECKER_MAP.get(check_key)
    if checker_definition is None:
        raise ValueError(f"Unknown checker key: {check_key}")

    logger.info("Retrying checker %s for upload_id=%s", check_key, upload_id)
    update_job_status(job_id, "processing")
    _update_upload_status(upload_id, "processing")

    try:
        existing_results, existing_summary = _read_audit_report(upload_id)
        step_states = _normalize_step_states(existing_summary.get("check_progress"))
        sheets = load_sheets(file_path, original_filename=original_filename)

        preserved_results = [result for result in existing_results if result.get("checker_key") != check_key]
        step_results = _execute_checker(
            upload_id=upload_id,
            step_states=step_states,
            existing_results=preserved_results,
            step_key=check_key,
            step_label=checker_definition["label"],
            checker=checker_definition["checker"],
            sheets=sheets,
            free_zone=free_zone
        )

        merged_results = preserved_results + step_results
        summary = _build_summary(merged_results, step_states, state="completed")
        _write_audit_report(upload_id, merged_results, summary)
        _update_upload_status(upload_id, "completed")
        update_job_status(job_id, "completed", result={"summary": summary})

        logger.info("Retry complete for upload_id=%s, check=%s", upload_id, check_key)
        return summary

    except Exception as exc:
        logger.exception("Retry failed for upload_id=%s, check=%s", upload_id, check_key)
        _update_upload_status(upload_id, "failed")
        update_job_status(job_id, "failed", error_message=str(exc))
        raise self.retry(exc=exc, countdown=10, max_retries=2)


@app.task(bind=True, name="retry_audit_checks")
def retry_audit_checks(self, job_id: str, payload: dict):
    upload_id = payload.get("upload_id")
    file_path = payload.get("file_path")
    original_filename = payload.get("original_filename")
    free_zone = payload.get("free_zone", "mainland")
    requested_check_keys = payload.get("check_keys") or []

    check_keys = [check_key for check_key in requested_check_keys if check_key in CHECKER_MAP]
    if not check_keys:
        raise ValueError("No valid checker keys were provided for bulk retry.")

    logger.info("Bulk retrying checks %s for upload_id=%s", check_keys, upload_id)
    update_job_status(job_id, "processing")
    _update_upload_status(upload_id, "processing")

    try:
        existing_results, existing_summary = _read_audit_report(upload_id)
        step_states = _normalize_step_states(existing_summary.get("check_progress"))
        sheets = load_sheets(file_path, original_filename=original_filename)

        merged_results = _retry_selected_checks(
            upload_id=upload_id,
            step_states=step_states,
            existing_results=existing_results,
            sheets=sheets,
            free_zone=free_zone,
            check_keys=check_keys
        )

        summary = _build_summary(merged_results, step_states, state="completed")
        _write_audit_report(upload_id, merged_results, summary)
        _update_upload_status(upload_id, "completed")
        update_job_status(job_id, "completed", result={"summary": summary})

        logger.info("Bulk retry complete for upload_id=%s, checks=%s", upload_id, check_keys)
        return summary

    except Exception as exc:
        logger.exception("Bulk retry failed for upload_id=%s, checks=%s", upload_id, check_keys)
        _update_upload_status(upload_id, "failed")
        update_job_status(job_id, "failed", error_message=str(exc))
        raise self.retry(exc=exc, countdown=10, max_retries=2)


def _execute_checker(upload_id: int, step_states: list, existing_results: list, step_key: str, step_label: str,
                     checker, sheets: dict, free_zone: str) -> list:
    started_at = time.monotonic()
    final_results = []
    final_outcome = "skip"
    final_message = "Check did not run."

    for attempt in range(1, MAX_CHECK_ATTEMPTS + 1):
        _mark_step(
            step_states,
            step_key,
            status="processing",
            attempts=attempt,
            message=f"Running {step_label} (attempt {attempt} of {MAX_CHECK_ATTEMPTS})",
            retryable=False
        )
        _write_audit_report(
            upload_id,
            existing_results,
            _build_summary(existing_results, step_states, state="processing", current_check=step_label)
        )

        try:
            checker_results = checker.run(sheets, free_zone)
            if checker_results:
                final_results = _annotate_results(checker_results, step_key, step_label, attempt)
            else:
                final_results = [_empty_result(
                    step_key,
                    step_label,
                    attempt,
                    "Skipped because the checker returned no audit results for this workbook."
                )]
            final_outcome = _step_outcome(final_results)
            final_message = _step_message(final_results)
        except Exception as exc:
            logger.exception("Checker %s raised an error", checker.__name__)
            final_results = [_system_failure_result(step_key, step_label, attempt, exc)]
            final_outcome = "fail"
            final_message = final_results[0]["message"]

    remaining_duration = MIN_CHECK_DURATION_SECONDS - (time.monotonic() - started_at)
    if remaining_duration > 0:
        _mark_step(
            step_states,
            step_key,
            status="processing",
            attempts=MAX_CHECK_ATTEMPTS,
            message=f"Finalizing {step_label}...",
            retryable=False
        )
        _write_audit_report(
            upload_id,
            existing_results,
            _build_summary(existing_results, step_states, state="processing", current_check=step_label)
        )
        time.sleep(remaining_duration)

    _mark_step(
        step_states,
        step_key,
        status="completed",
        outcome=final_outcome,
        attempts=MAX_CHECK_ATTEMPTS,
        message=final_message,
        retryable=final_outcome in ("fail", "skip")
    )
    _write_audit_report(
        upload_id,
        existing_results + final_results,
        _build_summary(existing_results + final_results, step_states, state="processing")
    )
    return final_results


def _retry_selected_checks(upload_id: int, step_states: list, existing_results: list, sheets: dict,
                           free_zone: str, check_keys: list) -> list:
    results = [result for result in existing_results if result.get("checker_key") not in check_keys]

    for check_key in check_keys:
        checker_definition = CHECKER_MAP[check_key]
        step_results = _execute_checker(
            upload_id=upload_id,
            step_states=step_states,
            existing_results=results,
            step_key=check_key,
            step_label=checker_definition["label"],
            checker=checker_definition["checker"],
            sheets=sheets,
            free_zone=free_zone
        )
        results = [result for result in results if result.get("checker_key") != check_key]
        results.extend(step_results)

    return results


def _annotate_results(checker_results: list, step_key: str, step_label: str, attempt: int) -> list:
    annotated = []
    for result in checker_results:
        result_dict = result.to_dict()
        result_dict["checker_key"] = step_key
        result_dict["checker_label"] = step_label
        result_dict["attempt"] = attempt
        annotated.append(result_dict)
    return annotated


def _system_failure_result(step_key: str, step_label: str, attempt: int, exc: Exception) -> dict:
    result = CheckResult(
        check_name=step_label,
        category="System",
        status="fail",
        message=f"Checker error: {exc}",
        details={}
    ).to_dict()
    result["checker_key"] = step_key
    result["checker_label"] = step_label
    result["attempt"] = attempt
    return result


def _empty_result(step_key: str, step_label: str, attempt: int, message: str) -> dict:
    result = CheckResult(
        check_name=step_label,
        category=step_label,
        status="skip",
        message=message,
        details={}
    ).to_dict()
    result["checker_key"] = step_key
    result["checker_label"] = step_label
    result["attempt"] = attempt
    return result


def _build_summary(results: list, step_states: list, state: str, current_check: str | None = None) -> dict:
    counts = {"passed": 0, "failed": 0, "warnings": 0, "skipped": 0}
    for result in results:
        if result["status"] == "pass":
            counts["passed"] += 1
        elif result["status"] == "fail":
            counts["failed"] += 1
        elif result["status"] == "warning":
            counts["warnings"] += 1
        else:
            counts["skipped"] += 1

    counts["total"] = len(results)
    counts["state"] = state
    counts["current_check"] = current_check
    counts["checks_total"] = len(step_states)
    counts["checks_completed"] = sum(1 for step in step_states if step["status"] == "completed")
    counts["check_progress"] = step_states
    return counts


def _write_audit_report(upload_id: int, results: list, summary: dict):
    now = datetime.now(timezone.utc)
    sql = """
        INSERT INTO audit_reports (audit_upload_id, results, summary, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (audit_upload_id) DO UPDATE
          SET results = EXCLUDED.results,
              summary = EXCLUDED.summary,
              updated_at = EXCLUDED.updated_at
    """
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(sql, (upload_id, json.dumps(results), json.dumps(summary), now, now))


def _read_audit_report(upload_id: int) -> tuple[list, dict]:
    sql = "SELECT results, summary FROM audit_reports WHERE audit_upload_id = %s"
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(sql, (upload_id,))
        row = cur.fetchone()

    if row is None:
        return [], {}

    results, summary = row
    return _normalize_json(results, []), _normalize_json(summary, {})


def _normalize_json(value, default):
    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def _write_failure_report(upload_id: int, error_message: str):
    if upload_id is None:
        return

    step_states = _initial_step_states()
    summary = _build_summary([], step_states, state="failed")
    summary.update({
        "total": 1,
        "passed": 0,
        "failed": 1,
        "warnings": 0,
        "skipped": 0,
        "current_check": None
    })
    results = [CheckResult(
        check_name="Audit Processing",
        category="System",
        status="fail",
        message=error_message,
        details={}
    ).to_dict()]
    _write_audit_report(upload_id, results, summary)


def _update_upload_status(upload_id: int, status: str):
    if upload_id is None:
        return

    now = datetime.now(timezone.utc)
    sql = "UPDATE audit_uploads SET status = %s, updated_at = %s WHERE id = %s"
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(sql, (status, now, upload_id))


def _initial_step_states() -> list:
    return [
        {
            "key": step_key,
            "label": step_label,
            "status": "pending",
            "outcome": None,
            "attempts": 0,
            "max_attempts": MAX_CHECK_ATTEMPTS,
            "message": "Waiting to run.",
            "retryable": False
        }
        for step_key, step_label, _checker in CHECKER_DEFINITIONS
    ]


def _normalize_step_states(existing_states) -> list:
    base_states = {state["key"]: state for state in _initial_step_states()}
    if not existing_states:
        return list(base_states.values())

    for existing_state in existing_states:
        key = existing_state.get("key")
        if key in base_states:
            base_states[key].update(existing_state)
            base_states[key]["max_attempts"] = MAX_CHECK_ATTEMPTS

    return [base_states[step_key] for step_key, _step_label, _checker in CHECKER_DEFINITIONS]


def _mark_step(step_states: list, step_key: str, status: str, outcome: str | None = None,
               attempts: int | None = None, message: str | None = None, retryable: bool | None = None):
    for step in step_states:
        if step["key"] == step_key:
            step["status"] = status
            step["outcome"] = outcome
            if attempts is not None:
                step["attempts"] = attempts
            if message is not None:
                step["message"] = message
            if retryable is not None:
                step["retryable"] = retryable
            break


def _step_outcome(checker_results: list) -> str:
    statuses = [result["status"] for result in checker_results]
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    if "pass" in statuses:
        return "pass"
    return "skip"


def _step_message(checker_results: list) -> str:
    preferred_order = ["fail", "warning", "skip", "pass"]
    for status in preferred_order:
        for result in checker_results:
            if result["status"] == status:
                return result["message"]
    return "Check completed."
