# Phase 3 Calibration Upgrade — Implementation Plan

**Branches:** `feature/calibration-phase3` (step 1) → `feature/calibration-phase3-hydras` (steps 2–6). `main` and `feature/aws-ready` untouched.
**Goal:** bring the calibration tool to the level of professional hydrographic software (e.g. OTT Hydras):
precise input, the whole network as references, a relative-gap mode, and automatic drift detection.

## Baseline — already in the code

The four Phase 3 features first landed in `bafeaa51` (20 Oct 2026) and were hardened on `feature/aws-ready`
(audited corrections layer, admin-only access, idempotent commits, undo).

| Feature | Baseline status |
|---|---|
| 1. Direct number input for the offset | Number field + slider bound to `calibrationOffset`; API limit ±10 m. |
| 2. All stations in the Compare dropdown | Dropdown built from `/api/stations` minus target and "All Stations"; backend allowlist = all six stations (`CALIBRATION_STATIONS`). |
| 3. Relative Gap Calibration | `correction_type="relative"`, `expected_gap`; preview = reference + gap; commit **overwrites** the window's correction (`new offset = corrected − raw`, upsert replaces) — no double counting. Test: `test_relative_commit_matches_reference`. |
| 4. Drift Detection Engine | `suggest` with `reference_station` + `expected_gap`; reference validated against the allowlist **before** any query; flags \|delta − gap\| > 0.05 m; returns `malfunction_start/end`; UI snaps the window. |

## Refinement plan

| Step | Content | Estimate | Status |
|---|---|---|---|
| 1 | Direct number input UX (§1) | 0.5 day | ✅ done |
| 2 | Time alignment + coverage rule for relative mode (§3a) | 1.5 days | ✅ done |
| 3 | References endpoint + coverage-aware dropdown (§2) | 0.5 day | ✅ done |
| 4 | Expected-gap suggestion + two correction strengths (§3b) | 1 day | ✅ done |
| 5 | Drift engine: smoothing, episodes, slow-drift trend (§4) | 1.5 days | ✅ done |
| 6 | Drift UI: episode list, deviation strip, slow-drift notice (§4) | 1.5 days | ✅ done |
| 7 | End-to-end browser test, docs, PR | 0.5 day | ✅ browser test + docs; PR to open |

Cross-cutting rules: new endpoints are admin-only; every write goes through the audited commit/undo path
(detection never writes); thresholds and windows are request parameters with server defaults and are stored
in the audit record; raw data is never modified; tests run in CI against real PostgreSQL.

---

### §1 Direct number input — ✅ done (step 1)

**Gaps found:** `parseFloat(v) || 0` on every keystroke reset `-` and `0.` to `0` (negatives could not be typed);
the ±10 m slider had 20,000 positions (useless for millimetres); an empty field silently became 0; Auto-Suggest
overwrote the typed value.

**Delivered** (`frontend/src/components/Dashboard/OffsetInput.js`):
- Text field (`inputMode="decimal"`) keeps the text being typed (`-`, `-.`, `0.`); a number is applied as soon as the
  text parses (live preview) and on blur/Enter. Comma accepted as decimal separator. Letters ignored.
- Inline validation: "Enter a number in metres" / "Max ±10 m"; > ±1 m shows a warning but is allowed.
  While the text is not a valid number, **Preview and Commit are disabled** (and the hook refuses them).
- Slider directly below, bound to the same value; spans ±0.5 m (1 mm steps), widening to include larger typed values.
- Nudges: ±1 mm buttons beside the field, ±1 cm beside the slider; ↑/↓ = 1 mm, Shift = 1 cm.
- Auto-Suggest is offered under the field ("Suggested −0.200 m (high) · Use") instead of overwriting.
- Also fixed: drift auto-snap converted local timestamps through UTC (`toISOString()`), moving the window 2–3 h early.
- Tests: `OffsetInput.test.js` (30 cases); verified in Chrome (typing `-0.2`, blur on `-`, nudges, Suggest → Use → Preview).

### §2 All stations in the Compare dropdown (step 3)

**Gaps:** frontend list (DB) and backend allowlist (env var) can diverge → a station offered in the UI is rejected;
no indication whether a reference has data in the window; a reference equal to a newly chosen target stays selected.

**Work:**
1. `GET /api/calibration/references?station&start&end` (admin) → `{station, samples_in_window, coverage_pct, last_reading}`
   for every other station; the single source for the dropdown; backend allowlist validated against the same set.
2. Items show coverage ("Ashdod · 98%"), 0% disabled ("no data in window"), sorted by coverage.
3. Reset reference to "None" when it equals the target or loses coverage after the window changes.
4. Remember the last reference per target station (per browser).

**Done when:** every listed station previews without a 400; an empty reference cannot be selected.
**Tests:** pytest (coverage counts, admin-only); Jest (reset rule).

### §3 Relative Gap Calibration

**Gaps:** exact-timestamp join — stations sampled at different offsets or with gaps give little/no overlap, and
unmatched target rows stay uncorrected inside the window (partial correction, no warning); the expected gap must be
known in advance; "follow reference" copies the reference's short-term noise into the target.

**Work — step 2 (alignment):**
1. Nearest-match join with tolerance (default ±2 min, ≤ 10 min); linear interpolation of the reference between neighbours.
2. Coverage rule: < 95 % of target rows matched → commit refused with "Reference covers 81 % of the window";
   unmatched rows drawn distinctly in the preview.

