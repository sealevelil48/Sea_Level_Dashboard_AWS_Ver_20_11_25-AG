-- =============================================================================
-- 004 — Least-privilege database roles (idempotent)
--   sealevel_reader      dashboard API: SELECT only
--   sealevel_calibrator  calibration API: reader + write the calibration tables only
--   sealevel_sync        on-prem → Aurora sync: write the replica tables only
-- Login users are created by the migrate Lambda from Secrets Manager and granted one of these.
-- The raw replica table can never be modified by the API, even if the API were compromised.
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sealevel_reader') THEN CREATE ROLE sealevel_reader NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sealevel_calibrator') THEN CREATE ROLE sealevel_calibrator NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sealevel_sync') THEN CREATE ROLE sealevel_sync NOLOGIN; END IF;
END $$;

GRANT USAGE ON SCHEMA public TO sealevel_reader, sealevel_calibrator, sealevel_sync;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sealevel_reader, sealevel_calibrator, sealevel_sync;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sealevel_reader, sealevel_calibrator, sealevel_sync;

GRANT INSERT, UPDATE, DELETE ON "Calibration_Offsets", "Calibration_Audit", "Calibration_Audit_Rows" TO sealevel_calibrator;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sealevel_calibrator;
DO $$ BEGIN EXECUTE format('GRANT TEMPORARY ON DATABASE %I TO sealevel_calibrator', current_database()); END $$;  -- bulk staging table

GRANT INSERT, DELETE ON "Monitors_info2", "Locations" TO sealevel_sync;
DO $$ BEGIN
    IF to_regclass('"SeaTides"') IS NOT NULL THEN EXECUTE 'GRANT INSERT, DELETE ON "SeaTides" TO sealevel_sync'; END IF;
END $$;

-- Readers must never write, even through the view.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM sealevel_reader;
