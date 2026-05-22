"""
Redis queue consumer — reads jobs pushed by Rails (PythonWorkerClient)
from the office_tools:jobs list and dispatches them to Celery tasks.

Run with: python worker.py
"""
import json
import logging
import signal

import redis as redis_lib

from config import PROCESSING_QUEUE_KEY, REDIS_URL, QUEUE_KEY
from tasks.qc_tasks import qc_analysis, data_processing
from tasks.audit_tasks import retry_audit_check, retry_audit_checks, run_audit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TASK_MAP = {
    "qc_analysis":    qc_analysis,
    "data_processing": data_processing,
    "audit_check":    run_audit,
    "retry_audit_check": retry_audit_check,
    "retry_audit_checks": retry_audit_checks,
}

running = True


def handle_signal(sig, frame):
    global running
    logger.info("Shutting down worker…")
    running = False


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def main():
    r = redis_lib.from_url(REDIS_URL)
    _recover_inflight_jobs(r)
    logger.info("Worker started. Listening on '%s'…", QUEUE_KEY)

    while running:
        raw = r.brpoplpush(QUEUE_KEY, PROCESSING_QUEUE_KEY, timeout=2)
        if raw is None:
            continue

        try:
            job = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Invalid JSON on queue: %s", raw)
            _ack_job(r, raw)
            continue

        job_id    = job.get("id", "unknown")
        task_name = job.get("task")
        payload   = job.get("payload", {})

        task_fn = TASK_MAP.get(task_name)
        if task_fn is None:
            logger.warning("Unknown task '%s' for job %s — skipping", task_name, job_id)
            _ack_job(r, raw)
            continue

        logger.info("Dispatching job %s → %s", job_id, task_name)
        try:
            task_fn.delay(job_id, payload)
            _ack_job(r, raw)
        except Exception:
            logger.exception("Dispatch failed for job %s — requeueing", job_id)
            _requeue_job(r, raw)


def _ack_job(redis_client, raw):
    redis_client.lrem(PROCESSING_QUEUE_KEY, 1, raw)


def _requeue_job(redis_client, raw):
    pipe = redis_client.pipeline()
    pipe.lpush(QUEUE_KEY, raw)
    pipe.lrem(PROCESSING_QUEUE_KEY, 1, raw)
    pipe.execute()


def _recover_inflight_jobs(redis_client):
    recovered = 0

    while redis_client.rpoplpush(PROCESSING_QUEUE_KEY, QUEUE_KEY) is not None:
        recovered += 1

    if recovered > 0:
        logger.warning("Recovered %s in-flight job(s) back to '%s'", recovered, QUEUE_KEY)


if __name__ == "__main__":
    main()
