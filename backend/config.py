"""
Configuration management for Sea Level Monitoring System
Supports both local development (.env files) and AWS Secrets Manager (production Lambda)
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseSettings, validator
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load local .env file if it exists (for local development)
load_dotenv()


def get_secrets_from_aws(environment: str) -> Dict[str, Any]:
    """
    Fetch secrets from AWS Secrets Manager.

    Retrieves two secrets:
    - sealevel/{environment}/database: Database connection credentials
    - sealevel/{environment}/api-keys: API keys and secret key

    Args:
        environment: 'dev', 'staging', or 'prod'

    Returns:
        Dictionary with keys: database_url, secret_key, govmap_api_key
    """
    try:
        import boto3

        client = boto3.client('secretsmanager', region_name='il-central-1')
        secrets = {}

        # Fetch database credentials
        try:
            db_response = client.get_secret_value(SecretId=f'sealevel/{environment}/database')
            db_secret = json.loads(db_response['SecretString'])
            secrets['database_url'] = (
                f"postgresql://{db_secret['username']}:{db_secret['password']}"
                f"@{db_secret['host']}:{db_secret['port']}/{db_secret['dbname']}"
            )
            logger.info(f"✓ Loaded database credentials from AWS Secrets Manager (sealevel/{environment}/database)")
        except Exception as e:
            logger.error(f"✗ Failed to fetch database secret: {e}")
            raise

        # Fetch API keys
        try:
            api_response = client.get_secret_value(SecretId=f'sealevel/{environment}/api-keys')
            api_secret = json.loads(api_response['SecretString'])
            secrets['secret_key'] = api_secret.get('secret_key')
            secrets['govmap_api_key'] = api_secret.get('govmap_api_key')
            logger.info(f"✓ Loaded API keys from AWS Secrets Manager (sealevel/{environment}/api-keys)")
        except Exception as e:
            logger.error(f"✗ Failed to fetch API keys secret: {e}")
            raise

        return secrets

    except ImportError:
        logger.error("boto3 not installed. Cannot fetch secrets from AWS Secrets Manager.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching secrets from AWS: {e}")
        raise


def load_secrets() -> Dict[str, Any]:
    """
    Load secrets from either local .env (development) or AWS Secrets Manager (production).

    Decision logic:
    - If ENVIRONMENT=development or not set → use local .env file
    - If ENVIRONMENT=staging or prod → fetch from AWS Secrets Manager

    Returns:
        Dictionary with keys: database_url, secret_key, govmap_api_key
    """
    environment = os.getenv('ENVIRONMENT', 'development')

    if environment == 'development':
        logger.info("Loading secrets from local .env file (development mode)")
        return {
            'database_url': os.getenv('DATABASE_URL', 'postgresql://username:password@localhost:5432/sealevel_monitoring'),
            'secret_key': os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
            'govmap_api_key': os.getenv('GOVMAP_API_KEY', 'dev-api-key-placeholder'),
        }
    else:
        logger.info(f"Loading secrets from AWS Secrets Manager ({environment} environment)")
        return get_secrets_from_aws(environment)


class Settings(BaseSettings):
    # Database Configuration
    database_url: str = "postgresql://username:password@localhost:5432/sealevel_monitoring"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600

    # Cache Configuration
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 300

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: List[str] = ["http://localhost:3000"]

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Security Configuration
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 30

    # Environment Configuration
    environment: str = "development"

    # External Services
    ims_forecast_url: str = "https://ims.gov.il/sites/default/files/ims_data/xml_files/isr_sea.xml"
    govmap_api_key: str = "dev-api-key-placeholder"

    # Performance Settings
    max_data_points: int = 10000
    request_timeout: int = 30

    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False

# Load secrets at module initialization
try:
    _secrets = load_secrets()
except Exception as e:
    logger.warning(f"Failed to load secrets: {e}. Using defaults.")
    _secrets = {
        'database_url': None,
        'secret_key': 'dev-secret-key-change-in-production',
        'govmap_api_key': 'dev-api-key-placeholder',
    }

# Global settings instance with secrets
settings = Settings(
    database_url=_secrets.get('database_url') or os.getenv('DATABASE_URL', Settings.database_url),
    secret_key=_secrets.get('secret_key') or os.getenv('SECRET_KEY', Settings.secret_key),
    govmap_api_key=_secrets.get('govmap_api_key') or os.getenv('GOVMAP_API_KEY', Settings.govmap_api_key),
    environment=os.getenv('ENVIRONMENT', 'development'),
)

# Database connection string with proper error handling
def get_database_url():
    """Get database URL with validation"""
    db_url = settings.database_url

    if not db_url or db_url == "postgresql://username:password@localhost:5432/sealevel_monitoring":
        raise ValueError(
            "Database URL not configured. Please set DATABASE_URL environment variable "
            "or configure AWS Secrets Manager for production."
        )

    return db_url

# Logging configuration
def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format=settings.log_format
    )

    # Reduce noise from external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)

    return logging.getLogger(__name__)