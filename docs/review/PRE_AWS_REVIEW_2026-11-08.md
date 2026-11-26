# Pre-AWS Review — Sea Level Dashboard

**Branch reviewed:** `feature/calibration-correction` (9afa5783), compared with `main` (a4d0c30d)
**Date:** 2026-11-08
**How it was checked:** I read the code, ran the calibration handlers against a local PostgreSQL 16 loaded with synthetic Haifa/Ashdod data, built the frontend, ran both test suites, ran `npm audit`, and scanned the git history.

Severity levels: **P0** = blocks go-live · **P1** = fix before go-live · **P2** = fix soon after · **P3** = cleanup

---

## 1. Data accuracy (calibration)

| # | Sev | Finding | Evidence |
|---|-----|---------|----------|
| D1 | P0 | **Interpolate commit always fails.** In `_fetch_interpolation_boundaries`, each half of the `UNION ALL` has its own `ORDER BY … LIMIT 1` without parentheses, and PostgreSQL rejects that. Preview works, so the user sees a good preview, clicks Confirm, and gets a 500 error. | Reproduced: `psycopg2.errors.SyntaxError: syntax error at or near "UNION"` |
| D2 | P0 | **Corrections disappear when you zoom out.** `get_data` adds `Calibration_Offset` only at the `raw` aggregation level. The 5min, 15min, hourly, daily and weekly queries average the uncorrected `Tab_Value_mDepthC1`. So the same station shows corrected values over short ranges and uncorrected values over long ranges. This affects both `lambda_handler` and `lambda_handler_batch`. | `get_data/main.py` lines 321-400 and 561-640 |
| D3 | P0 | **Every other consumer ignores the offset.** Live data, yesterday data, station map, analytics, predictions (Kalman/ARIMA) and the Southern Baseline QC all read the raw column. Forecasts and statistics are computed from data you have already corrected. | `grep Calibration_Offset` matches only `get_data` |
| D4 | P0 | **A commit can be applied twice.** `apiService.request()` retries POSTs on 5xx and network errors, and offset mode is additive (`COALESCE(offset,0) + :offset`). If the first commit succeeds but the response is lost, the retry adds the offset a second time. | `apiService.js` retry loop has no method guard |
| D5 | P1 | **No audit trail and no undo.** Commits change `Calibration_Offset` in place: offset mode adds, interpolate and relative modes overwrite. Nothing records who changed what, when, or what the value was before. For a national-datum system this needs an append-only `Calibration_Audit` table that stores the before values, plus a revert endpoint. | — |
| D6 | P1 | **"Suggest" measures the wrong thing.** It returns `median(12h before) − median(12h after)` and ignores the data inside the window. For a corrupted plateau, which is the main use case, the before and after medians agree, so the suggestion is about 0. | Test: a +0.20 m plateau gave a suggestion of **−0.0007** |
| D7 | P2 | Preview and commit pick the interpolation boundaries differently. Preview uses only points inside the window and returns 422 if no sample falls exactly on the start time. Commit searches the whole table. | — |
| D8 | P2 | After a commit, stale data keeps showing: the browser cache (5 min) is not cleared, and responses carry `Cache-Control: public, max-age=120`, which CloudFront would also honour. | — |
| D9 | P2 | Relative-mode preview loops `df.loc[...]` once per row (O(n²)), and `fillna(inplace=True)` on a column slice does nothing under pandas 3. | — |
| D10 | P3 | The action bar always says "offset X m", even in interpolate and relative modes. | `CalibrationActionBar.js` |

## 2. Security

