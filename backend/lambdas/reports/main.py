"""
Reports job (AWS): monthly and yearly reports for the MAPI website.

Invoked by
  * EventBridge schedules — {"kind": "monthly"} on the 1st (previous month), {"kind": "yearly"} on 2 Jan
    (previous year)
  * the API (POST /api/reports/generate) — {"kind", "year", "month", "requested_by"}
Writes the zip + manifest to REPORTS_BUCKET and e-mails a notice through REPORTS_TOPIC_ARN.
"""
import json
import logging
import os
from datetime import date

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    # DB_URI is built from DB_SECRET_ARN by lambda_entry (entry point lambda_entry.reports_handler)
    from shared import report_store, reports
    from shared.database import engine
    kind = (event or {}).get("kind", "monthly")
    if kind == "monthly":
        year, month = (int(event["year"]), int(event["month"])) if event.get("year") else reports.previous_month()
        rep = reports.monthly_report(engine, year, month)
    elif kind == "yearly":
        year = int(event["year"]) if event.get("year") else date.today().year - 1
        rep = reports.yearly_report(engine, year)
    else:
        raise ValueError(f"unknown report kind {kind!r}")
    meta = report_store.save(rep)
    logger.info(json.dumps({"report": meta}, ensure_ascii=False))
    topic = os.getenv("REPORTS_TOPIC_ARN")
    if topic:
        import boto3
        notes = "\n".join(f"  - {n}" for n in rep.notes) or "  (none)"
        boto3.client("sns").publish(
            TopicArn=topic, Subject=f"Sea level {kind} report {rep.period} ready",
            Message=f"{rep.name} is ready in the dashboard (Reports tab).\n\nFiles: {len(rep.files)}\nNotes:\n{notes}\n")
    return meta