**Work — step 4 (gap + strength):**
3. `POST /api/calibration/suggest-gap`: median(target − reference) over a calm baseline before the window
   (default 7 days, outliers excluded) with IQR and confidence; UI: "Typical gap +0.034 m (7 days before) · Use".
4. Two strengths: **Follow reference** (reference + gap, current) and **Level shift** (one constant offset =
   median(reference + gap − target) over the window; keeps the target's own signal — new default).
5. Audit record stores reference, gap, tolerance, coverage and strength.

**Done when:** a target/reference pair sampled 30 s apart corrects ≥ 99 % of rows; < 95 % coverage blocks commit with a reason.
**Tests:** synthetic offset sampling, reference gaps, coverage refusal, both strengths, gap suggestion on a known +0.034 m baseline.

### §4 Drift Detection Engine (steps 5–6)

**Gaps:** first-to-last flagged sample becomes one window, so two separate faults (Tuesday and Friday) merge into one
span covering good data; a single spike triggers; a fixed threshold catches steps but not slow creep; threshold not
adjustable in the UI; no deviation view, no per-episode review.

**Backend (`shared/drift.py`):**
1. Deviation `d(t) = (target − reference) − gap` on the aligned series (§3).
2. Rolling-median smoothing (default 30 min).
3. Episodes: |d| > threshold (default 0.05 m), merge runs separated by < 30 min, drop runs < 20 min →
   `{start, end, samples, max_dev, median_dev, type}`.
4. Classification: **step** (before/after medians differ, flat plateau → suggest offset), **spike/plateau**
   (returns to baseline → suggest bridge or level shift), **slow drift** (robust Theil–Sen slope of d(t), mm/day).
5. Parameters per request with server defaults; refuse when coverage < 95 %.

**UI:**
6. "Detect drift" panel listing episodes (start–end, duration, max deviation, type) with **Correct this** →
   prefills window, mode and value, ready for Preview.
7. Deviation strip under the main chart: d(t), ±threshold band, episodes shaded.
8. Slow-drift banner ("Haifa drifting +4 mm/day vs Ashdod since 1 Nov") — informational, never auto-applied.

**Done when:** two separate faults → two episodes; a 10-minute spike is ignored; a 1 cm/day creep over 30 days is
reported as slow drift within ±1 mm/day; episode → audited commit in three clicks.
**Tests:** fixtures with two steps, a spike, a slow ramp and noise-only data (0 false positives on noise).


---

## Delivered on `feature/calibration-phase3-hydras`

**Math** (`backend/shared/calibration_math.py`, pure and unit-tested):
- `align_reference` — reference onto target timestamps: exact → linear interpolation between neighbours within
  ±tolerance (default 120 s, max 600 s) → nearest one-sided → no match.
- `suggest_gap` — median of target − reference over a baseline, outliers beyond 3 × MAD removed, IQR → confidence.
- `detect_drift` — 30-min rolling median, threshold, runs merged across < 30-min gaps, runs < 20 min dropped,
  **edges snapped to the exact first/last raw sample beyond the threshold**, step vs plateau classification,
  Theil–Sen slow-drift trend (mm/day with 95 % interval) outside episodes, ≤ 300-point deviation series.

**API** (admin only, audited path unchanged):
- `preview`/`commit` relative mode: alignment + `strength` (`follow` | `level`) + `tolerance_seconds`;
  preview returns `coverage`, `commit_allowed` and a `matched` flag per sample; commit refuses below 95 % (follow)
  / 50 % (level). In follow mode unmatched samples get the correction interpolated in time (no uncorrected holes).
- **SQL overwrite rule:** every mode writes `new offset = corrected − raw` with an upsert that *replaces* the
  stored value; nothing is accumulated. Test `test_relative_commit_overwrites_never_accumulates` commits the same
  relative correction twice and checks the value and the stored offset are unchanged.
- `POST /api/calibration/references` — coverage of every other station for the window.
- `POST /api/calibration/suggest-gap` — typical gap from the N days before the window (default 7).
- `suggest` with reference + gap → drift engine: `episodes`, `slow_drift`, `deviation`, `coverage`;
  `malfunction_start/end` = first episode (window snaps to it). Threshold and smoothing are request parameters.

**UI:**
- Reference: native, accessible select with coverage ("Acre · 99%"); stations with no data in the window disabled;
  reset when it becomes the target or loses coverage.
- Relative mode: expected gap uses the validated number input (fixes the same `parseFloat || 0` bug), "Measure
  typical gap" with Use, strength radios, drift threshold selector.
- "Detect Drift (snap window)": panel with deviation strip (±threshold band, episodes shaded), episodes with
  type/duration/max deviation and **Correct this** (prefills window + offset, nothing written until commit),
  slow-drift notice (never auto-applied). Results survive the window snap they cause.
- Fixed: "Use Graph Selection" converted chart times to UTC (window 2–3 h early) and used `alert()`; calibration
  form labels were not linked to their fields (screen readers, tap-to-focus).
- Also fixed: `get_predictions` used `logger` before defining it (flake8 F821 — CI lint would fail). The same
  line exists on `feature/aws-ready`.

**Verification:** backend 68 tests (13 pure math + Phase 3 DB tests with a 30-s out-of-step station and a 1-h
outage); frontend 123 tests; full flow in Chrome: coverage list → Detect Drift snaps to 12:00–18:00 → Correct this
(−0.200 m) → Preview → Measure gap vs Acre (−0.034 m) → relative Preview → Commit → Undo.

**Deviation from §4.7:** the deviation strip lives in the calibration panel (next to the episodes it explains)
rather than under the main chart; it can move under the chart in the UI redesign.
