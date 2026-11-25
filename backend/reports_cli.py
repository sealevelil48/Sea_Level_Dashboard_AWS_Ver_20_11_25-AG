#!/usr/bin/env python
"""
Generate the MAPI website reports from the command line — for the on-prem server's scheduled task.

  python reports_cli.py monthly                       # previous month
  python reports_cli.py monthly --year 2025 --month 1
  python reports_cli.py yearly                        # previous year
  python reports_cli.py yearly --year 2025 --out D:\\SeaLevel\\website --unzip

Reads DB_URI from backend/.env. Writes sea_level_<kind>_<period>.zip (+ .json) to REPORTS_DIR (default
<repo>/reports_output), where the dashboard's Reports tab lists them too. --out also copies the files
into a folder (e.g. the website upload share); --unzip extracts them there in the website's folder layout.
"""
import argparse
import io
import sys
import zipfile
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["monthly", "yearly"])
    ap.add_argument("--year", type=int)
    ap.add_argument("--month", type=int)
    ap.add_argument("--out", type=Path, help="also copy the report to this folder")
    ap.add_argument("--unzip", action="store_true", help="extract into --out instead of copying the zip")
    a = ap.parse_args(argv)

    from shared import report_store, reports
    from shared.database import engine
    if engine is None:
        print("✖ no database (DB_URI)", file=sys.stderr)
        return 2
    if a.kind == "monthly":
        year, month = (a.year, a.month) if a.year and a.month else reports.previous_month()
        rep = reports.monthly_report(engine, year, month)
    else:
        rep = reports.yearly_report(engine, a.year or date.today().year - 1)
    meta = report_store.save(rep)
    print(f"✔ {rep.name}: {len(rep.files)} files")
    for n in rep.notes:
        print(f"  - {n}")
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        data = rep.zip_bytes()
        if a.unzip:
            zipfile.ZipFile(io.BytesIO(data)).extractall(a.out)
            print(f"  extracted to {a.out}")
        else:
            (a.out / rep.name).write_bytes(data)
            print(f"  copied to {a.out / rep.name}")
    return 0 if meta else 1


if __name__ == "__main__":
    sys.exit(main())