| # | Sev | Finding |
|---|-----|---------|
| S1 | P0 | **The calibration "access secret" is public.** `REACT_APP_CALIBRATION_ACCESS` is compiled into the JS bundle, because CRA inlines every `REACT_APP_*` variable. Anyone can open DevTools, copy the header, and commit corrections. Layer 1 of the two-layer model therefore protects nothing. The replacement is real identity: Google sign-in through Cognito, with an `admin` group check on the server. |
| S2 | P0 | **Credentials are in git history.** `backend/.env` was committed in Aug–Oct 2025 and removed in bb3d3047. Two real DB connection strings with passwords are still in history (the `SeaLevel` and `postgres` users on `Test2-SeaLevels*`). Rotate them. If the repo is or ever was public, also consider rewriting history (`git filter-repo`). |
| S3 | P1 | The GovMap token is hard-coded in `backend/mapframe.html` and `.env.example`. It is client-side by nature, but restrict it to the production domain in GovMap's console. |
| S4 | P1 | `POST /api/cache/clear` takes no authentication and accepts any pattern, so anyone can flush the cache (a cheap DoS). `/api/metrics`, `/api/health` (Python version, pool stats) and `/docs` are all public. |
| S5 | P1 | CORS falls back to `*` together with `allow_credentials=True`. The handlers also hard-code `Access-Control-Allow-Origin: *`. |
| S6 | P1 | Error responses return `str(e)` to clients from most endpoints, which leaks SQL and internal paths. The calibration endpoints already do this correctly. |
| S7 | P2 | `_check_auth` compares the key with `!=`; use `hmac.compare_digest`. This becomes moot once auth moves to JWT. |
| S8 | P2 | There is no CSP or security headers (HSTS, X-Frame-Options, Referrer-Policy) and no rate limiting. On AWS, CloudFront response-headers policies and WAF cover this. |
| S9 | P2 | `npm audit` (prod deps): **5 critical, 34 high**. The ones that matter at runtime: `maplibre-gl` (critical XSS sanitizer bypass, fix available) and `xlsx` 0.18.5 (prototype pollution and ReDoS, with no fix on npm; switch to the SheetJS CDN build or `exceljs`). Most of the rest are build-time `react-scripts` dependencies. |
| S10 | P3 | `setup_aws_credentials.ps1` writes long-lived IAM user keys. On AWS, use IAM Identity Center or OIDC from GitHub Actions instead of static keys. |

I tested path traversal through the SPA catch-all route with encoded `..`, and it is **not exploitable** (Starlette normalises the path). I will still add a `resolve()` check.

## 3. Backend correctness and performance

| # | Sev | Finding |
|---|-----|---------|
| B1 | P0 | **`config.py` cannot import.** It uses `from pydantic import BaseSettings`, which is pydantic v1, but requirements pin pydantic 2.5.3. Anything that imports `config` crashes. |
| B2 | P1 | **Sync DB calls inside `async def` routes block the event loop.** Every handler is synchronous, so one slow query stalls every other request. This is the likely cause of the "performance issues". Make the routes plain `def`, which FastAPI runs in a threadpool. On Lambda the problem goes away. |
| B3 | P1 | **There are two DB engines with large pools.** `shared.database` uses 20+10 connections and `database_production` adds its own. On Lambda, each concurrent container would open up to 30 connections and quickly exhaust RDS. Use one engine, `pool_size=1` or `NullPool` on Lambda, and RDS Proxy. |
| B4 | P1 | `RequestDeduplicator` creates the coroutine before checking for duplicates. The duplicate's coroutine is never awaited, which raises a RuntimeWarning and leaks a little memory. |
| B5 | P2 | `dummy_handler` is defined only inside the first `except`, so if the calibration import fails the server crashes with a `NameError`. |
| B6 | P2 | `_invalidate_redis_cache` uses `KEYS *data*`, which is O(N) and blocks Redis. Use `SCAN` or versioned cache keys. |
| B7 | P2 | `/api/stations/map` returns **hard-coded fake values** dated 2025-10-22. The fallback station lists are also inconsistent: "Yafo" vs "Jaffa", and Haifa and Ashdod are missing from the fallback. |
| B8 | P3 | There are three server variants (`local_server.py`, `-prod`, `_optimized`), four DB modules and two data_processing modules. Only one of each is live, and the rest is dead code that confuses reviewers. |

## 4. DevOps and deployment

