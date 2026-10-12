-- Non-destructive calibration offset column
-- Run once against PostgreSQL before starting the updated server.
-- Raw Tab_Value_mDepthC1 is NEVER modified; corrections live in this column only.
ALTER TABLE "Monitors_info2"
    ADD COLUMN IF NOT EXISTS "Calibration_Offset" NUMERIC DEFAULT 0;

UPDATE "Monitors_info2"
    SET "Calibration_Offset" = 0 WHERE "Calibration_Offset" IS NULL;

COMMENT ON COLUMN "Monitors_info2"."Calibration_Offset" IS
    'Non-destructive correction applied at query time. Raw Tab_Value_mDepthC1 is never modified.';
