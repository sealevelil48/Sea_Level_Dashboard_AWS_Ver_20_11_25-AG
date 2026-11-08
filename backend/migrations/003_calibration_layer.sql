-- =============================================================================
-- 003 — Cloud-owned calibration layer (idempotent; safe to re-run)
--
-- Why: on AWS, "Monitors_info2" is a replica synced from the on-prem database
-- every minute. Writing corrections into the replicated table would race with
-- the sync. Corrections therefore live in their own table, and readers use the
-- "Monitors_effective" view, which applies them.
--
--   "Calibration_Offsets"      one row per corrected sample (tag, datetime, offset)
--   "Calibration_Audit"        one row per commit/revert: who, when, what
--   "Calibration_Audit_Rows"   the previous offset of every affected sample (enables undo)
--   "Monitors_effective"       view = Monitors_info2 with Tab_Value_mDepthC1 corrected,
--                              plus "Raw_mDepthC1" and "Calibration_Offset"
-- =============================================================================

CREATE TABLE IF NOT EXISTS "Calibration_Offsets" (
    "Tab_TabularTag" TEXT        NOT NULL,
    "Tab_DateTime"   TIMESTAMP   NOT NULL,
    "Offset"         DOUBLE PRECISION NOT NULL,
    "Audit_Id"       BIGINT,
    PRIMARY KEY ("Tab_TabularTag", "Tab_DateTime")
);

CREATE TABLE IF NOT EXISTS "Calibration_Audit" (
    "Id"               BIGSERIAL PRIMARY KEY,
    "Request_Id"       UUID UNIQUE,
    "Action"           TEXT NOT NULL CHECK ("Action" IN ('commit', 'revert', 'import')),
    "Station"          TEXT NOT NULL,
    "Correction_Type"  TEXT,
    "Start_DateTime"   TIMESTAMP,
    "End_DateTime"     TIMESTAMP,
    "Parameters"       JSONB NOT NULL DEFAULT '{}'::jsonb,
    "Rows_Affected"    INTEGER NOT NULL DEFAULT 0,
    "User_Email"       TEXT NOT NULL,
    "User_Sub"         TEXT,
    "Created_At"       TIMESTAMPTZ NOT NULL DEFAULT now(),
    "Reverts_Audit_Id" BIGINT REFERENCES "Calibration_Audit"("Id"),
    "Reverted_By_Id"   BIGINT REFERENCES "Calibration_Audit"("Id")
);
CREATE INDEX IF NOT EXISTS idx_cal_audit_station_created
    ON "Calibration_Audit" ("Station", "Created_At" DESC);

CREATE TABLE IF NOT EXISTS "Calibration_Audit_Rows" (
    "Audit_Id"       BIGINT    NOT NULL REFERENCES "Calibration_Audit"("Id") ON DELETE CASCADE,
    "Tab_TabularTag" TEXT      NOT NULL,
    "Tab_DateTime"   TIMESTAMP NOT NULL,
    "Old_Offset"     DOUBLE PRECISION,           -- NULL = sample had no correction
    PRIMARY KEY ("Audit_Id", "Tab_TabularTag", "Tab_DateTime")
);

-- Build the view from whatever columns Monitors_info2 actually has, replacing
-- the depth column with the corrected value. Works on-prem and on Aurora.
DO $$
DECLARE
    tag_type  TEXT;
    dt_type   TEXT;
    col_list  TEXT;
