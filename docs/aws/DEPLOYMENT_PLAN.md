# AWS deployment plan — dev → stg → prod (MAPI)

Architecture: the AWS architect's design of **12.08.2025** ([ARCHITECTURE.md](ARCHITECTURE.md)), region **il-central-1**.
Everything is code: `infra/template.yaml` (main stack), `infra/cloudfront-waf.yaml` (us-east-1),
`infra/github-deploy-role.yaml` (deploy role), `scripts/deploy.sh` (one command per environment).

## 1. Environments

| | dev | stg | prod |
|---|---|---|---|
| Purpose | integration, Ben's testing | final check before release, client demos | MAPI analysts + approved clients |
| Stack names | `sealevel-dev`, `sealevel-dev-cloudfront-waf` | `sealevel-stg`, … | `sealevel-prod`, … |
| Site | CloudFront URL (optional `sealevel-dev.mapi.gov.il`) | `sealevel-stg.mapi.gov.il` | `sealevel.mapi.gov.il` |
| Data | own Aurora replica, history from 2025-01-01 | own replica, history from 2025-01-01 | own replica, full history (DMS full load) |
| Sync from on-prem | every 5 min | every 5 min | **every 1 min** (architect) |
| Aurora Serverless v2 | 0.5–2 ACU, no deletion protection, 3-day backups | 0.5–2 ACU | 0.5–4 ACU, deletion protection, 14-day backups |
| Sign-in allowlist (SSM) | `mapi.gov.il` | `mapi.gov.il` + test clients | `mapi.gov.il` + approved clients |
| Calibration + Reports (admin) | benp@mapi.gov.il only | benp@mapi.gov.il only | benp@mapi.gov.il only |
| Everyone else | view only — no calibration panel, no Reports tab; API answers 403 | same | same |
| Who deploys | any branch, no approval | `main` only, 1 reviewer | `main` only, required reviewer, same image tag that passed stg |

Each environment has its own database. Corrections made in dev or stg never reach prod. **Calibration work
is done in prod only.** In prod, the calibration layer is the system of record for the validated series.

> **Decision for the AWS team:** use one AWS account for all three stacks, or one account per environment
> (AWS Organizations best practice). The templates support both. For separate accounts, deploy
> `github-deploy-role.yaml` in each account with `EnvironmentPattern=dev|stg|prod`.

## 1b. Network (MAPI sheet `AWS_Network_Architecture_Updated_V3.xlsx`) and the on-prem server

| | dev | stg | prod |
|---|---|---|---|
| VPC (sysadmin allocation, *M-Mapi-Miflas-…*) | **10.26.24.0/24** | **10.26.25.0/24** | **10.26.23.0/24** |
| private-subnet-a (AZ 1) | 10.26.24.0/25 | 10.26.25.0/25 | 10.26.23.0/25 |
| private-subnet-b (AZ 2) | 10.26.24.128/25 | 10.26.25.128/25 | 10.26.23.128/25 |

The design sheet lists 10.0/10.1/10.2.0.0/24. I used the sysadmin's allocation in the *SysAdmin Addresses* sheet,
assuming it is the final one. **Please confirm.**

The sheet has **private subnets only (no NAT)**. The stack handles that this way:
- `CREATE_VPC_ENDPOINTS=true` + `PRIVATE_ROUTE_TABLE_IDS` adds VPC endpoints for S3 (gateway), Secrets Manager,
  SNS and Lambda (interface endpoints in both subnets, so they take a few IPs out of the 2 × 123 available).
- The IMS forecast, alerts and mariners routes run in a separate Lambda **outside** the VPC, so nothing in the
  VPC needs the internet. Cognito, CloudFront, WAF and API Gateway are managed services outside the VPC.

**On-prem PostgreSQL**: the server's firewall opens **TCP/UDP 30886–30890** (`Ports.txt`). 30886/30887 are the
current dashboard API and frontend. The sync needs TCP to PostgreSQL from **10.26.23.0/24, 10.26.24.0/24
and 10.26.25.0/24** over the VPN. Either PostgreSQL listens on, or is forwarded from, a free port in that range
(e.g. **30888**, set `ONPREM_DB_PORT=30888` and `"port": 30888` in the on-prem secret), or IT opens 5432 for
those CIDRs. Only TCP is needed. Add the three CIDRs to `pg_hba.conf` for the `sl_aws_sync` user.

## 2. What we need from the MAPI AWS / network team (blocking)

| # | Item | For |
|---|---|---|
| A1 | AWS account(s) in il-central-1 + deploy `infra/github-deploy-role.yaml` → role ARN | GitHub Actions deploys without stored keys |
| A2 | VPC per environment as in §1b (two private /25 subnets); route table IDs for the S3 endpoint | Lambdas reach Secrets Manager, S3, SNS via endpoints |
| A3 | **Route from those subnets to the on-prem PostgreSQL** (Site-to-Site VPN / Direct Connect), firewall: TCP to the DB port (30888 or 5432) from 10.26.23–25.0/24 | Sync |
| A4 | Lambda concurrency quota ≥ 100 per account (≥ 200 if all three envs share one account) | Reserved concurrency |
| A5 | DNS: `sealevel.mapi.gov.il`, `sealevel-stg.mapi.gov.il` (CNAME → CloudFront) + **ACM certificates in us-east-1** | Custom domains (optional for dev) |
| A6 | Architect sign-off on the one addition to the diagram: the **admin-only Calibration Lambda** that writes only the calibration tables (Aurora stays a read-only replica of the raw data) | Calibration editor |

