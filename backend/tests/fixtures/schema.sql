-- Minimal synthetic copy of the production schema for tests.
DROP VIEW IF EXISTS "Monitors_effective";
DROP TABLE IF EXISTS "Calibration_Audit_Rows", "Calibration_Offsets", "Calibration_Audit", "Monitors_info2", "Locations", "SeaTides" CASCADE;
CREATE TABLE "Locations" ("Tab_TabularTag" INTEGER, "Station" TEXT, "X" FLOAT, "Y" FLOAT, "Longitude" FLOAT, "Latitude" FLOAT);
CREATE TABLE "Monitors_info2" ("Tab_TabularTag" INTEGER, "Tab_DateTime" TIMESTAMP,
                               "Tab_Value_mDepthC1" NUMERIC, "Tab_Value_monT2m" NUMERIC);
CREATE TABLE "SeaTides" ("Date" DATE, "Station" TEXT, "HighTide" FLOAT, "LowTide" FLOAT);
CREATE INDEX ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime");
INSERT INTO "Locations" VALUES (1, 'Haifa', 0, 0, 34.99, 32.82), (2, 'Ashdod', 0, 0, 34.63, 31.80);
-- Haifa has a +0.20 m malfunction plateau on 2026-10-08 12:00–18:00; Ashdod is clean.
INSERT INTO "Monitors_info2"
SELECT t, g,
       CASE WHEN t = 1 AND g BETWEEN '2026-10-08 12:00' AND '2026-10-08 18:00' THEN 0.30 ELSE 0.10 END
         + 0.01 * sin(extract(epoch FROM g) / 3600),
       20
  FROM generate_series('2026-10-07'::timestamp, '2026-10-10', '1 minute') g, (VALUES (1), (2)) v(t);
