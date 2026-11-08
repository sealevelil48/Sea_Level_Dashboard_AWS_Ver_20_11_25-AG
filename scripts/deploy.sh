#!/usr/bin/env bash
# =============================================================================
# Deploy the Sea Level Dashboard to AWS (il-central-1).
#
#   scripts/deploy.sh <env> <config-file>      e.g. scripts/deploy.sh prod infra/params.prod.env
#
# Steps: build + push backend image → CloudFront WAF (us-east-1) → sam deploy → run migrations → build + upload frontend
#        → CloudFront invalidation → smoke test.
# Needs: aws CLI v2, sam CLI, docker, node 18+, jq. Credentials via SSO/OIDC (no static keys).
# =============================================================================
set -euo pipefail

ENV="${1:?usage: deploy.sh <dev|prod> <params-file>}"
PARAMS_FILE="${2:?params file, see infra/params.example.env}"
# shellcheck disable=SC1090
source "$PARAMS_FILE"

REGION="${AWS_REGION:-il-central-1}"
STACK="sealevel-${ENV}"
REPO="sealevel-backend"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
TAG="$(git -C "$ROOT" rev-parse --short HEAD)$(git -C "$ROOT" diff --quiet || echo -dirty)"
IMAGE="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO}:${TAG}"

echo "▶ ${STACK} in ${REGION} (account ${ACCOUNT}), image ${TAG}"

# --- 1. Backend image --------------------------------------------------------
aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$REPO" --region "$REGION" \
      --image-scanning-configuration scanOnPush=true --image-tag-mutability IMMUTABLE >/dev/null
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
if ! aws ecr describe-images --repository-name "$REPO" --image-ids imageTag="$TAG" --region "$REGION" >/dev/null 2>&1; then
  docker build --platform linux/amd64 --provenance=false -f "$ROOT/backend/Dockerfile.lambda" -t "$IMAGE" "$ROOT/backend"
  docker push "$IMAGE"
fi

# --- 2. Infrastructure -------------------------------------------------------
# The origin-verify token is generated once and kept in SSM so redeploys don't rotate it.
TOKEN_PARAM="/sealevel/${ENV}/origin-verify-token"
ORIGIN_TOKEN="$(aws ssm get-parameter --name "$TOKEN_PARAM" --with-decryption --query Parameter.Value --output text --region "$REGION" 2>/dev/null || true)"
if [ -z "$ORIGIN_TOKEN" ]; then
  ORIGIN_TOKEN="$(openssl rand -hex 32)"
  aws ssm put-parameter --name "$TOKEN_PARAM" --type SecureString --value "$ORIGIN_TOKEN" --region "$REGION" >/dev/null
fi

# CloudFront WAF ("AWS WAF - Request Filtering") must live in us-east-1.
aws cloudformation deploy --template-file "$ROOT/infra/cloudfront-waf.yaml" --stack-name "${STACK}-cloudfront-waf" \
  --region us-east-1 --parameter-overrides Env="$ENV" --no-fail-on-empty-changeset
CF_WAF_ARN="$(aws cloudformation describe-stacks --stack-name "${STACK}-cloudfront-waf" --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='WebAclArn'].OutputValue" --output text)"

sam deploy --template-file "$ROOT/infra/template.yaml" --stack-name "$STACK" --region "$REGION" \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND --no-fail-on-empty-changeset --resolve-s3 \
  --parameter-overrides \
    Env="$ENV" ImageUri="$IMAGE" VpcId="$VPC_ID" PrivateSubnetIds="$PRIVATE_SUBNET_IDS" \
    OnPremCidr="$ONPREM_CIDR" OnPremSecretArn="$ONPREM_SECRET_ARN" \
    GoogleClientId="$GOOGLE_CLIENT_ID" GoogleClientSecretName="$GOOGLE_CLIENT_SECRET_NAME" \
    CognitoDomainPrefix="$COGNITO_DOMAIN_PREFIX" AdminEmails="$ADMIN_EMAILS" AllowedUsers="$ALLOWED_USERS" \
    AlarmEmail="$ALARM_EMAIL" OriginVerifyToken="$ORIGIN_TOKEN" CloudFrontWebAclArn="$CF_WAF_ARN"

out() { aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
          --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }

# --- 3. Database migrations + least-privilege users --------------------------
echo "▶ migrations"
aws lambda invoke --function-name "$(out MigrateFunctionName)" --region "$REGION" \
  --cli-read-timeout 310 /tmp/migrate.json >/dev/null
cat /tmp/migrate.json; echo
grep -q '"applied"' /tmp/migrate.json || { echo "✖ migrations failed"; exit 1; }

# --- 4. Frontend ---------------------------------------------------------------
echo "▶ frontend"
(
  cd "$ROOT/frontend"
  npm ci --no-audit --no-fund
  REACT_APP_API_URL="" \
  REACT_APP_AUTH_MODE=cognito \
  REACT_APP_COGNITO_DOMAIN="$(out CognitoDomain)" \
  REACT_APP_COGNITO_CLIENT_ID="$(out UserPoolClientId)" \
  GENERATE_SOURCEMAP=false npm run build
)
BUCKET="$(out FrontendBucketName)"
# Hashed assets: cache forever. index.html / service worker / manifest: always revalidate.
aws s3 sync "$ROOT/frontend/build" "s3://$BUCKET" --delete --region "$REGION" \
  --exclude index.html --exclude service-worker.js --exclude manifest.json \
  --cache-control "public, max-age=31536000, immutable"
for f in index.html service-worker.js manifest.json; do
  [ -f "$ROOT/frontend/build/$f" ] && aws s3 cp "$ROOT/frontend/build/$f" "s3://$BUCKET/$f" --region "$REGION" \
    --cache-control "no-cache"
done
aws cloudfront create-invalidation --distribution-id "$(out DistributionId)" --paths "/index.html" "/" >/dev/null

# --- 5. Smoke test -----------------------------------------------------------
SITE="$(out SiteUrl)"
echo "▶ smoke test ${SITE}"
curl -fsS "${SITE}/api/health" && echo
code="$(curl -s -o /dev/null -w '%{http_code}' "${SITE}/api/stations")"
[ "$code" = "401" ] || { echo "✖ /api/stations should require sign-in, got ${code}"; exit 1; }
echo "✔ deployed: ${SITE}"
echo "  Google OAuth redirect URI: $(out GoogleRedirectUri)"
