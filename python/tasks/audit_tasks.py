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
from audit_rule_catalog import DEFAULT_ENABLED_RULES, RULE_MAP, RULES, SECTIONS, normalize_enabled_rules

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

SECTION_CHECKERS = {
    "general_ledger": general_ledger,
    "trial_balance": trial_balance,
    "balance_sheet": balance_sheet,
    "profit_loss": profit_loss,
    "equity_statement": equity_statement,
    "cash_flow": cash_flow,
    "prepayment": prepayment,
    "sales": sales_checker,
    "sl_control": sl_control,
    "pl_control": pl_control,
    "bank_control": bank_control,
    "accruals": accruals,
    "share_capital": share_capital,
    "vat_control": vat_control,
}


@app.task(bind=True, name="audit_check")
def run_audit(self, job_id: str, payload: dict):
    upload_id = payload.get("upload_id")
    file_path = payload.get("file_path")
    original_filename = payload.get("original_filename")
    free_zone = payload.get("free_zone", "mainland")
    enabled_rules = normalize_enabled_rules(payload.get("enabled_rules"))

    logger.info("Starting audit for upload_id=%s, free_zone=%s", upload_id, free_zone)
    update_job_status(job_id, "processing")
    _update_upload_status(upload_id, "processing")

    try:
        step_states = _initial_step_states(enabled_rules)
        _write_audit_report(upload_id, [], _build_summary([], step_states, state="processing"))

        sheets = load_sheets(file_path, original_filename=original_filename)
        results = []

        for section in SECTIONS:
            section_key = section["section_key"]
            checker = SECTION_CHECKERS[section_key]

            for rule in section["rules"]:
                rule_key = rule["rule_key"]
                rule_label = rule["rule_label"]

                if not enabled_rules.get(rule_key, True):
                    results = _replace_results_for_rule(results, rule_key, [
                        _disabled_result(rule_key, rule_label, section["section_label"])
                    ])
                    _mark_step(
                        step_states,
                        rule_key,
                        status="completed",
                        outcome="disabled",
                        attempts=0,
                        message="Disabled in Settings.",
                        retryable=False
                    )
                    _write_audit_report(
                        upload_id,
                        results,
                        _build_summary(results, step_states, state="processing")
                    )
                    continue

                step_results = _execute_rule(
                    upload_id=upload_id,
                    step_states=step_states,
                    existing_results=results,
                    rule_key=rule_key,
                    rule_label=rule_label,
                    section_label=section["section_label"],
                    checker=checker,
                    sheets=sheets,
                    free_zone=free_zone
                )
                results = _replace_results_for_rule(results, rule_key, step_results)

        summary = _build_summary(results, step_states, state="completed")
        _write_audit_report(upload_id, results, summary)
        _update_upload_status(upload_id, "completed")
        update_job_status(job_id, "completed", result={"summary": summary})

        logger.info("Audit complete for upload_id=%s: %s", upload_id, summary)
        return summary

    except Exception as exc:
        logger.exception("Audit failed for upload_id=%s", upload_id)
        _write_failure_report(upload_id, str(exc), enabled_rules)
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
    enabled_rules = normalize_enabled_rules(payload.get("enabled_rules"))

    rule_definition = RULE_MAP.get(check_key)
    if rule_definition is None:
        raise ValueError(f"Unknown checker key: {check_key}")
    if not enabled_rules.get(check_key, True):
        raise ValueError(f"Rule {check_key} is disabled in Settings and cannot be retried.")

    logger.info("Retrying checker %s for upload_id=%s", check_key, upload_id)
    update_job_status(job_id, "processing")
    _update_upload_status(upload_id, "processing")

    try:
        existing_results, existing_summary = _read_audit_report(upload_id)
        step_states = _normalize_step_states(existing_summary.get("check_progress"), enabled_rules)
        sheets = load_sheets(file_path, original_filename=original_filename)

        preserved_results = [result for result in existing_results if result.get("checker_key") != check_key]
        step_results = _execute_rule(
            upload_id=upload_id,
            step_states=step_states,
            existing_results=preserved_results,
            rule_key=check_key,
            rule_label=rule_definition["rule_label"],
            section_label=rule_definition["section_label"],
            checker=SECTION_CHECKERS[rule_definition["section_key"]],
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
    enabled_rules = normalize_enabled_rules(payload.get("enabled_rules"))

    check_keys = [
        rule["rule_key"]
        for rule in RULES
        if rule["rule_key"] in requested_check_keys and enabled_rules.get(rule["rule_key"], True)
    ]
    if not check_keys:
        raise ValueError("No valid checker keys were provided for bulk retry.")

    logger.info("Bulk retrying checks %s for upload_id=%s", check_keys, upload_id)
    update_job_status(job_id, "processing")
    _update_upload_status(upload_id, "processing")

    try:
        existing_results, existing_summary = _read_audit_report(upload_id)
        step_states = _normalize_step_states(existing_summary.get("check_progress"), enabled_rules)
        sheets = load_sheets(file_path, original_filename=original_filename)

        results = [result for result in existing_results if result.get("checker_key") not in check_keys]

        for check_key in check_keys:
            rule_definition = RULE_MAP[check_key]
            step_results = _execute_rule(
                upload_id=upload_id,
                step_states=step_states,
                existing_results=results,
                rule_key=check_key,
                rule_label=rule_definition["rule_label"],
                section_label=rule_definition["section_label"],
                checker=SECTION_CHECKERS[rule_definition["section_key"]],
                sheets=sheets,
                free_zone=free_zone
            )
            results = _replace_results_for_rule(results, check_key, step_results)

        summary = _build_summary(results, step_states, state="completed")
        _write_audit_report(upload_id, results, summary)
        _update_upload_status(upload_id, "completed")
        update_job_status(job_id, "completed", result={"summary": summary})

        logger.info("Bulk retry complete for upload_id=%s, checks=%s", upload_id, check_keys)
        return summary

    except Exception as exc:
        logger.exception("Bulk retry failed for upload_id=%s, checks=%s", upload_id, check_keys)
        _update_upload_status(upload_id, "failed")
        update_job_status(job_id, "failed", error_message=str(exc))
        raise self.retry(exc=exc, countdown=10, max_retries=2)


def _execute_rule(upload_id: int, step_states: list, existing_results: list, rule_key: str, rule_label: str,
                  section_label: str, checker, sheets: dict, free_zone: str) -> list:
    started_at = time.monotonic()
    final_results = []
    final_outcome = "skip"
    final_message = "Check did not run."

    for attempt in range(1, MAX_CHECK_ATTEMPTS + 1):
        _mark_step(
            step_states,
            rule_key,
            status="processing",
            attempts=attempt,
            message=f"Running {rule_label} (attempt {attempt} of {MAX_CHECK_ATTEMPTS})",
            retryable=False
        )
        _write_audit_report(
            upload_id,
            existing_results,
            _build_summary(existing_results, step_states, state="processing", current_check=rule_label)
        )

        try:
            checker_results = checker.run(sheets, free_zone, enabled_rule_keys={rule_key})
            matching_results = [result for result in checker_results if getattr(result, "rule_key", None) == rule_key]

            if matching_results:
                final_results = _annotate_results(matching_results, rule_key, rule_label, attempt)
            elif len(checker_results) == 1:
                final_results = _annotate_results(checker_results, rule_key, rule_label, attempt)
            else:
                final_results = [_empty_result(
                    rule_key,
                    rule_label,
                    section_label,
                    attempt,
                    "Skipped because the checker returned no audit result for this rule."
                )]

            final_outcome = _step_outcome(final_results)
            final_message = _step_message(final_results)
        except Exception as exc:
            logger.exception("Checker %s raised an error for %s", checker.__name__, rule_key)
            final_results = [_system_failure_result(rule_key, rule_label, section_label, attempt, exc)]
            final_outcome = "fail"
            final_message = final_results[0]["message"]

    remaining_duration = MIN_CHECK_DURATION_SECONDS - (time.monotonic() - started_at)
    if remaining_duration > 0:
        _mark_step(
            step_states,
            rule_key,
            status="processing",
            attempts=MAX_CHECK_ATTEMPTS,
            message=f"Finalizing {rule_label}...",
            retryable=False
        )
        _write_audit_report(
            upload_id,
            existing_results,
            _build_summary(existing_results, step_states, state="processing", current_check=rule_label)
        )
        time.sleep(remaining_duration)

    _mark_step(
        step_states,
        rule_key,
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


def _annotate_results(checker_results: list, rule_key: str, rule_label: str, attempt: int) -> list:
    annotated = []
    for result in checker_results:
        result_dict = result.to_dict()
        result_dict["checker_key"] = rule_key
        result_dict["checker_label"] = rule_label
        result_dict["attempt"] = attempt
        result_dict["rule_key"] = rule_key
        annotated.append(result_dict)
    return annotated


def _system_failure_result(rule_key: str, rule_label: str, section_label: str, attempt: int, exc: Exception) -> dict:
    result = CheckResult(
        check_name=rule_label,
        category=section_label,
        status="fail",
        message=f"Checker error: {exc}",
        details={},
        rule_key=rule_key
    ).to_dict()
    result["checker_key"] = rule_key
    result["checker_label"] = rule_label
    result["attempt"] = attempt
    return result


def _empty_result(rule_key: str, rule_label: str, section_label: str, attempt: int, message: str) -> dict:
    result = CheckResult(
        check_name=rule_label,
        category=section_label,
        status="skip",
        message=message,
        details={},
        rule_key=rule_key
    ).to_dict()
    result["checker_key"] = rule_key
    result["checker_label"] = rule_label
    result["attempt"] = attempt
    return result


def _disabled_result(rule_key: str, rule_label: str, section_label: str) -> dict:
    result = CheckResult(
        check_name=rule_label,
        category=section_label,
        status="disabled",
        message="Disabled in Settings.",
        details={},
        rule_key=rule_key
    ).to_dict()
    result["checker_key"] = rule_key
    result["checker_label"] = rule_label
    result["attempt"] = 0
    return result


def _build_summary(results: list, step_states: list, state: str, current_check: str | None = None) -> dict:
    counts = {"passed": 0, "failed": 0, "warnings": 0, "skipped": 0, "disabled": 0}
    for result in results:
        if result["status"] == "pass":
            counts["passed"] += 1
        elif result["status"] == "fail":
            counts["failed"] += 1
        elif result["status"] == "warning":
            counts["warnings"] += 1
        elif result["status"] == "disabled":
            counts["disabled"] += 1
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


def _write_failure_report(upload_id: int, error_message: str, enabled_rules: dict):
    if upload_id is None:
        return

    step_states = _initial_step_states(enabled_rules)
    summary = _build_summary([], step_states, state="failed")
    summary.update({
        "total": 1,
        "passed": 0,
        "failed": 1,
        "warnings": 0,
        "skipped": 0,
        "disabled": 0,
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


def _initial_step_states(enabled_rules: dict | None) -> list:
    resolved = normalize_enabled_rules(enabled_rules or DEFAULT_ENABLED_RULES)
    return [
        {
            "key": rule["rule_key"],
            "label": rule["rule_label"],
            "section_key": rule["section_key"],
            "section_label": rule["section_label"],
            "enabled": resolved.get(rule["rule_key"], True),
            "status": "pending",
            "outcome": None,
            "attempts": 0,
            "max_attempts": MAX_CHECK_ATTEMPTS,
            "message": resolved.get(rule["rule_key"], True) and "Waiting to run." or "Disabled in Settings.",
            "retryable": False
        }
        for rule in RULES
    ]


def _normalize_step_states(existing_states, enabled_rules: dict | None) -> list:
    base_states = {state["key"]: state for state in _initial_step_states(enabled_rules)}
    if not existing_states:
        return list(base_states.values())

    for existing_state in existing_states:
        key = existing_state.get("key")
        if key in base_states:
            base_states[key].update(existing_state)
            base_states[key]["max_attempts"] = MAX_CHECK_ATTEMPTS
            base_states[key]["enabled"] = normalize_enabled_rules(enabled_rules).get(key, True)

    return [base_states[rule["rule_key"]] for rule in RULES]


def _mark_step(step_states: list, rule_key: str, status: str, outcome: str | None = None,
               attempts: int | None = None, message: str | None = None, retryable: bool | None = None):
    for step in step_states:
        if step["key"] == rule_key:
            step["status"] = status
            step["outcome"] = outcome
            if attempts is not None:
                step["attempts"] = attempts
            if message is not None:
                step["message"] = message
            if retryable is not None:
                step["retryable"] = retryable
            break


def _replace_results_for_rule(existing_results: list, rule_key: str, new_results: list) -> list:
    preserved_results = [result for result in existing_results if result.get("checker_key") != rule_key]
    preserved_results.extend(new_results)
    return preserved_results


def _step_outcome(checker_results: list) -> str:
    statuses = [result["status"] for result in checker_results]
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    if "skip" in statuses:
        return "skip"
    if "disabled" in statuses:
        return "disabled"
    if "pass" in statuses:
        return "pass"
    return "skip"


def _step_message(checker_results: list) -> str:
    preferred_order = ["fail", "warning", "skip", "disabled", "pass"]
    for status in preferred_order:
        for result in checker_results:
            if result["status"] == status:
                return result["message"]
    return "Check completed."
