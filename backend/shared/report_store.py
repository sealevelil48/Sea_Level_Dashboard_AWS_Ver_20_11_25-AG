"""
Where generated reports live.

  AWS:     S3 bucket REPORTS_BUCKET, keys reports/<kind>/<name>.zip (+ .json manifest). Downloads are
           short-lived presigned URLs. Kept until deleted (versioned bucket).
  On-prem: folder REPORTS_DIR (default <repo>/reports_output) — the same folder the Windows
           scheduled task writes to, so the dashboard lists reports made either way.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

NAME_RE = re.compile(r"^sea_level_(monthly|yearly)_(\d{4}(?:-\d{2})?)\.zip$")
PRESIGN_SECONDS = 900


def _bucket() -> Optional[str]:
    return os.getenv("REPORTS_BUCKET") or None


def _dir() -> Path:
    d = Path(os.getenv("REPORTS_DIR") or Path(__file__).resolve().parents[2] / "reports_output")
    d.mkdir(parents=True, exist_ok=True)
    return d


def valid_name(name: str) -> Optional[str]:
    m = NAME_RE.match(name or "")
    return m.group(1) if m else None


def save(report) -> dict:
    """Store a shared.reports.Report; returns its manifest (+ size, created)."""
    body = report.zip_bytes()
    meta = {**report.manifest(), "size": len(body), "created": datetime.now(timezone.utc).isoformat()}
    if _bucket():
        import boto3
        s3 = boto3.client("s3")
        key = f"reports/{report.kind}/{report.name}"
        s3.put_object(Bucket=_bucket(), Key=key, Body=body, ContentType="application/zip",
                      ServerSideEncryption="AES256", ContentDisposition=f'attachment; filename="{report.name}"')
        s3.put_object(Bucket=_bucket(), Key=key[:-4] + ".json", Body=json.dumps(meta, ensure_ascii=False).encode(),
                      ContentType="application/json", ServerSideEncryption="AES256")
    else:
        d = _dir()
        (d / report.name).write_bytes(body)
        (d / (report.name[:-4] + ".json")).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def list_reports() -> List[dict]:
    out = []
    if _bucket():
        import boto3
        s3 = boto3.client("s3")
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=_bucket(), Prefix="reports/"):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".json"):
                    out.append(json.loads(s3.get_object(Bucket=_bucket(), Key=obj["Key"])["Body"].read()))
    else:
        for p in _dir().glob("sea_level_*.json"):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    return sorted(out, key=lambda m: (m.get("period", ""), m.get("kind", "")), reverse=True)


def download(name: str):
    """(presigned_url, None) on AWS, (None, bytes) on-prem. Raises KeyError if missing."""
    kind = valid_name(name)
    if not kind:
        raise KeyError(name)
    if _bucket():
        import boto3
        s3 = boto3.client("s3")
        key = f"reports/{kind}/{name}"
        try:
            s3.head_object(Bucket=_bucket(), Key=key)
        except Exception as exc:
            raise KeyError(name) from exc
        return s3.generate_presigned_url("get_object", Params={"Bucket": _bucket(), "Key": key},
                                         ExpiresIn=PRESIGN_SECONDS), None
    p = _dir() / name
    if not p.is_file():
        raise KeyError(name)
    return None, p.read_bytes()