## 3. What Ben prepares (one-time)

| # | Item |
|---|---|
| B1 | **Read-only on-prem DB user** `sl_aws_sync` (SQL in [DEPLOYMENT.md](DEPLOYMENT.md) §1a) → Secrets Manager secret per account; allow subnet CIDRs in `pg_hba.conf` |
| B2 | **Google OAuth client** (Google Cloud console, Workspace `mapi.gov.il`): consent screen *External*; redirect URIs `https://mapi-sealevel-{dev,stg,prod}.auth.il-central-1.amazoncognito.com/oauth2/idpresponse`; secret → Secrets Manager `sealevel/google-oauth-client-secret` |
| B3 | GitHub → Settings → Environments `dev`, `stg`, `prod`: variables from `infra/params.example.env` + `AWS_DEPLOY_ROLE_ARN`; reviewers on stg/prod; "deployment branches: main" on stg/prod |
| B4 | **Rotate** the on-prem DB passwords that are in git history and any key that was in `frontend/Env.txt` ([review](../review/REVIEW_2026-11-25.md)) |
| B5 | Restrict the GovMap token to the stg/prod domains |

Suggested per-environment values:

```
# dev                                   # stg                                   # prod
COGNITO_DOMAIN_PREFIX=mapi-sealevel-dev  COGNITO_DOMAIN_PREFIX=mapi-sealevel-stg  COGNITO_DOMAIN_PREFIX=mapi-sealevel-prod
SYNC_SCHEDULE='rate(5 minutes)'          SYNC_SCHEDULE='rate(5 minutes)'          SYNC_SCHEDULE='rate(1 minute)'
SYNC_START_DATE=2025-01-01               SYNC_START_DATE=2025-01-01               SYNC_START_DATE=2020-01-01  (or DMS)
AURORA_MAX_ACU=2                         AURORA_MAX_ACU=2                         AURORA_MAX_ACU=4
                                         CUSTOM_DOMAIN=sealevel-stg.mapi.gov.il  CUSTOM_DOMAIN=sealevel.mapi.gov.il
```

## 4. Rollout

| Phase | Steps | Exit criteria |
|---|---|---|
| **0. Merge** | Review & merge PR `fix/review-hydras-editor-aws` → `main`. CI green (backend on PostgreSQL, frontend, cfn-lint, image build). | `main` contains the editor + infra |
| **1. dev** | Actions → Deploy → `dev`. The first run stops at migrations ("Monitors_info2 not found"); restore the schema (`pg_dump --schema-only`), run the deploy again; the sync then fills history from 2025-01-01. Confirm the alarm e-mail. | `/api/health` ok, `/api/stations` 401 without token, Google sign-in works, data ≤ 5 min old, calibration visible only to Ben |
| **2. dev acceptance** | Ben: editor end-to-end (select → delete → interpolate → table edit → commit → undo), exports (validated + raw), predictions, maps, mobile. | Checklist §5 passed |
| **3. stg** | Deploy → `stg` from `main` (reviewer approves). Custom domain + certificate. 1 week soak; CSP report-only violations checked in the browser console. | No 5xx alarms, sync lag < 10 min, no CSP violations |
| **4. prod** | DMS full load of the history (target prep mode **Do nothing**), then Deploy → `prod` with the **same commit** as stg. Switch CSP to enforce after a clean week. | Smoke test + checklist on prod; analysts signed in |
| **5. Cut-over** | Point users to `sealevel.mapi.gov.il`; keep the on-prem server read-only for 2 weeks as fallback; then retire it. Calibration happens only in prod from then on. | On-prem dashboard retired |

Rollback: redeploy the previous image tag (immutable in ECR) — `ImageUri=…/sealevel-backend:<sha>`; data
corrections roll back with **Undo** / `POST /api/calibration/revert`.

## 5. Acceptance checklist (dev, stg, prod)

- [ ] Signed out → only "Sign in with Google"; non-allowlisted Google account is refused
- [ ] Client account: data, graph, table, maps, forecasts, CSV export; **no** calibration panel; `POST /api/calibration/preview` → 403
- [ ] Ben: calibration panel; samples load for a ≤ 14-day window; box-select a spike → Delete → Commit → spike gone from graph, KPI cards, CSV; Raw CSV still has it with `Deleted=true`
- [ ] Interpolate the deleted points → straight line; Undo → deleted again; Undo → original
- [ ] Table view: type a value → Preview → Commit → value shown; audit history lists the user e-mail
- [ ] Sync: newest sample age ≤ schedule + 2 min; CloudWatch alarm fires when the VPN is down (test once in dev)
- [ ] Lighthouse mobile ≥ 80; PWA install on a phone (after the UI redesign)

## 6. Operations

Logs `/aws/lambda/sealevel-<env>-*`, API access log `/sealevel/<env>/api-access`; alarms by e-mail (sync failure,
API 5xx, calibration errors, Aurora at max). Access: edit SSM `/sealevel/<env>/allowed-users`. Full runbook:
[DEPLOYMENT.md](DEPLOYMENT.md).
