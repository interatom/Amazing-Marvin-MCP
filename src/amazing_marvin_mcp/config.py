import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Configuration settings for the Amazing Marvin MCP"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API settings
    amazing_marvin_api_key: str
    amazing_marvin_full_access_token: str | None = None

    # CouchDB / Cloudant direct-access settings (optional — enables DB fast-paths)
    amazing_marvin_db_uri: str | None = None
    amazing_marvin_db_name: str | None = None
    amazing_marvin_db_user: str | None = None
    amazing_marvin_db_password: str | None = None

    # Server settings
    port: int = Field(default=3000)
    host: str = Field(default="0.0.0.0")

    # FastMCP settings
    max_context_size: int = Field(default=8192)
    max_request_size: int = Field(default=32768)


def get_settings() -> Settings:
    """Get configuration settings with environment variable validation"""
    try:
        return Settings()
    except Exception:
        logger.exception("Configuration error")
        raise
