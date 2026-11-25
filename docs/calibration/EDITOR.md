# Calibration editor — graphical and tabular (Hydras-style)

The goal is the same workflow as OTT Hydras 3's Graphical Editor: select bad points on the graph or in a table,
fix them (delete, shift, interpolate, type a value), save to the database, keep the original logger data
untouched, and report from the validated series.

## Hydras 3 capability → this dashboard

| Hydras 3 | Here | How |
|---|---|---|
| Select individual points or a range on the time-series graph | ✅ | **Select points on graph**: drag a box (time *and* level), click a point; Shift adds, Ctrl/⌘ toggles. The chart focuses on the correction window and shows every raw sample. |
| Delete bad points | ✅ | **Delete** → the samples leave the validated series. The raw sample stays in `Monitors_info2`. |
| Shift values (datum / reference offset) | ✅ | **Vertical Offset** on the selection or the whole window. |
| Linear interpolation across missing / removed data | ✅ | **Interpolate** across the selection, from the nearest good unselected samples (≤ 1 day away). Deleted points are re-filled. |
| Original vs Corrected/Validated series | ✅ | `Monitors_info2` = original, never written. `Monitors_effective` view = validated (offsets applied, deleted samples left out). Every chart, statistic, prediction and export reads the validated series. |
| Save edits to the database | ✅ | **Review & commit** → `Calibration_Offsets` + `Calibration_Audit` (who, when, parameters, previous value of every sample) in one transaction. |
| Tabular editing — type corrected values | ✅ | **Table view**: every sample with raw value, validated value and state; tick rows (same selection as the graph) or type new values → **Preview typed values** → commit. |
| Undo | ✅ (more than Hydras) | **Undo** restores the exact previous state (offsets and deleted flags) from the audit rows. |
| Export validated / original | ✅ | **Download CSV** = validated series (everyone). **Raw CSV** = original values + offset + deleted flag (admins). Full resolution. |
| Not in Hydras: relative-to-reference correction, drift detection, gap measuring | ✅ | Phase 3 — see [PHASE3_PLAN.md](PHASE3_PLAN.md). |

Not covered (possible next step): inserting samples where the logger recorded nothing at all (a missing
timestamp). Interpolation re-fills deleted samples and samples that exist, but it does not create new ones.

## Workflow

1. Turn on **Calibration Correction** (admins only), pick one station and set the window (≤ 14 days for
   point editing; a longer window still supports whole-window corrections).
2. The chart zooms to the window: coloured line and dots = validated samples; grey = raw logger values
   (shown when anything is corrected); red ✕ = deleted samples; orange circles = your selection.
3. **✏️ Select points on graph** → drag around the spike → **🗑 Delete**, **〰 Interpolate** or **↩ Restore**.
   This creates a preview right away. To shift the selection instead, choose *Vertical Offset* and type the value.
4. Check the preview line and the summary in the bottom bar → **Review & commit…** → **Commit correction**.
5. The editor stays open and reloads the saved state, so you can keep editing. **Undo** reverts the last commit.

## API (admin only)

| Endpoint | Body |
|---|---|
| `POST /api/calibration/samples` | `{station, start_datetime, end_datetime}` → every raw sample with `raw_value, offset, value, deleted` (≤ 20,000) |
| `POST /api/calibration/preview` / `commit` | `{station, start_datetime, end_datetime, correction_type, …, timestamps?, values?, request_id (commit)}` |
| `correction_type` | `offset` (`offset`), `interpolate`, `relative` (`reference_station`, `expected_gap`, `strength`), `delete`, `restore`, `manual` (`values: [{Tab_DateTime, value}]`) |
| `timestamps` | optional list of selected samples; without it the whole window is used (`delete` requires a selection) |
| `GET /api/export?series=validated|raw` | full-resolution CSV/JSON, ≤ 400 days; `raw` = admins |

## Data model

```
Monitors_info2 (raw, replicated from on-prem, never written by the app)
Calibration_Offsets ("Tab_TabularTag", "Tab_DateTime", "Offset", "Deleted", "Audit_Id")
Calibration_Audit / Calibration_Audit_Rows (previous "Old_Offset", "Old_Deleted" per sample)
Monitors_effective = Monitors_info2 + Offset, WHERE NOT Deleted   ← validated series, used by every reader
```

`backend/migrations/003_calibration_layer.sql` is idempotent and is re-applied on every deploy (the AWS
migrate Lambda). On-prem: run it once with `psql -f`.
