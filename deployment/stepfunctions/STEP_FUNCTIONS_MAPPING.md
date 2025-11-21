# Step Functions mapping for Sea Level Dashboard

This file maps the recommended Step Functions workflows to the existing Lambda code in the repository.

Workflows (created from repo scan):

- DataIngestionWorkflow
  - Purpose: fetch live/remote data, normalize, store staging data
  - Trigger: EventBridge schedule / S3 arrival
  - Key Lambdas: `backend/lambdas/get_data/main.py`, `backend/lambdas/get_live_data/main.py`, `backend/lambdas/get_yesterday_data/main.py`
  - Suggested states: Fetch -> Validate -> Transform -> Store -> Notify

- SeaTidesRefreshWorkflow
  - Purpose: orchestrate materialized view maintenance (pre-checks, index/create, ANALYZE/VACUUM, REFRESH, post-checks)
  - Trigger: Manual / EventBridge schedule / completion of ingestion
  - Key Lambdas: a small orchestration Lambda (you can reuse `backend/optimizations/optimize_seatides.py` as a job runner or create an `orchestrator` Lambda)
  - Suggested states: Pre-checks -> Maintenance (optional) -> Refresh -> Post-check -> Notify

- PredictionsWorkflow
  - Purpose: run model predictions and persist results
  - Trigger: schedule or ingestion completion
  - Key Lambdas: `backend/lambdas/get_predictions/main.py`
  - Suggested states: Partition -> RunModel (Map) -> Aggregate -> Store -> Notify

- NotificationsWorkflow
  - Purpose: evaluate warnings and send alerts (IMS warnings, thresholds)
  - Trigger: schedule or results from ingest/predictions
  - Key Lambdas: `backend/lambdas/get_ims_warnings/main.py`, `backend/lambdas/get_station_map/main.py`
  - Suggested states: FetchChecks -> Evaluate -> BuildMessage -> Publish

- BatchBackfillWorkflow (optional)
  - Purpose: ad-hoc backfills, exports, heavy batch endpoints
  - Trigger: API / manual
  - Key Lambdas: `backend/lambdas/get_data/main.py` (batch handler `lambda_handler_batch`), other batch scripts
  - Suggested states: Validate -> Chunk -> ProcessChunks (Map) -> Merge -> Store -> Notify

Notes:
- You can merge Notifications into Ingestion or Predictions if you prefer fewer workflows, but separate workflows are better for observability and retries.
- `get_data/main.py` already contains both streaming and `batch` entrypoints; the batch entrypoint is a good candidate for the BatchBackfill workflow.

Files referenced by scan:
- `backend/lambdas/get_data/main.py` (contains `lambda_handler_batch` and `lambda_handler`)
- `backend/lambdas/get_live_data/main.py`
- `backend/lambdas/get_yesterday_data/main.py`
- `backend/lambdas/get_predictions/main.py`
- `backend/lambdas/get_ims_warnings/main.py`
- `backend/lambdas/get_station_map/main.py`
- `backend/lambdas/get_stations/main.py`

Next: see `template-sfn-sam.yaml` for a starter SAM template to deploy these workflows and lambdas.
