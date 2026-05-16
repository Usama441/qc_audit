import json
import psycopg2
from datetime import datetime, timezone
from config import DATABASE_URL


def _connect():
    return psycopg2.connect(DATABASE_URL)


def update_job_status(job_id: str, status: str, result: dict = None, error_message: str = None):
    fields = ["status = %s", "updated_at = %s"]
    values = [status, datetime.now(timezone.utc)]

    if status == "processing":
        fields.append("started_at = %s")
        values.append(datetime.now(timezone.utc))
    elif status in ("completed", "failed"):
        fields.append("completed_at = %s")
        values.append(datetime.now(timezone.utc))

    if result is not None:
        fields.append("result = %s")
        values.append(json.dumps(result))

    if error_message is not None:
        fields.append("error_message = %s")
        values.append(error_message)

    values.append(job_id)

    sql = f"UPDATE python_jobs SET {', '.join(fields)} WHERE job_id = %s"

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, values)
