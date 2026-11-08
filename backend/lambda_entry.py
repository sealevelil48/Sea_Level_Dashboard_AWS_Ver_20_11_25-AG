"""
AWS Lambda entry points (one container image, several functions — see infra/template.yaml).

  lambda_entry.api_handler        API Gateway → FastAPI app (read-only DB credentials)
  lambda_entry.calibration_handler  same app, calibration routes (calibration writer credentials)
  lambdas.sync.main.handler       EventBridge, every minute: on-prem PostgreSQL → Aurora
  lambdas.cognito_access.main.handler  Cognito triggers: only approved Google accounts may sign in

Database credentials come from Secrets Manager (DB_SECRET_ARN) at cold start, never from env text.
"""
import json
import os
from urllib.parse import quote_plus


def _db_uri_from_secret():
    arn = os.getenv("DB_SECRET_ARN")
    if not arn or os.getenv("DB_URI"):
        return
    import boto3
    secret = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"])
    host = os.getenv("DB_HOST_OVERRIDE") or secret["host"]          # e.g. the RDS Proxy endpoint
    os.environ["DB_URI"] = (
        f"postgresql+psycopg2://{quote_plus(secret['username'])}:{quote_plus(secret['password'])}"
        f"@{host}:{secret.get('port', 5432)}/{secret.get('dbname', os.getenv('DB_NAME', 'sealevel'))}?sslmode=require"
    )


_db_uri_from_secret()

from mangum import Mangum  # noqa: E402
from app import app  # noqa: E402

api_handler = Mangum(app, lifespan="off")
calibration_handler = api_handler  # same app; API Gateway routes /api/calibration/* to the writer function
