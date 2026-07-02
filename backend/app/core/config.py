"""Application configuration using pydantic-settings."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "AutoMind AI Platform"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Database (RDS PostgreSQL)
    database_url: str = "postgresql+asyncpg://automind:automind@localhost:5432/cp_portal"
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # AWS
    aws_region: str = "ap-south-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # DynamoDB
    dynamodb_table_name: str = "automind_sessions"

    # S3
    s3_assets_bucket: str = "automind-assets"
    s3_tour_scripts_bucket: str = "automind-tour-scripts"

    # Cognito
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""

    # JWT
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_hours: int = 24

    # SQS
    sqs_processing_queue_url: str = ""

    # External APIs
    gupshup_api_key: str = ""
    gupshup_app_name: str = ""
    gupshup_source_number: str = ""  # e.g. "91xxxxxxxxxx"
    sns_topic_arn: str = ""          # arn:aws:sns:ap-south-1:...:hot-lead-alerts
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    lead_alert_threshold: int = 7


settings = Settings()
