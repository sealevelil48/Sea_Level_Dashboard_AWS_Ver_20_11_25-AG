"""
Downloadable exports (architect's "S3 Bucket — Downloadable Exports").

The API generates CSV/JSON from the same corrected data the dashboard shows, writes it to the
private exports bucket and returns a short-lived presigned download URL. Objects expire via a
bucket lifecycle rule. Without EXPORTS_BUCKET (on-prem), the file is returned directly.
"""
import csv
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone

PRESIGN_SECONDS = 900


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name or "all")[:40]


def render(records, fmt: str) -> bytes:
    if fmt == "json":
        return json.dumps(records, default=str, ensure_ascii=False).encode("utf-8")
    buf = io.StringIO()
    if records:
        writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens Hebrew/UTF-8 correctly


def store(records, fmt: str, station: str, user_sub: str):
    """Returns (presigned_url, filename) when EXPORTS_BUCKET is set, else (None, filename, body)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"sealevel_{_safe(station)}_{stamp}.{fmt}"
    body = render(records, fmt)
    bucket = os.getenv("EXPORTS_BUCKET")
    if not bucket:
        return None, filename, body
    import boto3
    s3 = boto3.client("s3")
    key = f"exports/{_safe(user_sub)}/{uuid.uuid4()}/{filename}"
    s3.put_object(Bucket=bucket, Key=key, Body=body, ServerSideEncryption="AES256",
                  ContentType="application/json" if fmt == "json" else "text/csv; charset=utf-8",
                  ContentDisposition=f'attachment; filename="{filename}"')
    url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=PRESIGN_SECONDS)
    return url, filename, None