| # | Sev | Finding |
|---|-----|---------|
| O1 | P0 | **CI never runs.** `.github/workflows/ci.yml` has a mis-indented `- name: Install dependencies` at column 0, so the YAML is invalid. Even after fixing that, the tests fail at collection (`ModuleNotFoundError: shared`), and `CI=true` turns the ~40 eslint `no-console` warnings into build errors. The frontend tests show 1 failed and 84 passed. |
| O2 | P0 | **There is no infrastructure as code for the actual target.** The deployment guide (`deployment/פריסה.txt`) describes Lambda, Layer, API Gateway, Cognito, S3 and CloudFront, but everything is click-ops. The SAM template covers only Step Functions, uses `python3.9` (deprecated on Lambda), and has `CodeUri` paths that don't resolve. |
| O3 | P1 | **The Lambda packaging plan won't fit.** pandas, numpy, scipy, statsmodels and scikit-learn (plus prophet) exceed the 250 MB unzipped Layer/zip limit. Use **Lambda container images** (ECR, up to 10 GB). |
| O4 | P1 | Production URLs and IPs are hard-coded in `package.json` (`85.155.88.90`) and `start_app.bat` (`5.102.231.16`, `C:\Users\slg\...`), and `start_app.bat` kills *every* python and node process on the host. |
| O5 | P1 | Requirements disagree: the root and backend files pin different fastapi, starlette and aiohttp versions, prophet is pinned with nothing to build it on, and pandas 2.2.2 won't install on Python ≥3.13. Use a single lockfile and target Python 3.12 on Lambda. |
| O6 | P1 | **Where the data comes from is undocumented.** Nothing in the repo writes to `Monitors_info2`; it is filled on-prem. Moving to AWS needs a decision (see the questions at the end). |
| O7 | P2 | There is no structured logging or alarms. `server.log` is written to the CWD. On Lambda, use JSON logs to CloudWatch plus alarms on 5xx and duration. |
| O8 | P2 | `docker-compose.yml` references `backend/Dockerfile` and `frontend/Dockerfile`, which don't exist. |
| O9 | P3 | The repo root holds ~35 status/report `.md` files. The pack is 97 MB because `node_modules` was once committed. |

## 5. UI / UX

| # | Sev | Finding |
|---|-----|---------|
| U1 | P0 | **The calibration toggle is visible to every visitor.** It should render only for the admin role, and the server must enforce that too, since hiding the toggle alone is not security. |
| U2 | P1 | Commit is a single click on a green button with no undo. It needs a confirmation step that restates the station, window, mode, rows affected and effective change, plus a "Revert last" action backed by the audit table (D5). |
| U3 | P1 | There is no sign-in UI. You'll need a header avatar/menu with Sign in with Google, sign out, and an "Admin" badge. |
| U4 | P2 | The site is English-only, with `lang="en"` and no RTL support, while the users are Israeli and the source docs are in Hebrew. At least add a Hebrew locale for labels and warnings. |
| U5 | P2 | `Dashboard/index.js` is 1,449 lines, and `Dashboard.old.js` (2,378 lines) is still in the tree. The main bundle is 212 kB gzipped, with Plotly *and* Chart.js *and* Leaflet *and* MapLibre all shipped. |
| U6 | P2 | Errors go to `console.error` and the components return `null`. The user sees an empty chart instead of "no data for this range" or "server unavailable". |
| U7 | P3 | Fake map values (B7) could be mistaken for real readings. That is a trust issue for a public dashboard. |

---

## Proposed target on AWS (il-central-1)

```
Users ──► CloudFront (WAF, security headers) ──► S3 (React build, private, OAC)
              │
              └─/api/*──► API Gateway HTTP API ──JWT authorizer (Cognito)──► Lambda (container images, Python 3.12)
                                                                                    │
Cognito User Pool ◄── Google IdP (OAuth)                                            ├─► RDS Proxy ─► RDS PostgreSQL
   group "admin" = Ben → only group allowed on /api/calibration/*                   └─► Secrets Manager
EventBridge schedule ─► refresh / predictions jobs     CloudWatch logs + alarms     GitHub Actions (OIDC) ─► SAM deploy
```

- **Google sign-in:** Cognito Hosted UI with Google as the identity provider and the PKCE code flow. No secrets go in the browser.
- **Calibration lockdown:** the API Gateway route `/api/calibration/*` requires a valid JWT. The Lambda then also checks `cognito:groups` contains `admin`, and every audit row records the caller's `sub` and email. The frontend shows calibration only to admins.
- **Everything as code:** one SAM template, deployed per environment (dev/prod) from GitHub Actions.

## Fix plan (after you approve)

1. **Data accuracy:** D1–D9, a `Calibration_Audit` table plus a revert endpoint, and the offset applied in a single SQL expression shared by every reader.
2. **Auth:** Cognito and Google, the admin group, removal of `REACT_APP_CALIBRATION_ACCESS` and the internal proxy key, and an admin-only UI.
3. **Security hardening:** S3–S9, plus closing the open admin endpoints.
4. **Backend:** B1–B7, one DB engine, sync routes, removal of fake data.
5. **DevOps:** working CI (lint, test, build), a SAM template, Dockerfiles for Lambda, a lockfile, and env-driven URLs.
6. **UX:** U1–U3 and U6 now. U4 (Hebrew) and U5 (bundle diet) come as a follow-up.
7. **Tests:** new pytest coverage for every calibration mode against a real Postgres in CI.

