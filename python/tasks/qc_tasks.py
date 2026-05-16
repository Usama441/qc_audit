import logging
from celery_app import app
from db import update_job_status

logger = logging.getLogger(__name__)


@app.task(bind=True, name="qc_analysis")
def qc_analysis(self, job_id: str, payload: dict):
    """
    Run quality control analysis on the provided data.
    payload keys: audit_id, data (list of records to analyse)
    """
    update_job_status(job_id, "processing")
    try:
        import pandas as pd

        df = pd.DataFrame(payload.get("data", []))

        result = {
            "total_records": len(df),
            "columns":       list(df.columns),
            "null_counts":   df.isnull().sum().to_dict(),
            "summary":       df.describe(include="all").fillna("").to_dict(),
        }

        update_job_status(job_id, "completed", result=result)
        return result

    except Exception as exc:
        logger.exception("qc_analysis failed for job %s", job_id)
        update_job_status(job_id, "failed", error_message=str(exc))
        raise self.retry(exc=exc, countdown=5, max_retries=3)


@app.task(bind=True, name="data_processing")
def data_processing(self, job_id: str, payload: dict):
    """
    General-purpose data processing task.
    payload keys: operation, data
    """
    update_job_status(job_id, "processing")
    try:
        import pandas as pd

        df     = pd.DataFrame(payload.get("data", []))
        result = {"processed_rows": len(df)}

        update_job_status(job_id, "completed", result=result)
        return result

    except Exception as exc:
        logger.exception("data_processing failed for job %s", job_id)
        update_job_status(job_id, "failed", error_message=str(exc))
        raise self.retry(exc=exc, countdown=5, max_retries=3)
