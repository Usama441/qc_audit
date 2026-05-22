from celery import Celery
from config import REDIS_URL

app = Celery(
    "office_tools",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.qc_tasks", "tasks.audit_tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)
