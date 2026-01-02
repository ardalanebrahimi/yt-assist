"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # YouTube API
    youtube_api_key: str = ""
    channel_id: str = "UCmHxUdpnCfQTQtwbxN9mtOA"

    # OpenAI API (for Whisper)
    openai_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./data/yt_assist.db"

    # API Server
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    @property
    def data_dir(self) -> Path:
        """Get the data directory path."""
        return Path("data")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
