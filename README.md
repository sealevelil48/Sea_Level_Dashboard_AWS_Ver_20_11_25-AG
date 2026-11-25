# Sea Level Dashboard — Israel Mapping Center (MAPI)

Monitoring, quality control and analysis of sea level at six Israeli coastal stations
(Acre, Haifa, Yafo, Ashdod, Ashkelon, Eilat): live and historical data, IMS forecasts and alerts,
Kalman/ARIMA predictions, Southern Baseline anomaly rules, and an audited calibration editor.

| | |
|---|---|
| Frontend | React 18 (CRA), Chart.js, Leaflet / GovMap — `frontend/` |
| API | FastAPI, one app for AWS Lambda and on-prem — `backend/app.py` |
| Database | PostgreSQL (`Monitors_info2`, `Locations`, `SeaTides`) + calibration layer — `backend/migrations/` |
| AWS | SAM template per the architecture of 12.08.2025 — `infra/`, `scripts/deploy.sh` |
| Auth | Google sign-in through Amazon Cognito; calibration for admins only |

## Repository layout

```
backend/
  app.py                    API routes (auth, data, export, calibration)
  lambda_entry.py           AWS Lambda entry points (Mangum)
  local_server_optimized.py on-prem launcher (uvicorn, serves frontend/build)
  lambdas/                  handlers: data, live, predictions, analytics, IMS, calibration, sync, migrate, Cognito
  shared/                   database, auth, calibration math, Kalman filter, Southern Baseline rules, exports
  migrations/               SQL migrations (calibration layer, least-privilege roles, indexes)
  tests/                    pytest against a real PostgreSQL
frontend/src/
  components/Dashboard/     dashboard, chart, filters, calibration editor (graph + table)
  hooks/                    useCalibration, useChartJsConfig, useFilters, …
  auth/                     Cognito PKCE sign-in
infra/                      template.yaml (main stack), cloudfront-waf.yaml (us-east-1), params.example.env
scripts/deploy.sh           one-command deploy: dev | stg | prod
docs/                       AWS architecture + deployment plan, calibration editor, reviews, guides
```

## Calibration editor (admins)

Raw logger data in `Monitors_info2` is never modified. Corrections live in `Calibration_Offsets`
(offset + deleted flag per sample) and every reader uses the `Monitors_effective` view — the
**validated series**. Every commit is audited (who, when, what) and can be undone.

Operations, on the whole window or on points selected on the graph / in the table:
shift (offset) · interpolate (also re-fills deleted points) · relative to a reference station ·
delete points · restore original · typed values. Drift detection suggests windows.
See [docs/calibration/EDITOR.md](docs/calibration/EDITOR.md).

## Website reports (admins)

Monthly and yearly files for the MAPI website — generated on a schedule (AWS / Windows Task Scheduler)
or from the **Reports** tab. See [docs/reports/WEBSITE_REPORTS.md](docs/reports/WEBSITE_REPORTS.md).

## Who sees what

Everyone signs in with Google (Cognito; allowlist in SSM). Only `ADMIN_EMAILS` (benp@mapi.gov.il) sees and
can use calibration and reports; all other users have a read-only dashboard.

## Run locally

```bash
# backend (Python 3.12)
cd backend && python -m venv venv && . venv/bin/activate
pip install -r requirements-lambda.txt uvicorn
cp .env.example .env            # DB_URI=…, AUTH_MODE=disabled for local development
python local_server_optimized.py         # http://localhost:30886

# frontend
cd frontend && npm ci && npm start      # http://localhost:30887 (AUTH_MODE=disabled)
```

On Windows, the on-prem server is started with `start_app.bat` (as Administrator).

## Tests

```bash
cd backend  && TEST_DB_URI=postgresql+psycopg2://user:pass@localhost:5432/sealevel_test pytest -q
cd frontend && CI=true npx react-scripts test --watchAll=false
```

CI (`.github/workflows/ci.yml`) runs both, a production build, `cfn-lint` and the Lambda image build.

## Deploy to AWS

See [docs/aws/DEPLOYMENT_PLAN.md](docs/aws/DEPLOYMENT_PLAN.md) (dev → stg → prod) and the runbook
[docs/aws/DEPLOYMENT.md](docs/aws/DEPLOYMENT.md). Short version:

```bash
scripts/deploy.sh dev infra/params.dev.env
```

or GitHub → Actions → **Deploy** → choose `dev`, `stg` or `prod`.