BEGIN
    SELECT format_type(a.atttypid, a.atttypmod) INTO tag_type
      FROM pg_attribute a WHERE a.attrelid = '"Monitors_info2"'::regclass AND a.attname = 'Tab_TabularTag';
    SELECT format_type(a.atttypid, a.atttypmod) INTO dt_type
      FROM pg_attribute a WHERE a.attrelid = '"Monitors_info2"'::regclass AND a.attname = 'Tab_DateTime';

    EXECUTE 'DROP VIEW IF EXISTS "Monitors_effective"';

    -- Match key column types to the source table so the join can use indexes.
    IF tag_type IS NOT NULL AND tag_type <> (SELECT format_type(atttypid, atttypmod) FROM pg_attribute
            WHERE attrelid = '"Calibration_Offsets"'::regclass AND attname = 'Tab_TabularTag') THEN
        EXECUTE format('ALTER TABLE "Calibration_Offsets" ALTER COLUMN "Tab_TabularTag" TYPE %s USING "Tab_TabularTag"::%s', tag_type, tag_type);
        EXECUTE format('ALTER TABLE "Calibration_Audit_Rows" ALTER COLUMN "Tab_TabularTag" TYPE %s USING "Tab_TabularTag"::%s', tag_type, tag_type);
    END IF;
    IF dt_type IS NOT NULL AND dt_type <> (SELECT format_type(atttypid, atttypmod) FROM pg_attribute
            WHERE attrelid = '"Calibration_Offsets"'::regclass AND attname = 'Tab_DateTime') THEN
        EXECUTE format('ALTER TABLE "Calibration_Offsets" ALTER COLUMN "Tab_DateTime" TYPE %s', dt_type);
        EXECUTE format('ALTER TABLE "Calibration_Audit_Rows" ALTER COLUMN "Tab_DateTime" TYPE %s', dt_type);
    END IF;

    SELECT string_agg(
             CASE WHEN column_name = 'Tab_Value_mDepthC1'
                  THEN '(CAST(m."Tab_Value_mDepthC1" AS DOUBLE PRECISION) + COALESCE(o."Offset", 0)) AS "Tab_Value_mDepthC1"'
                  ELSE format('m.%I', column_name) END,
             ', ' ORDER BY ordinal_position)
      INTO col_list
      FROM information_schema.columns
     WHERE table_name = 'Monitors_info2'
       AND table_schema = current_schema()
       AND column_name NOT IN ('Calibration_Offset');   -- legacy in-table column is superseded

    EXECUTE 'CREATE VIEW "Monitors_effective" AS SELECT ' || col_list ||
            ', CAST(m."Tab_Value_mDepthC1" AS DOUBLE PRECISION) AS "Raw_mDepthC1"' ||
            ', COALESCE(o."Offset", 0) AS "Calibration_Offset"' ||
            ' FROM "Monitors_info2" m LEFT JOIN "Calibration_Offsets" o' ||
            '   ON o."Tab_TabularTag" = m."Tab_TabularTag" AND o."Tab_DateTime" = m."Tab_DateTime"';
END $$;

-- One-time import of corrections made with the old in-table column (on-prem era).
DO $$
DECLARE
    imported INTEGER;
    audit_id BIGINT;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_name = 'Monitors_info2' AND column_name = 'Calibration_Offset')
       AND NOT EXISTS (SELECT 1 FROM "Calibration_Audit" WHERE "Action" = 'import') THEN
        INSERT INTO "Calibration_Audit" ("Action", "Station", "User_Email", "Parameters")
        VALUES ('import', '*', 'migration-003', '{"source": "Monitors_info2.Calibration_Offset"}')
        RETURNING "Id" INTO audit_id;

        EXECUTE format($q$
            INSERT INTO "Calibration_Offsets" ("Tab_TabularTag", "Tab_DateTime", "Offset", "Audit_Id")
            SELECT "Tab_TabularTag", "Tab_DateTime", CAST("Calibration_Offset" AS DOUBLE PRECISION), %s
              FROM "Monitors_info2"
             WHERE "Calibration_Offset" IS NOT NULL AND "Calibration_Offset" <> 0
            ON CONFLICT DO NOTHING$q$, audit_id);
        GET DIAGNOSTICS imported = ROW_COUNT;
        UPDATE "Calibration_Audit" SET "Rows_Affected" = imported WHERE "Id" = audit_id;
        RAISE NOTICE 'Imported % legacy calibration offsets', imported;
    END IF;
END $$;