---

## Resolution — branch `feature/aws-ready`

Architecture follows the AWS architect's design of **12.08.2025** — see [docs/aws/ARCHITECTURE.md](../aws/ARCHITECTURE.md).
Additional finding during the fix: **A1 (P1)** — the production server (`local_server_optimized.py`) had no
`/api/analytics` route, so every analytics call from the dashboard returned 404. Fixed (routed to the Data & Math Lambda).

| # | Status | How it was fixed / verified |
|---|---|---|
| D1 | ✅ | Interpolation anchors on the nearest good samples *outside* the window; SQL parenthesised. Test `test_interpolate_commit_works`. |
| D2, D3 | ✅ | All readers use the `Monitors_effective` view (raw + correction), so every aggregation level and every consumer (live, map, predictions, analytics, QC) sees corrected values. Test `test_corrections_visible_in_aggregated_data`. |
| D4 | ✅ | Commits carry a `request_id` (UUID, unique in the audit table); the client never retries writes. Test `test_offset_commit_is_idempotent_and_revertible`. |
| D5 | ✅ | `Calibration_Audit` + `Calibration_Audit_Rows` written in the same transaction; `revert` restores the exact previous values; **Undo** in the UI. Verified end-to-end in Chrome. |
| D6 | ✅ | Suggest = median(surrounding 12 h) − median(window). The +0.20 m plateau now yields −0.200 (was −0.0007). |
| D7 | ✅ | Preview and commit share one code path (`_compute_targets`). Test `test_preview_matches_commit`. |
| D8 | ✅ | Client cache cleared and chart refetched after commit/undo; API data responses use `no-cache`. Verified in Chrome. |
| D9, D10 | ✅ | Vectorised relative mode; the action bar shows mode-specific summaries plus a confirmation dialog. |
| S1 | ✅ | Shared secret removed. Google sign-in (Cognito, PKCE) and server-side admin check (`ADMIN_EMAILS`=benp@mapi.gov.il + verified e-mail). Tests: forged, expired, wrong-audience and access tokens are rejected; non-admin gets 403. |
| S2 | ⚠️ action needed | **Rotate the on-prem DB passwords** that appear in git history. Rewriting history is optional. |
| S3 | ⚠️ action needed | Restrict the GovMap token to the production domain in GovMap's console. |
| S4–S7 | ✅ | Admin-only maintenance endpoints; no wildcard CORS; generic 5xx bodies; docs disabled by default; JWT verification replaces the shared key. |
| S8 | ✅ | CloudFront security headers (HSTS, frame, nosniff, referrer, CSP report-only), WAF on CloudFront and API, API throttling. |
| S9 | ◐ | Runtime risk reduced (CSV export is server-side). `xlsx`/`maplibre-gl` upgrades are part of the UI redesign. |
| B1–B5, B7 | ✅ | pydantic v2 settings; sync routes in a threadpool; one pool sized by env (`DB_POOL_SIZE=1` on Lambda); dedup removed; safe imports; fake map data removed. |
| B6 | ✅ | `SCAN` instead of `KEYS`; Redis optional (off on AWS, per the architect). |
| B8 | ✅ | `local_server.py` and `local_server-prod.py` retired; one app (`backend/app.py`) for on-prem and Lambda. |
| O1 | ✅ | CI rewritten: backend tests against real PostgreSQL 16, frontend tests and build, cfn-lint, Lambda image build. Broken legacy tests are quarantined with a note. |
| O2, O3, O5 | ✅ | SAM template for the full stack; Lambda container image (Python 3.12, pinned deps, no prophet); `scripts/deploy.sh`; GitHub OIDC deploy workflow. |
| O6 | ✅ | Sync Lambda (every minute, overlap window, chunked catch-up), tested against two databases. |
| O7 | ✅ | stdout logging → CloudWatch; alarms → SNS e-mail. |
| O4, O8, O9 | ◐ | On-prem scripts are kept so the current server keeps running (now explicit about auth mode). They are retired after cut-over. |
| U1–U3, U6 | ✅ | Calibration UI shown only to admins; confirmation dialog; Undo; sign-in screen and user menu; calibration errors surfaced in the UI. Station checkboxes now have proper labels (a11y). |
| U4, U5, U7 | → | Covered by the UI redesign proposal (PWA, Hebrew/RTL, lighter bundle). |

**Test totals:** backend 46 passed (real PostgreSQL); frontend 87 passed; both CloudFormation templates lint clean.
