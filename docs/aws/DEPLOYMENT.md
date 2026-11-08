# Deployment Runbook — AWS (il-central-1)

One command deploys everything once the prerequisites below exist:

```bash
scripts/deploy.sh dev infra/params.dev.env      # or prod
```

It builds and pushes the backend image, deploys the CloudFront WAF (us-east-1) and the main stack,
runs the database migrations, builds and uploads the frontend, invalidates CloudFront, and runs a
smoke test (`/api/health` = 200, `/api/stations` without a token = 401).
The GitHub Actions **Deploy** workflow runs the same script through OIDC (no stored AWS keys).

---

## 0. What you need from the company AWS / network team

| Item | Why |
|---|---|
| Account access in **il-central-1** (IAM Identity Center or a deploy role for GitHub OIDC) | Deploy |
| A **VPC** with **≥2 private subnets** that have a **NAT route** | Lambdas call Secrets Manager, S3 and IMS (forecasts/warnings) |
| A **route from those subnets to the on-prem PostgreSQL** (Site-to-Site VPN / Direct Connect) and a firewall rule allowing TCP 5432 | 1-minute sync |
| Lambda **concurrency quota ≥ 100** in the account | Reserved concurrency (API 20, math 10, calibration 2, sync 1) |

## 1. One-time prerequisites

**a. Read-only on-prem database user** (run on the on-prem server):
```sql
CREATE ROLE sl_aws_sync LOGIN PASSWORD '<strong password>';
GRANT CONNECT ON DATABASE "<db>" TO sl_aws_sync;
GRANT USAGE ON SCHEMA public TO sl_aws_sync;
GRANT SELECT ON "Monitors_info2", "Locations", "SeaTides" TO sl_aws_sync;
```
Store it in Secrets Manager (il-central-1) as JSON `{"host":"<on-prem IP>","port":5432,"dbname":"<db>","username":"sl_aws_sync","password":"…"}`
and put the ARN in `ONPREM_SECRET_ARN`. Allow the Lambda subnets' CIDR in the on-prem `pg_hba.conf`.

**b. Google OAuth client** ([console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials):
- Consent screen: **External** (clients sign in with their own Google accounts), app name "Sea Level Dashboard – MAPI".
- Create OAuth client → *Web application*. Authorized redirect URI: the `GoogleRedirectUri` stack output,
  `https://<COGNITO_DOMAIN_PREFIX>.auth.il-central-1.amazoncognito.com/oauth2/idpresponse` (you know it before deploying).
- Save the client secret in Secrets Manager as plain text, named e.g. `sealevel/google-oauth-client-secret`.

**c. Parameters file:** copy `infra/params.example.env` → `infra/params.dev.env` and fill it in (it is git-ignored).

## 2. First deploy

1. `scripts/deploy.sh dev infra/params.dev.env` — the first run stops at **migrations** with
   *"Monitors_info2 not found"*. That's expected: Aurora is empty.
2. **Initial load** of the replica schema and history (choose one):
   - **Small history / simplest:** let the sync fill it. Create the empty tables with the on-prem schema
     (`pg_dump --schema-only -t '"Monitors_info2"' -t '"Locations"' -t '"SeaTides"'`, restored through
     a temporary bastion or Query Editor). The sync copies 7 days of history per minute from `SYNC_START_DATE`.
   - **Large history:** AWS DMS full load (on-prem → Aurora), **target table preparation mode: "Do nothing"**
     (DMS must not drop tables — the `Monitors_effective` view depends on them). Keep DMS CDC instead of
     the sync Lambda only if the network team prefers DMS; disable the `EveryMinute` schedule in that case.
3. Re-run `scripts/deploy.sh` — migrations apply, and the legacy on-prem `Calibration_Offset` values are
   imported into the audited calibration layer once.
4. Confirm the SNS e-mail subscription for alarms.

## 3. Access management

| Task | How |
|---|---|
| Let a client in | Edit the SSM parameter `/sealevel/<env>/allowed-users` — add `client.co.il` (whole domain) or `name@gmail.com`. Takes effect within a minute; no deploy. |
| Remove a client | Remove the entry. They are blocked at their next sign-in / token refresh (≤ 1 hour). To cut access immediately: Cognito console → user → *Disable* / sign out globally. |
| Calibration admin | `ADMIN_EMAILS` parameter (default `benp@mapi.gov.il`). Admin also requires Google to report the e-mail as verified. Members of the Cognito group `admin` are admins too. |
| See who changed data | `SELECT * FROM "Calibration_Audit" ORDER BY "Id" DESC;` or `POST /api/calibration/history` |
| Future CRM integration | Replace the allowlist lookup in `backend/lambdas/cognito_access/main.py` with a CRM query. |

## 4. Operations

- **Logs:** CloudWatch → `/aws/lambda/sealevel-<env>-*`; API access log `/sealevel/<env>/api-access` (includes the user e-mail).
- **Alarms (e-mail):** sync failing (data going stale), API 5xx, calibration errors, Aurora at max capacity.
- **Rollback:** redeploy a previous image tag: `ImageUri=<account>.dkr.ecr.il-central-1.amazonaws.com/sealevel-backend:<old sha>`.
  Data corrections are rolled back with *Undo* in the UI (or `POST /api/calibration/revert`).
- **Backups:** Aurora automated backups (14 days prod) + snapshot on stack deletion.
- **CSP:** sent as `Content-Security-Policy-Report-Only` first. After a week with no violations in the browser
  console, change the header name to `Content-Security-Policy` in `SecurityHeaders`.

## 5. Cost shape (no ElastiCache, per the 12.08.2025 decision)

Dominated by Aurora Serverless v2 (min 0.5 ACU) and NAT (company VPC). Lambda, API Gateway, CloudFront,
S3, Cognito and WAF are small at the expected user count. Lower `AuroraMinACU`/`AuroraMaxACU` for dev.

## 6. On-prem server during the migration

`backend/local_server_optimized.py` runs the same API (`backend/app.py`). Until the Cognito pool exists,
the on-prem build scripts use `REACT_APP_AUTH_MODE=disabled`; the backend then needs `AUTH_MODE=disabled`
and **calibration is locked** (the old shared-secret header was readable in the browser bundle).
Once the pool exists, set the Cognito values in `backend/.env` and build the frontend with
`REACT_APP_AUTH_MODE=cognito` to get the same Google sign-in on-prem — add
`https://<server-hostname>/auth/callback` to `ExtraCallbackUrls`. Cognito accepts plain `http://` callback
URLs only for `localhost`, so the on-prem server needs HTTPS (e.g. the existing nginx with a certificate).
