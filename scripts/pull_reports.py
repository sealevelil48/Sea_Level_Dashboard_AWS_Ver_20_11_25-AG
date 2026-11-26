#!/usr/bin/env python
"""
Download the website reports made on AWS (monthly on the 1st, yearly on 2 January) to a folder,
extracted in the website layout (MM/<Station>/…, שנתי/…). Only reports not yet downloaded are fetched.

  python scripts/pull_reports.py --env prod --dest "D:\\MAPI website\\sea level"
  python scripts/pull_reports.py --env prod --dest ./site --period 2025-01      # one report

Needs AWS credentials with s3:GetObject/ListBucket on sealevel-reports-<env>-<account>
(e.g. `aws sso login`). Region il-central-1.
"""
import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

import boto3


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default="prod", choices=["dev", "stg", "prod"])
    ap.add_argument("--dest", required=True, type=Path)
    ap.add_argument("--period", help="only this period, e.g. 2025-01 or 2025")
    ap.add_argument("--region", default="il-central-1")
    a = ap.parse_args(argv)

    account = boto3.client("sts", region_name=a.region).get_caller_identity()["Account"]
    bucket = f"sealevel-reports-{a.env}-{account}"
    s3 = boto3.client("s3", region_name=a.region)
    a.dest.mkdir(parents=True, exist_ok=True)
    seen_file = a.dest / ".pulled_reports.json"
    seen = json.loads(seen_file.read_text()) if seen_file.exists() else {}

    pulled = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="reports/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".zip"):
                continue
            if a.period and f"_{a.period}.zip" not in key:
                continue
            if seen.get(key) == obj["ETag"]:
                continue
            data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            zipfile.ZipFile(io.BytesIO(data)).extractall(a.dest)
            seen[key] = obj["ETag"]
            pulled += 1
            print(f"✔ {key.rsplit('/', 1)[-1]} → {a.dest}")
    seen_file.write_text(json.dumps(seen, indent=1))
    print(f"{pulled} report(s) downloaded" if pulled else "Nothing new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
